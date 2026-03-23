"""IFCT-first nutrition lookup with local USDA CSV fallback and semantic ranking."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nutriseeker.app.config import IFCT_CSV, USDA_CSV, SENTENCE_MODEL

log = logging.getLogger(__name__)

# Mirrors your notebook: keyword hints → canonical IFCT row names (substring match).
FOOD_KEYWORD_MAP: dict[str, str] = {
    "rice": "Rice, raw, milled",
    "biryani": "Rice, raw, milled",
    "poha": "Rice flakes",
    "puffed rice": "Rice puffed",
    "roti": "Wheat flour, atta",
    "chapati": "Wheat flour, atta",
    "paratha": "Wheat flour, atta",
    "bread": "Wheat flour, refined",
    "naan": "Wheat flour, refined",
    "upma": "Wheat, semolina",
    "semolina": "Wheat, semolina",
    "wheat": "Wheat, whole",
    "bajra": "Bajra",
    "ragi": "Finger millet",
    "millet": "Finger millet",
    "maize": "Maize, dry",
    "corn": "Maize, dry",
    "oat": "Oat",
    "dal": "Red gram, dal",
    "lentil": "Lentil dal",
    "rajma": "Kidney bean",
    "chana": "Bengal gram, dal",
    "chickpea": "Bengal gram, dal",
    "moong": "Green gram, dal",
    "urad": "Black gram, dal",
    "chicken": "Chicken, poultry, breast, skinless",
    "mutton": "Mutton, muscle",
    "egg": "Egg, poultry, whole, raw",
    "omelette": "Egg, poultry, whole, raw",
    "boiled egg": "Egg, poultry, whole, boiled",
    "fish": "Rohu",
    "prawn": "Prawn",
    "milk": "Milk, whole, Cow",
    "curd": "Curd",
    "yogurt": "Curd",
    "paneer": "Paneer",
    "butter": "Butter",
    "ghee": "Ghee",
    "potato": "Potato, brown skin, big",
    "aloo": "Potato, brown skin, big",
    "tomato": "Tomato, ripe",
    "onion": "Onion, big",
    "spinach": "Spinach",
    "palak": "Spinach",
    "carrot": "Carrot",
    "cabbage": "Cabbage",
    "cauliflower": "Cauliflower",
    "brinjal": "Brinjal",
    "banana": "Banana, ripe, robusta",
    "apple": "Apple",
    "mango": "Mango, ripe",
    "orange": "Orange",
    "grapes": "Grapes, black",
    "papaya": "Papaya, ripe",
    "watermelon": "Watermelon",
    "cashew": "Cashewnut",
    "almond": "Almond",
    "peanut": "Groundnut",
    "groundnut": "Groundnut",
    "coconut": "Coconut, fresh",
}


@dataclass
class NutritionRow:
    source: str
    food: str
    calories: float
    protein: float
    carbs: float
    fat: float
    fiber: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "food": self.food,
            "calories": self.calories,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
            "fiber": self.fiber,
        }


def _kj_to_kcal(enerc: float) -> float:
    return round(float(enerc) / 4.184, 1)


class NutritionStore:
    """Loads IFCT + optional local USDA table; semantic search over IFCT names."""

    _embedder = None
    _ifct_matrix: np.ndarray | None = None
    _ifct_names: list[str] | None = None

    def __init__(self, ifct_path: Path | None = None, usda_path: Path | None = None):
        self.ifct_path = ifct_path or IFCT_CSV
        self.usda_path = usda_path or USDA_CSV
        self._df_ifct: pd.DataFrame | None = None
        self._df_usda: pd.DataFrame | None = None
        self._ready = False

    def load(self) -> None:
        if self._df_ifct is not None:
            return
        if not self.ifct_path.is_file():
            raise FileNotFoundError(
                f"IFCT CSV not found at {self.ifct_path}. "
                "Place ifct2017_compositions.csv under nutriseeker/data/ or set NUTRI_IFCT_CSV."
            )
        self._df_ifct = pd.read_csv(self.ifct_path)
        req = {"name", "enerc", "protcnt", "choavldf", "fatce", "fibtg"}
        missing = req - set(self._df_ifct.columns)
        if missing:
            raise ValueError(f"IFCT CSV missing columns: {missing}")

        if self.usda_path.is_file():
            self._df_usda = pd.read_csv(self.usda_path)
        else:
            self._df_usda = None
            log.warning("No local USDA CSV at %s — IFCT-only mode.", self.usda_path)

        self._build_ifct_index()
        self._ready = True

    def _build_ifct_index(self) -> None:
        from sentence_transformers import SentenceTransformer

        assert self._df_ifct is not None
        self._ifct_names = self._df_ifct["name"].astype(str).tolist()
        self._embedder = SentenceTransformer(SENTENCE_MODEL)
        self._ifct_matrix = self._embedder.encode(
            self._ifct_names,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def _series_to_row(self, data: pd.Series) -> NutritionRow:
        return NutritionRow(
            source="IFCT 2017",
            food=str(data["name"]),
            calories=_kj_to_kcal(float(data["enerc"])),
            protein=round(float(data["protcnt"]), 1),
            carbs=round(float(data["choavldf"]), 1),
            fat=round(float(data["fatce"]), 1),
            fiber=round(float(data["fibtg"]), 1),
        )

    def _row_from_ifct_iloc(self, idx: int) -> NutritionRow:
        assert self._df_ifct is not None
        return self._series_to_row(self._df_ifct.iloc[idx])

    def lookup_keyword(self, food_name: str) -> NutritionRow | None:
        assert self._df_ifct is not None
        q = food_name.lower().strip()
        for keyword, mapped in FOOD_KEYWORD_MAP.items():
            if keyword in q:
                result = self._df_ifct[
                    self._df_ifct["name"].str.lower().str.contains(mapped.lower(), na=False)
                ]
                if not result.empty:
                    return self._series_to_row(result.iloc[0])
        return None

    def lookup_substring(self, food_name: str) -> NutritionRow | None:
        assert self._df_ifct is not None
        q = food_name.lower().strip()
        result = self._df_ifct[self._df_ifct["name"].str.lower().str.contains(re.escape(q), na=False)]
        if not result.empty:
            return self._series_to_row(result.iloc[0])
        return None

    def lookup_semantic(self, food_name: str, top_k: int = 3) -> list[tuple[float, NutritionRow]]:
        assert self._embedder is not None and self._ifct_matrix is not None and self._ifct_names is not None
        qv = self._embedder.encode(
            [food_name], convert_to_numpy=True, normalize_embeddings=True
        )[0]
        sims = self._ifct_matrix @ qv
        idxs = np.argsort(-sims)[:top_k]
        out: list[tuple[float, NutritionRow]] = []
        for i in idxs:
            out.append((float(sims[i]), self._row_from_ifct_iloc(int(i))))
        return out

    def lookup_usda_local(self, food_name: str) -> NutritionRow | None:
        if self._df_usda is None or self._df_usda.empty:
            return None
        df = self._df_usda
        q = food_name.lower().strip()
        mask = df["name"].astype(str).str.lower().str.contains(re.escape(q), na=False)
        if not mask.any():
            mask = df["name"].astype(str).str.lower().str.startswith(q[: min(4, len(q))], na=False)
        if not mask.any():
            return None
        row = df[mask].iloc[0]
        return NutritionRow(
            source="USDA (local CSV)",
            food=str(row["name"]),
            calories=round(float(row["calories"]), 1),
            protein=round(float(row["protein"]), 1),
            carbs=round(float(row["carbs"]), 1),
            fat=round(float(row["fat"]), 1),
            fiber=round(float(row["fiber"]), 1),
        )

    def resolve(self, food_name: str) -> tuple[NutritionRow | None, list[tuple[float, NutritionRow]]]:
        """Return best row + semantic alternatives for transparency."""
        self.load()
        alt: list[tuple[float, NutritionRow]] = []
        hit = self.lookup_keyword(food_name)
        if hit:
            return hit, self.lookup_semantic(food_name, top_k=3)
        hit = self.lookup_substring(food_name)
        if hit:
            return hit, self.lookup_semantic(food_name, top_k=3)
        alt = self.lookup_semantic(food_name, top_k=5)
        if alt:
            best = alt[0][1]
            if alt[0][0] > 0.35:
                return best, alt
        hit = self.lookup_usda_local(food_name)
        if hit:
            return hit, alt
        return None, alt


_store: NutritionStore | None = None


def get_store() -> NutritionStore:
    global _store
    if _store is None:
        _store = NutritionStore()
    return _store
