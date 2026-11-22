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
- Initialized Git; nothing committed yet.
- 8 tests pass (`uv run pytest`).
- Not yet done: normalized `Page`/`Query`/`Relevance` records from step 3.
