# Retrieval in RAG

Keyword, dense text, visual and hybrid retrieval compared on the same 318 questions over [ViDoRe V3 HR](https://huggingface.co/datasets/vidore/vidore_v3_hr) (1,110 pages from 14 EU labour-market reports), with cited answers and the page evidence behind each one.

Every retriever runs through a hosted API: Qwen3-Embedding-8B (dense text), Voyage multimodal-3.5 and ColQwen3-4B (visual), Cohere rerank-5-pro (reranking), all via OpenRouter or Superlinked; answers come from DeepSeek. The 66 setups (any subset of the four first-stage retrievers, RRF fusion, three visual weights, with or without reranking) are precomputed, so the demo itself makes no API calls and needs no keys.

## Results

Held-out partition (211 of 318 questions; fusion and reranking settings were tuned on the other 107). Answer accuracy is the share of answers graded fully correct against the dataset's reference answer, with the top 5 pages given to DeepSeek as text.

| Setup | nDCG@10 | Recall@5 | Answer accuracy |
| --- | ---: | ---: | ---: |
| BM25 | 0.492 | 0.418 | 38.9% |
| Qwen3-Embedding-8B (text) | 0.520 | 0.461 | 46.0% |
| Voyage multimodal-3.5 (visual, single vector) | 0.592 | 0.527 | 50.2% |
| ColQwen3-4B (visual, multi-vector) | 0.622 | 0.529 | 49.8% |
| RRF (all 4) | 0.652 | 0.552 | 53.6% |
| RRF (BM25, Voyage) → Cohere rerank | 0.733 | 0.652 | 53.6% |
| RRF (all 4) → Cohere rerank | 0.731 | 0.646 | 54.5% |

The best possible Recall@5 on this partition is 0.845, because some questions have more than five judged pages. Bootstrap confidence intervals, per-content-type scores, cost and latency for all 66 setups are in the demo (`/api/configs`).

## Quick start

No API keys needed. Requires [uv](https://docs.astral.sh/uv/), Node.js 20 or 22+, and about 1.2 GB of disk. [AGENTS.md](AGENTS.md) has the full steps with checks and fixes.

```sh
uv sync
uvx --from huggingface_hub hf download vidore/vidore_v3_hr --repo-type dataset \
    --revision 0cdf0979f2c5a0fd3e335e6373b9da48a9fe3bc3 --local-dir data/vidore_v3_hr
uv run atlas-export-pages                      # page images, ~2.5 min
(cd web && npm ci && npm run build)
uv run atlas-serve                             # http://127.0.0.1:8000
```

The precomputed results the demo reads (`artifacts/demo/grid.json`, `artifacts/answers/answers.json`, page sizes and run settings) are in Git. `uv run atlas-export-static` builds a static copy of the demo into `site/` that any static host can serve.

## Commands

The Python package is `evidence_atlas`; commands keep the `atlas-` prefix.

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
uv run atlas-serve                   # demo server on http://127.0.0.1:8000
uv run atlas-export-static           # static copy of the demo in site/
```

Which commands call paid APIs, and which keys they need, is listed in [AGENTS.md](AGENTS.md#re-running-the-pipeline-needs-api-keys-costs-money).

For frontend development, run `uv run atlas-serve` and `cd web && npm run dev` (Vite proxies `/api` to the backend).

## Layout

```text
configs/            dataset revision, dev/held-out split, showcase questions
src/evidence_atlas/ project code
  config.py         loads configs/*.yaml
  data/             dataset records, audit, evidence viewer
  evaluation/       partitions, metrics, run reports
  retrieval/        retrievers and the shared run format
  providers/        API clients, response cache, call log
  demo/             precomputed configuration grid and page images
  generation/       cited answers and grading
  api/              demo backend (FastAPI)
web/                demo frontend (React + Vite)
tests/
docs/               evaluation protocol, plan, progress, research notes
artifacts/          generated outputs; only the files the demo needs are in Git
data/               downloaded dataset (not in Git)
```

Further reading: [docs/EVALUATION_PROTOCOL.md](docs/EVALUATION_PROTOCOL.md), [docs/PROGRESS.md](docs/PROGRESS.md), [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

## Data and license

Dataset: [ViDoRe V3 HR](https://huggingface.co/datasets/vidore/vidore_v3_hr) by the ViDoRe team, pinned to revision `0cdf0979f2c5a0fd3e335e6373b9da48a9fe3bc3`. Its annotations are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the source reports are © European Union, also CC BY 4.0 (per the dataset's `documents_metadata`). The demo shows page images and text from these reports with a link to each source document.

Code: MIT, see [LICENSE](LICENSE).
