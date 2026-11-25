# AGENTS.md

Setup guide for a coding agent (or a person) running this project, "Retrieval in RAG", on a fresh machine. The Python package is `evidence_atlas` and the commands are `atlas-*`; do not rename them.

The demo needs **no API keys and makes no paid calls**. All retrieval results and answers are precomputed and tracked in Git. What is not in Git is the dataset (downloaded from Hugging Face) and the page images (generated locally from the dataset).

Run every command from the repository root unless a step says otherwise.

## Prerequisites

| Need | Version / amount | Check |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | 0.9 or newer (build backend is `uv_build>=0.9`) | `uv --version` |
| Python | 3.12 (pinned by `.python-version`; uv downloads it if missing) | `uv run python --version` → `Python 3.12.x` |
| Node.js + npm | Node 20 or 22+ (Vite 6.4 needs `^18.0.0 \|\| ^20.0.0 \|\| >=22.0.0`; some ESLint deps need ≥18.18) | `node --version` |
| Network | Hugging Face (dataset), PyPI, npm registry | |
| Disk | about 1.2 GB free | dataset 496 MB, page images 185 MB, `.venv` 190 MB, `web/node_modules` 91 MB |

No Hugging Face account or token is needed; the dataset is public and not gated. Without `HF_TOKEN` the download prints a rate-limit warning, which is harmless.

## Steps

### 1. Install Python dependencies

```sh
uv sync
```

Produces `.venv/` with the project installed in editable mode, plus pytest.

Check:

```sh
uv run python -c "import evidence_atlas, fastapi; print('ok')"
```

Expect `ok`.

### 2. Download the dataset (≈496 MB)

```sh
uvx --from huggingface_hub hf download vidore/vidore_v3_hr \
    --repo-type dataset \
    --revision 0cdf0979f2c5a0fd3e335e6373b9da48a9fe3bc3 \
    --local-dir data/vidore_v3_hr
```

The revision is the one pinned in `configs/vidore_hr.yaml` (`dataset.revision`); all precomputed results were made against it. `uvx` runs the Hugging Face CLI without adding it to the project. Add `--dry-run` first to see the file list without downloading.

Produces `data/vidore_v3_hr/` with 22 files: `corpus/`, `documents_metadata/`, `queries/`, `qrels/` (one Parquet file each), `pdfs/` (14 PDFs plus 2 metadata files), `README.md`, `.gitattributes`, and a `.cache/` folder used by the CLI.

Check:

```sh
ls data/vidore_v3_hr/*/*.parquet | wc -l      # expect 4
ls data/vidore_v3_hr/pdfs/*.pdf | wc -l       # expect 14
uv run pytest -q                              # expect all tests to pass (API tests stop being skipped once data exists)
```

The corpus Parquet file is 442,091,664 bytes.

### 3. Export page images (≈2.5 minutes, no network)

```sh
uv run atlas-export-pages
```

Reads page PNGs from `data/vidore_v3_hr/corpus/*.parquet` and writes a 320 px thumbnail and an 1100 px image (WebP) per page, plus `sizes.json`. No API calls, no keys (it only uses Pillow and PyArrow).

Produces `artifacts/demo/pages/` with 2,221 files (2 × 1,110 WebP + `sizes.json`), about 185 MB. The last line printed is `Wrote 2220 images to …/artifacts/demo/pages (185 MB)`.

Check:

```sh
ls artifacts/demo/pages/*.webp | wc -l        # expect 2220
git status --short artifacts                  # expect no output (sizes.json is regenerated identical; images are ignored)
```

### 4. Build the frontend

```sh
cd web && npm ci && npm run build && cd ..
```

Produces `web/dist/` (≈550 KB: `index.html` and `assets/`). `npm ci` may warn that the `fsevents` install script was not run; that is harmless.

Check:

```sh
ls web/dist/index.html
```

### 5. Run the demo server

```sh
uv run atlas-serve
```

Serves the API and the built frontend at http://127.0.0.1:8000 (host and port are fixed in `src/evidence_atlas/api/app.py`). Stop with Ctrl+C.

Check, from another shell:

```sh
curl -s http://127.0.0.1:8000/api/meta | python3 -c "import json,sys; m=json.load(sys.stdin); print(m['questions'], m['configs'], m['pages'])"
# expect: 318 66 1110
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8000/page-images/403-thumb.webp
# expect: 200 image/webp
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
# expect: 200
```

Then open http://127.0.0.1:8000 in a browser.

### 6. Optional: static export

```sh
uv run atlas-export-static
```

Builds a static copy of the demo into `site/` that any static host can serve (no Python server needed). `site/` is ignored by Git. Needs steps 2–4 done first.

## What is in Git and what is not

Tracked precomputed files (all the demo server reads besides the dataset and images):

| File | Size | Made by |
| --- | ---: | --- |
| `artifacts/demo/grid.json` | 3.8 MB | `atlas-grid` (66 setups × 318 questions: rankings, metrics, cost, latency) |
| `artifacts/answers/answers.json` | 1.6 MB | `atlas-answers` (cited, graded answers for the 7 presets) |
| `artifacts/demo/pages/sizes.json` | 23 KB | `atlas-export-pages` (original pixel size of each page, for evidence boxes) |
| `artifacts/runs/{bm25,dense-qwen3-embedding-8b,visual-voyage-multimodal-3.5,visual-colqwen3-4b}/run.json` | <1 KB each | the retriever runs (settings; vector sizes shown in the demo) |

Ignored and local only: `data/`, the rest of `artifacts/` (API response cache `artifacts/cache/` ≈1.2 GB, `api_calls.jsonl`, logs, `inspection/`, page images, run rankings), `web/node_modules/`, `web/dist/`, `site/`, `.env`.

## Common failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| `FileNotFoundError: …/data/vidore_v3_hr/…` or `ValueError: No Parquet files in …` when starting the server or exporting pages | Dataset missing or downloaded to another folder | Run step 2 exactly; the path must be `data/vidore_v3_hr` relative to the repo root |
| `FileNotFoundError: …/artifacts/demo/grid.json` | Checkout without the tracked artifacts (e.g. a sparse or partial clone) | `git checkout -- artifacts` or re-clone |
| Demo loads but page images are broken (404 on `/page-images/…`) | Step 3 not run, or run after the server started | Run `uv run atlas-export-pages`, then restart `atlas-serve` (the images folder is mounted only if it exists at startup) |
| `http://127.0.0.1:8000/` returns `{"detail":"Not Found"}` but `/api/meta` works | Frontend not built, or built after the server started | Run step 4, then restart `atlas-serve` |
| `[Errno 48] Address already in use` / `[Errno 98] …` | Something else is on port 8000 | Stop it, or run on another port: `uv run uvicorn --factory evidence_atlas.api.app:create_app --host 127.0.0.1 --port 8765` |
| `npm ci` fails with engine errors or `SyntaxError` in Vite | Node too old | Use Node 20 or 22+ |
| `hf download` returns 429 or is slow | Anonymous rate limit | Wait and rerun (it resumes), or set `HF_TOKEN` to any Hugging Face read token |
| `uv sync` cannot find Python 3.12 | uv's managed Python downloads disabled | `uv python install 3.12` |
| `KeyError` / unexpected numbers after downloading a different dataset revision | Results are tied to revision `0cdf0979…` | Re-download with `--revision 0cdf0979f2c5a0fd3e335e6373b9da48a9fe3bc3` |

## Tests

```sh
uv run pytest
```

Runs offline. `tests/test_api.py` is skipped when `artifacts/demo/grid.json` or the dataset is missing; after step 2 it runs against the real data.

## Re-running the pipeline (needs API keys, costs money)

Not needed for the demo. Only do this to change models or regenerate results. Running these commands **overwrites the tracked files** in `artifacts/` and spends money on the provider accounts.

```sh
cp .env.example .env    # then fill in the keys; .env is ignored by Git
```

| `.env` key | Provider |
| --- | --- |
| `OPEN_ROUTER_KEY` | [OpenRouter](https://openrouter.ai/) |
| `SUPERLINKED_API_KEY` | [Superlinked](https://superlinked.com/) |

API responses are cached in `artifacts/cache/` (not in Git), so a fresh clone pays for every call once; reruns on the same machine are served from the cache. Every call is logged to `artifacts/api_calls.jsonl`.

| Command | Paid API calls | Key(s) | Writes |
| --- | --- | --- | --- |
| `atlas-inspect`, `atlas-bm25`, `atlas-fusion`, `atlas-eval`, `atlas-export-pages`, `atlas-serve`, `atlas-export-static` | none | none | |
| `atlas-dense` | Qwen3-Embedding-8B embeddings via OpenRouter | `OPEN_ROUTER_KEY` | `artifacts/runs/dense-qwen3-embedding-8b/` |
| `atlas-visual` (`voyage`) | Voyage multimodal-3.5 embeddings via OpenRouter (≈$1.33 for the corpus) | `OPEN_ROUTER_KEY` | `artifacts/runs/visual-voyage-multimodal-3.5/` |
| `atlas-visual` (`colqwen3`) | ColQwen3-4B embeddings via Superlinked (≈$0.24) | `SUPERLINKED_API_KEY` | `artifacts/runs/visual-colqwen3-4b/` |
| `atlas-rerank cohere` / `qwen` | Cohere rerank-5-pro / Qwen3 reranker via OpenRouter | `OPEN_ROUTER_KEY` | `artifacts/runs/rerank-*` |
| `atlas-rerank vl` | Qwen3-VL reranker via Superlinked | `SUPERLINKED_API_KEY` | `artifacts/runs/rerank-*` |
| `atlas-grid` | Cohere rerank-5-pro via OpenRouter for every reranked setup; `--dry-run` estimates cost and spends nothing | `OPEN_ROUTER_KEY` | `artifacts/demo/grid.json` |
| `atlas-answers` | DeepSeek (`deepseek/deepseek-v4.1-flash-1017`) via OpenRouter, to answer and to grade | `OPEN_ROUTER_KEY` | `artifacts/answers/answers.json` |
| `atlas-smoke` | one small call to each provider (well under $0.01) | both | |

Order for a full rebuild of the demo files: `atlas-bm25` → `atlas-dense` → `atlas-visual` (runs `voyage` and `colqwen3`; pass one name to run only that one) → `atlas-grid` → `atlas-answers`. `atlas-grid` reads the `rankings.jsonl` of the four retriever runs, which are not in Git, so those runs must be redone first. `atlas-fusion` and `atlas-rerank` produce the standalone evaluation runs (fusion tuning on dev, reranker comparison); the grid does its own fusion and reranking. Costs per run are recorded in each `artifacts/runs/*/run.json` (`index_cost_usd`, `query_cost_per_1k_usd`).
