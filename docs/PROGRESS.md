# Progress

Completed work only. Planned work stays in `IMPLEMENTATION_PLAN.md`.

## Dataset download

- Downloaded the full `vidore/vidore_v3_hr` snapshot to `data/vidore_v3_hr/`, including 14 PDFs.
- Pinned revision: `0cdf0979f2c5a0fd3e335e6373b9da48a9fe3bc3`.
- Verified all 22 downloaded files against expected sizes: about 495.5 MB total.
- Saved `data/vidore_v3_hr/download_manifest.json`.
- Added downloaded data and generated artifacts to `.gitignore`.

## Structural audit and evidence viewer

- Implemented `scripts/inspect_query.py` and `scripts/inspection.css`.
- Verified 1,110 corpus pages, 1,908 query rows (318 English), 10,386 qrels, and 14 document metadata records.
- Found no broken joins or structural errors. Decoded all 1,110 images and opened all 14 PDFs.
- Recorded warnings: 12 pages with empty Markdown, 18 qrel rows without boxes, and 12 zero-width box occurrences.
- Saved the audit to `artifacts/dataset_audit.json`.
- Generated `artifacts/inspection/0/index.html`: question, reference answer, six labeled pages, evidence overlays, Markdown, and PDF links.
- Opened the viewer in the browser and checked desktop/mobile rendering.
- Added seven passing tests in `tests/test_inspect_query.py`.

## Query 0 review

- Compared all six labeled page images with their Markdown.
- Verified the decisive paragraph on corpus page 485 against PDF page 61. It supports the reference answer, and the Markdown retains its numbers.
- Recorded suspect relevance labels and the apparent grade-1/complete-answer inconsistency in `artifacts/inspection/0/review.md`.
- Rechecked grading against the official dataset card and paper: 2 means complete answer; 1 means required evidence needing additional information; 0 means irrelevant.
- Preserved the source data and official qrels unchanged. Findings cover one query, not the whole corpus.

## Research and planning

- Saved the implementation plan and short project discussion notes.
- Verified Superlinked's documented serverless ColQwen3 4B `:compact` API supports raw multi-vector output for text queries and page images.
- No authenticated Superlinked inference, embedding generation, retrieval indexing, or ranking evaluation has run.

## Project skeleton (step 2)

- Created an installable `uv` package: `pyproject.toml`, `uv.lock`, Python 3.12, console command `atlas-inspect`.
- Moved `scripts/inspect_query.py` and its CSS into `src/evidence_atlas/data/`; behavior unchanged. Dataset audit output is byte-identical; the viewer differs only in its stylesheet path.
- Added `configs/vidore_hr.yaml` (dataset repo, pinned revision, paths) and `evidence_atlas.config.load_config`.
- Added `.env.example`, `README.md`, and a `.gitignore` covering data, artifacts, `.env`, caches, and local agent tooling.
- Initialized Git (local identity only) and made the first commit.
- 8 tests pass (`uv run pytest`).
- Not yet done: normalized `Page`/`Query`/`Relevance` records from step 3.

## Typed dataset records

- Added `evidence_atlas.data.records`: `Document`, `Page`, `Query`, `Relevance`, `Box`, and `load_dataset` (English by default; loads in about 0.1 s without page images).
- The audit now reuses the same `load_rows`.
- Verified on real data: 14 documents, 1,110 pages, 318 English questions, every qrel resolves to a page.
- Findings: judged pages per English question range from 1 to 30 (median 3); 125 of 318 have no single complete-answer (grade 2) page. No field links translations to base questions; label matching links 1,580 of 1,590 uniquely.
- 12 tests pass.

## Evaluation protocol (step 4)

- Froze 107 dev and 211 held-out English questions, stratified by question type, in `configs/vidore_hr_partitions.json`; regeneration is refused.
- Implemented Hit@k, Recall@k, Complete@k, MRR@10, nDCG@10 (`evaluation/metrics.py`), with bootstrap intervals, type breakdowns, and paired comparisons (`evaluation/evaluate.py`).
- Hand-calculated tests; 21 tests pass.
- Sanity check on held-out: a perfect ranking scores nDCG@10 1.000; random scores 0.003. Perfect-ranking ceilings: Recall@5 0.845, Complete@5 0.782.
- Protocol written to `docs/EVALUATION_PROTOCOL.md`. Run format with cost and latency is deferred to step 5.

## BM25 baseline (step 5)

- Implemented BM25 (`retrieval/bm25.py`) with per-term explanations, the shared run format (`retrieval/runs.py`), run reports (`evaluation/report.py`), and commands `atlas-bm25` and `atlas-eval`.
- Held-out (n=211): nDCG@10 0.492 [0.447–0.534], MRR@10 0.604, Hit@5 0.782, Recall@5 0.418 (ceiling 0.845), Complete@5 0.441 (ceiling 0.782).
- Weakest on tables: held-out Table nDCG@10 0.312, Complete@5 0.261 (ceiling 0.667).
- Index build 2.7 s; query p50 0.6 ms, p95 0.9 ms; cost $0.
- 14 of 107 dev questions have no judged page in the top 10. Example: Q208 (France's 2020 national employment rate) fails because the answer table writes "FR" and "Nat.", never "France" or "national".
- 27 tests pass.

## API provider layer (step 6)

- Added `providers/`: `http.py` (keys from `.env`, retries with backoff, call log at `artifacts/api_calls.jsonl`), `cache.py` (per-item disk cache keyed by provider, model, settings, and input hash), `superlinked.py` (ColQwen3 multi-vector encode), `openrouter.py` (embeddings and chat), and the `atlas-smoke` command.
- Shared `load_page_images` in `data/records.py`; the evidence viewer now uses it.
- Smoke test (query 0, page 485): ColQwen3 returns 747 × 320 vectors per page and one 320-d vector per query token; Voyage multimodal 3.5 returns 1,024-d vectors; DeepSeek V4.1 Flash chat works. First run cost $0.0029; the second run made no calls.
- Observed: Superlinked took 16 s for 2 pages on first use, so full-corpus encoding needs concurrent requests. ColQwen3 vectors take about 1 MB per page in float32.
- 34 tests pass, with fake HTTP responses (no network or keys).

## Dense text retrieval (step 7)

- Added `retrieval/dense.py` (exact cosine search) and `atlas-dense`: Qwen3-Embedding-8B via OpenRouter, one vector per page's Markdown, instruction-prefixed questions. The 12 pages without text are not embedded.
- Cost: $0.0114 to embed 1,098 pages; about $0.0005 per 1,000 questions. Question encoding p50 3.3 s through the API (search 0.3 ms); too slow for live custom questions as is.
- Held-out nDCG@10 0.520 [0.478–0.560] vs BM25 0.492. Overall difference +0.028, 95% CI [−0.017, +0.071]: not significant.
- Tables: nDCG@10 0.536 vs 0.312, difference +0.224 [+0.127, +0.318], significant. Numerical questions: +0.119 [+0.012, +0.221], significant.
- The methods are complementary: dense better on 88 held-out questions, BM25 on 91. Taking the better of the two per question would give nDCG@10 0.623, the headroom for fusion.
- Dev example Q208 (France table): judged page 403 ranks 3rd with dense; BM25 never retrieved it.
- 39 tests pass.

## Visual retrieval (step 8)

- Added `retrieval/late_interaction.py` (exact MaxSim over all page vectors in one matrix), `retrieval/api_run.py` (shared cost, latency, save, and report for API runs; `run_dense.py` refactored onto it with byte-identical rankings), parallel requests in both clients, and `atlas-visual`.
- Page images sent as the original PNGs (mostly 1654 × 2339). ColQwen3 `:compact` returns exactly 747 × 320 vectors for every page.
- Held-out (n=211) nDCG@10: BM25 0.492, dense text 0.520, Voyage 0.592, ColQwen3 0.622. MRR@10: 0.604, 0.637, 0.709, 0.751. Complete@5: 0.441, 0.469, 0.531, 0.526 (ceiling 0.782).
- Paired nDCG@10 differences, all significant: ColQwen3 − BM25 +0.131 [+0.091, +0.172]; ColQwen3 − dense +0.103 [+0.070, +0.133]; Voyage − dense +0.073 [+0.044, +0.102]; ColQwen3 − Voyage +0.030 [+0.001, +0.058] (borderline).
- Visual models lead on every content type with n ≥ 23, including text-only pages. ColQwen3 − dense on charts +0.061 [+0.010, +0.109], on tables +0.059 [+0.002, +0.119].
- Methods remain complementary: per question, ColQwen3 is (jointly) best on 101 held-out questions, Voyage 87, BM25 62, dense 50. Best-of-four per question: nDCG@10 0.721.
- Cost: index Voyage $1.33, ColQwen3 $0.22; queries per 1,000 Voyage $0.0026, ColQwen3 $0.067. Query API latency p50: Voyage 565 ms, ColQwen3 1,240 ms; ColQwen3 search 23 ms.
- ColQwen3 page vectors occupy about 1.06 GB in float32.
- No held-out or dev question has a judged page among the 12 text-less pages, so that visual advantage is untested here.
- Caveat: each comparison changes both the input (text vs image) and the model, so gains cannot be attributed to the image input alone.
- 43 tests pass.

## Fusion (step 9, part 1)

- Added `retrieval/fusion.py` (reciprocal rank fusion) and `atlas-fusion`: tries every combination of two or more runs with equal weights and k ∈ {10, 30, 60} (33 settings), chooses by dev nDCG@10 only, then evaluates once on held-out. All settings tried are saved in `artifacts/runs/fusion/tuning.json`.
- Chosen on dev: all four methods, k = 10 (dev nDCG@10 0.617 vs 0.594 for ColQwen3 alone).
- Held-out nDCG@10 0.652 [0.613–0.690] vs ColQwen3 0.622; paired difference +0.029 [+0.007, +0.052], significant. MRR@10, Complete@5, and Recall@5 gains are positive but not significant.
- Shortlist quality on held-out (fusion): Recall@20 0.802, Recall@50 0.893; Complete@20 0.701, Complete@50 0.768.
- Fusion cost and latency: the sum of its members' costs; latency is the slowest member's (dense text, 3.3 s via API).
- 46 tests pass.
