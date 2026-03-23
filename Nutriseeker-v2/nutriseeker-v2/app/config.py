"""Runtime paths and model selection (no API keys)."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

IFCT_CSV = Path(os.environ.get("NUTRI_IFCT_CSV", str(DATA_DIR / "ifct2017_compositions.csv")))
USDA_CSV = Path(os.environ.get("NUTRI_USDA_CSV", str(DATA_DIR / "usda_foods_sample.csv")))

# auto: BLIP-2 on CUDA, BLIP base on CPU (faster cold start on weak hardware)
VISION_BACKEND = os.environ.get("NUTRI_VISION", "auto")  # auto | blip | blip2 | ollama

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llava:7b")

SENTENCE_MODEL = os.environ.get(
    "NUTRI_SENTENCE_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
