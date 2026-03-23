"""NutriSeeker FastAPI app — advanced UI + local models (no API keys)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from nutriseeker.app.services.pipeline import analyze_image_and_text, analyze_text_only

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"

app = FastAPI(
    title="NutriSeeker",
    description="Multimodal diet assessment — IFCT + local models (DietAI-style).",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "nutriseeker"}


@app.post("/api/analyze")
async def api_analyze(
    image: UploadFile | None = File(None),
    text: str = Form(""),
    overrides_json: str = Form(""),
):
    """Analyze meal image + optional text; `overrides_json` maps food substring → grams."""
    from PIL import Image
    import io

    overrides: dict[str, float] = {}
    if overrides_json.strip():
        try:
            overrides = json.loads(overrides_json)
            if not isinstance(overrides, dict):
                raise ValueError("overrides must be a JSON object")
            overrides = {str(k): float(v) for k, v in overrides.items()}
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise HTTPException(400, f"Invalid overrides JSON: {e}")

    pil = None
    if image is not None and image.filename:
        raw = await image.read()
        if raw:
            pil = Image.open(io.BytesIO(raw))

    if pil is None and not text.strip():
        raise HTTPException(400, "Provide an image and/or meal description text.")

    try:
        result = analyze_image_and_text(pil, text, gram_overrides=overrides or None)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        log.exception("analyze failed")
        raise HTTPException(500, str(e)) from e
    return result


@app.post("/api/analyze-text")
async def api_analyze_text(
    text: str = Form(...),
    overrides_json: str = Form(""),
):
    overrides: dict[str, float] = {}
    if overrides_json.strip():
        try:
            overrides = json.loads(overrides_json)
            overrides = {str(k): float(v) for k, v in overrides.items()}
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise HTTPException(400, f"Invalid overrides JSON: {e}")
    if not text.strip():
        raise HTTPException(400, "Text is required.")
    try:
        return analyze_text_only(text, gram_overrides=overrides or None)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))


if STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/")
def index():
    index_path = STATIC / "index.html"
    if not index_path.is_file():
        return {"detail": "Frontend not built — add nutriseeker/app/static/index.html"}
    return FileResponse(index_path)
