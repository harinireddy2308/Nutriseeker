# NutriSeeker (v2)

Multimodal meal analysis aligned with **DietAI24**-style pipelines: **image + text → food items → portion priors → IFCT-first nutrition** (local **USDA CSV** fallback). **No cloud API keys** — models load from Hugging Face; optional **Ollama + LLaVA** runs only on your machine.

## Where to run (no GPU laptop vs Colab)

| Environment | Pros |
|-------------|------|
| **Google Colab / Kaggle** | Free GPU for BLIP-2 / faster iteration. Upload `ifct2017_compositions.csv` to the runtime. |
| **This repo + CPU** | Uses **BLIP-large** automatically when CUDA is unavailable (slower but works). |
| **Local GPU** | **BLIP-2** for stronger captions; optional **Ollama** (`ollama pull llava:7b`) for richer food lists. |

Set `NUTRI_VISION=blip` to force the lighter model even on GPU if VRAM is tight.

## Setup

1. Python 3.10+ recommended.
2. Replace `nutriseeker/data/ifct2017_compositions.csv` with the full **IFCT 2017** composition file from NIN/IFCT (your notebook uses the same schema).
3. Optionally expand `nutriseeker/data/usda_foods_sample.csv` or import the USDA **FoodData Central** bulk CSV (offline) — **do not** use the FDC HTTP API if you require zero API keys.

```bash
cd nutriseeker
pip install -r requirements.txt
set PYTHONPATH=%CD%
uvicorn nutriseeker.app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

### Environment variables

| Variable | Meaning |
|----------|---------|
| `NUTRI_IFCT_CSV` | Path to IFCT CSV (default: package `data/ifct2017_compositions.csv`) |
| `NUTRI_USDA_CSV` | Path to local USDA-derived CSV |
| `NUTRI_VISION` | `auto` (default), `blip`, `blip2`, or `ollama` |
| `OLLAMA_HOST` | Default `http://127.0.0.1:11434` |
| `OLLAMA_VISION_MODEL` | Default `llava:7b` |

## Architecture

- **FastAPI** backend, static **SPA-style** frontend (`nutriseeker/app/static/`).
- **Vision**: BLIP-2 (CUDA) / BLIP-large (CPU); optional **Ollama LLaVA**.
- **Retrieval**: Multilingual **sentence-transformers** embeddings over IFCT food names + keyword map from your v1 notebook.
- **Portions**: Defaults (e.g. rice ~150 g) + optional `foodname: 200` grams in the text box.

## Legacy notebook

The first Colab notebook (`NutriSeeker(with_ifct).ipynb`) remains a reference; v2 is this application.
