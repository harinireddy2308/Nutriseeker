"""End-to-end meal analysis: vision + text + portions + IFCT/USDA."""
from __future__ import annotations

import re
from typing import Any

from PIL import Image

from nutriseeker.app.services.nutrition import get_store
from nutriseeker.app.services.portion import PortionItem, build_portions, scale_nutrients_per_100g
from nutriseeker.app.services.text_parse import extract_foods_from_text, merge_food_lists
from nutriseeker.app.services import vision


def _clean_caption_phrase(s: str) -> str:
    s = s.lower().strip()
    for phrase in (
        "a plate of",
        "a bowl of",
        "a dish of",
        "a serving of",
        "a photo of",
        "a picture of",
        "an image of",
        "this is",
        "there is",
        "shows",
    ):
        s = s.replace(phrase, "")
    s = re.split(r"[,;]| and | with ", s)[0]
    return s.strip()


def analyze_image_and_text(
    image: Image.Image | None,
    user_text: str,
    gram_overrides: dict[str, float] | None = None,
    text_only: bool = False,
) -> dict[str, Any]:
    store = get_store()
    store.load()

    caption = ""
    backend = "text-only"
    if not text_only and image is not None:
        v = vision.describe_meal(image.convert("RGB"), user_context=user_text)
        caption = v["caption"]
        backend = v["backend"]

    foods = merge_food_lists(caption, user_text)
    if text_only and not foods:
        foods = extract_foods_from_text(user_text)
    if not foods and caption:
        foods = [_clean_caption_phrase(caption) or caption[:80]]

    portions: list[PortionItem] = build_portions(foods, user_text=user_text, overrides=gram_overrides)

    items_out: list[dict[str, Any]] = []
    total = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0}

    for food_phrase, por in zip(foods, portions):
        resolved, alts = store.resolve(food_phrase)
        alt_dicts = [
            {"score": round(s, 3), **r.as_dict()} for s, r in alts[:5]
        ]
        if resolved is None:
            items_out.append(
                {
                    "query": food_phrase,
                    "grams": por.grams,
                    "portion_basis": por.basis,
                    "matched": None,
                    "alternatives": alt_dicts,
                    "scaled": None,
                }
            )
            continue
        base = resolved.as_dict()
        scaled = scale_nutrients_per_100g(base, por.grams)
        items_out.append(
            {
                "query": food_phrase,
                "grams": por.grams,
                "portion_basis": por.basis,
                "matched": base,
                "alternatives": alt_dicts,
                "scaled": scaled,
            }
        )
        for k in total:
            total[k] += float(scaled[k])

    return {
        "caption": caption,
        "vision_backend": backend,
        "foods_detected": foods,
        "items": items_out,
        "totals": {k: round(v, 2) for k, v in total.items()},
    }


def analyze_text_only(user_text: str, gram_overrides: dict[str, float] | None = None) -> dict[str, Any]:
    return analyze_image_and_text(None, user_text, gram_overrides=gram_overrides, text_only=True)
