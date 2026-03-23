"""Heuristic portion sizes (grams) for Indian meals — complements vision/text, no API."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Typical single-serving estimates when photo scale is unknown (DietAI-style priors).
DEFAULT_GRAMS: dict[str, float] = {
    "rice": 150,
    "biryani": 200,
    "poha": 120,
    "roti": 40,
    "chapati": 40,
    "paratha": 60,
    "bread": 35,
    "naan": 90,
    "dal": 120,
    "lentil": 120,
    "rajma": 100,
    "chana": 100,
    "chicken": 120,
    "mutton": 100,
    "fish": 120,
    "egg": 55,
    "paneer": 80,
    "potato": 100,
    "vegetable": 80,
    "salad": 70,
    "curry": 150,
    "sabzi": 100,
    "milk": 200,
    "curd": 100,
    "banana": 100,
    "default": 100,
}


@dataclass
class PortionItem:
    name: str
    grams: float
    basis: str  # "keyword" | "default" | "user" | "parsed"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def estimate_grams_for_token(token: str, user_hint_grams: dict[str, float] | None = None) -> PortionItem:
    t = _norm(token)
    if user_hint_grams:
        for k, g in user_hint_grams.items():
            if _norm(k) in t or t in _norm(k):
                return PortionItem(name=token.strip(), grams=float(g), basis="user")
    for key, g in DEFAULT_GRAMS.items():
        if key in t:
            return PortionItem(name=token.strip(), grams=g, basis="keyword")
    return PortionItem(name=token.strip(), grams=DEFAULT_GRAMS["default"], basis="default")


def split_food_phrases(text: str) -> list[str]:
    """Split caption or user text into candidate food tokens."""
    if not text or not text.strip():
        return []
    s = text.replace("/", ",")
    parts = re.split(r",|\band\b|\bwith\b|\bon\b", s, flags=re.IGNORECASE)
    out: list[str] = []
    for p in parts:
        p = re.sub(r"^(a|an|the|some|plate of|bowl of|dish of)\s+", "", p.strip(), flags=re.IGNORECASE)
        p = p.strip(" .")
        if len(p) > 2:
            out.append(p)
    return out[:12]


def build_portions(
    foods: list[str],
    user_text: str = "",
    overrides: dict[str, float] | None = None,
) -> list[PortionItem]:
    """Assign grams per detected food phrase."""
    hints: dict[str, float] = {}
    if overrides:
        hints.update(overrides)
    # Parse "rice 200g" or "dal: 150" from user text
    if user_text:
        for m in re.finditer(
            r"([A-Za-z][A-Za-z\s]+?)\s*[:=]?\s*(\d+)\s*(g|gm|gram|grams)?",
            user_text,
            re.IGNORECASE,
        ):
            hints[m.group(1).strip()] = float(m.group(2))
    items: list[PortionItem] = []
    seen: set[str] = set()
    for f in foods:
        key = _norm(f)
        if key in seen:
            continue
        seen.add(key)
        items.append(estimate_grams_for_token(f, hints))
    return items


def scale_nutrients_per_100g(row: dict[str, Any], grams: float) -> dict[str, Any]:
    f = grams / 100.0
    keys = ("calories", "protein", "carbs", "fat", "fiber")
    scaled = {k: round(float(row[k]) * f, 2) for k in keys if k in row}
    scaled["grams"] = round(grams, 1)
    scaled["food"] = row.get("food", "")
    scaled["source"] = row.get("source", "")
    return scaled
