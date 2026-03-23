"""Extract food phrases from free text (meal description) without cloud APIs."""
from __future__ import annotations

import re

from nutriseeker.app.services.portion import split_food_phrases


def extract_foods_from_text(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    # Remove filler
    t = text.strip()
    t = re.sub(r"\b(i|we)\s+(ate|had|eat)\b", "", t, flags=re.IGNORECASE)
    return split_food_phrases(t)


def merge_food_lists(
    from_image_caption: str,
    from_user_text: str,
) -> list[str]:
    """Union caption-derived and user foods; preserve order, dedupe."""
    a = split_food_phrases(from_image_caption) if from_image_caption else []
    b = extract_foods_from_text(from_user_text) if from_user_text else []
    seen: set[str] = set()
    out: list[str] = []
    for x in a + b:
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out
