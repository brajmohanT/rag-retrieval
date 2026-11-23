# Evidence Atlas

An interactive multimodal RAG showcase. It compares text, visual, and hybrid retrieval on the same questions over the [ViDoRe V3 HR](https://huggingface.co/datasets/vidore/vidore_v3_hr) corpus (14 EU labour-market reports, 1,110 pages), then shows the original page evidence behind each answer. All models run through hosted APIs.

Status: early build. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                      # create .venv and install the project
cp .env.example .env         # add API keys when a step needs them
```

The dataset (~495 MB) lives in `data/vidore_v3_hr/` and is not in Git.

## Commands

```sh
uv run pytest                        # run tests
uv run atlas-inspect --query-id 0    # audit the dataset; write an evidence viewer to artifacts/inspection/0/
uv run atlas-bm25                    # run BM25 on all questions; report in artifacts/runs/bm25/
uv run atlas-dense                   # dense text retrieval via API (cached after first run)
uv run atlas-visual                  # visual retrieval from page images: voyage, colqwen3, or both
uv run atlas-fusion                  # tune rank fusion on dev, evaluate on held-out (no API cost)
uv run atlas-rerank cohere           # rerank the fusion shortlist on dev; --partition all for the final run
uv run atlas-grid                    # precompute all 66 demo configurations (--dry-run to estimate cost)
uv run atlas-export-pages            # page thumbnails and large images for the demo
uv run atlas-answers                 # cited answers for the demo presets (--mode text|image|both)
uv run atlas-eval artifacts/runs/X   # (re)evaluate any saved run
uv run atlas-smoke                   # one cached call to each API provider (needs .env keys)
```

## Demo

```sh
(cd web && npm install && npm run build)   # build the frontend once
uv run atlas-serve                         # http://127.0.0.1:8000
```

For frontend development, run `uv run atlas-serve` and `cd web && npm run dev` (Vite proxies `/api` to the backend).

## Layout

```text
configs/            dataset paths and pinned revision
src/evidence_atlas/ project code
  config.py         loads configs/*.yaml
  data/             dataset records, audit, evidence viewer
  evaluation/       partitions, metrics, run reports
  retrieval/        retrievers and the shared run format
  providers/        API clients, response cache, call log
  demo/             precomputed configuration grid and page images for the demo
  generation/       cited answers and grading
  api/              demo backend (FastAPI)
web/                demo frontend (React + Vite)
tests/
docs/               plan, progress, research, discussion notes
data/, artifacts/   local only (ignored by Git)
```
