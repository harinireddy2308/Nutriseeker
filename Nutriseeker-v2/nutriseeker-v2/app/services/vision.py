"""Local vision captioning: BLIP (CPU-friendly) or BLIP-2 (GPU), optional Ollama LLaVA."""
from __future__ import annotations

import base64
import io
import logging
from typing import Literal

import requests
import torch
from PIL import Image

from nutriseeker.app.config import OLLAMA_HOST, OLLAMA_VISION_MODEL, VISION_BACKEND

log = logging.getLogger(__name__)

_processor = None
_model = None
_backend: str | None = None


def _pick_backend() -> Literal["blip", "blip2"]:
    if VISION_BACKEND in ("blip", "blip2"):
        return VISION_BACKEND  # type: ignore[return-value]
    return "blip2" if torch.cuda.is_available() else "blip"


def _load_blip():
    global _processor, _model, _backend
    from transformers import BlipForConditionalGeneration, BlipProcessor

    _processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
    _model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    _model = _model.to(dev)
    _model.eval()
    _backend = "blip"


def _load_blip2():
    global _processor, _model, _backend
    from transformers import Blip2ForConditionalGeneration, Blip2Processor

    _processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    kwargs = {"torch_dtype": dtype}
    if torch.cuda.is_available():
        kwargs["device_map"] = "auto"
    _model = Blip2ForConditionalGeneration.from_pretrained(
        "Salesforce/blip2-opt-2.7b",
        **kwargs,
    )
    if not torch.cuda.is_available():
        _model = _model.to("cpu")
    _model.eval()
    _backend = "blip2"


def ensure_vision_loaded() -> str:
    global _backend
    if _model is not None and _backend:
        return _backend
    choice = _pick_backend()
    log.info("Loading vision model: %s", choice)
    if choice == "blip2":
        try:
            _load_blip2()
        except Exception as e:
            log.warning("BLIP-2 load failed (%s), falling back to BLIP.", e)
            _load_blip()
    else:
        _load_blip()
    assert _backend
    return _backend


def caption_with_transformers(image: Image.Image, prompt: str | None = None) -> str:
    ensure_vision_loaded()
    dev = next(_model.parameters()).device
    if _backend == "blip2":
        if prompt:
            inputs = _processor(images=image, text=prompt, return_tensors="pt")
        else:
            inputs = _processor(images=image, return_tensors="pt")
        inputs = inputs.to(dev)
        if dev.type == "cuda":
            inputs = inputs.to(torch.float16)
        gen = _model.generate(**inputs, max_new_tokens=80)
        return _processor.decode(gen[0], skip_special_tokens=True).strip()
    inputs = _processor(images=image, return_tensors="pt").to(dev)
    gen = _model.generate(**inputs, max_length=80)
    return _processor.decode(gen[0], skip_special_tokens=True).strip()


def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST.rstrip('/')}/api/tags", timeout=2)
        return r.status_code == 200
    except OSError:
        return False


def caption_with_ollama(image: Image.Image, prompt: str) -> str | None:
    if not ollama_available():
        return None
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=92)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    try:
        r = requests.post(
            f"{OLLAMA_HOST.rstrip('/')}/api/generate",
            json={
                "model": OLLAMA_VISION_MODEL,
                "prompt": prompt,
                "images": [b64],
                "stream": False,
            },
            timeout=300,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()
    except Exception as e:
        log.warning("Ollama vision failed: %s", e)
        return None


def describe_meal(
    image: Image.Image,
    user_context: str = "",
) -> dict:
    """Caption with optional Ollama (LLaVA); otherwise BLIP / BLIP-2."""
    use_ollama = VISION_BACKEND == "ollama" or (
        VISION_BACKEND == "auto" and ollama_available()
    )
    if use_ollama:
        p = (
            "List each visible food item in this meal, comma-separated. "
            "Add one short phrase about overall portion (small/medium/large). "
        )
        if user_context.strip():
            p += f" User note: {user_context}"
        o = caption_with_ollama(image, p)
        if o:
            return {"caption": o, "backend": f"ollama:{OLLAMA_VISION_MODEL}"}

    ensure_vision_loaded()
    if _backend == "blip2" and user_context.strip():
        prompt = f"Describe this meal for nutrition logging. Context: {user_context}"
        cap = caption_with_transformers(image, prompt)
    else:
        cap = caption_with_transformers(image)
    return {"caption": cap, "backend": _backend or "unknown"}
