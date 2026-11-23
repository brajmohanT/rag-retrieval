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
