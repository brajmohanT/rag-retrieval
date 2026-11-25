# Evidence Atlas: implementation plan

**Status (23 November 2026):** Steps 1–11 and 15 done; local demo complete for benchmark questions. Remaining: deployment, live custom questions, heatmap. See [Next steps](#next-steps) and [PROGRESS.md](PROGRESS.md).  
**Revised:** 22 November 2026, adopting API-only inference and an interactive client showcase.  

## Goal and audience

Build an interactive, publicly hosted multimodal RAG showcase for organisations evaluating RAG solutions. Visitors change the retrieval configuration and see, side by side, how text, visual, and hybrid retrieval perform on the same questions, then verify each answer against the original page evidence.

The showcase must answer the questions a client asks:

- Which retrieval approach suits *my* kind of documents?
- How accurate is it, and how do I know the answer is grounded?
- What does it cost and how fast is it?
- Can it run within my data boundary?

The first release uses one fixed **ViDoRe V3 HR** corpus. An always-live public demo is a requirement.

## Decisions

| Area | Decision |
| --- | --- |
| Inference | **APIs only.** No rented GPU, VM-hosted model, or local model inference. BM25 runs locally because it is CPU code, not a model. |
| Corpus | ViDoRe V3 HR: 14 documents, 1,110 pages, 318 English base questions. |
| Demo | Interactive: visitors change configuration and compare retrieval methods live. |
| Audience | Prospective client organisations; polish, cost, latency, and privacy are first-class concerns. |
| Build style | Step by step, explained as we go (see below). |

## How we build

The owner wants to understand how every part is built. For each step:

1. **Explain** what the step does and why, before writing code.
2. **Build** the smallest working piece.
3. **Show** a concrete result: command output, a ranking, a metric, a screenshot.
4. **Review** together, then record completed work in `PROGRESS.md`.

Do not start the next step until the current one is reviewed. Prefer plain, readable code over abstractions; introduce a library only when the step needs it.

## Stack

| Area | Choice |
| --- | --- |
| Language and dependencies | Python, `uv` |
| Data | Parquet files from the pinned dataset revision |
| Text baseline | BM25 (local) |
| Dense text retrieval | Qwen3-Embedding-8B via OpenRouter, one vector per page |
| Visual retrieval | ColQwen3 4B multi-vector via Superlinked (MaxSim); Voyage multimodal 3.5 single-vector via OpenRouter |
| Reranking | Cohere Rerank 5 Pro via OpenRouter on page text, top 50, optional per configuration |
| Fusion | Reciprocal rank fusion (RRF) |
| Answer generation | DeepSeek V4.1 Flash via OpenRouter on page text (page images tested: no gain); also grades answers |
| Vector search | Exact search with NumPy over cached vectors; no vector database at this scale |
| Backend | FastAPI |
| Frontend | React 19 + Vite + TypeScript (`web/`) |
| Tests | `pytest` |

Before adopting any API, verify its current model names, pricing, rate limits, output format, and data-retention terms.

## Steps

### 1. Confirm decisions — done

API-only inference, interactive client showcase, and step-by-step build are decided. Provider choices are made at the step that first needs them.

### 2. Create the project skeleton — done

```text
rag_01/
├── docs/
├── configs/
│   └── vidore_hr.yaml
├── src/evidence_atlas/
│   ├── data/          # loading, normalized records
│   ├── providers/     # API clients and response cache
│   ├── retrieval/     # bm25, dense, visual, fusion, rerank
│   ├── evaluation/    # metrics, partitions, reports
│   ├── generation/    # answers and citations
│   └── api/           # FastAPI backend
├── web/               # React frontend
├── scripts/
├── tests/
├── data/              # ignored by Git
├── artifacts/         # embeddings, rankings, reports; large files ignored
├── .env.example       # API key names only, never values
├── pyproject.toml
└── README.md
```

- Initialize Git and a `.gitignore` covering `data/`, large artifacts, and `.env`.
- Move the audit and viewer code from `scripts/inspect_query.py` into the package without changing behavior; keep its tests passing.

**Deliverable:** installable project, passing tests, first commit.

### 3. Audit and normalize the dataset — done

Audit: see `PROGRESS.md` and `artifacts/dataset_audit.json`. Typed records live in `evidence_atlas.data.records`, keyed by the dataset's own IDs:

```text
Document:   doc_id, file_name, url, doc_type, year, visual_types, license
Page:       page_id (= corpus_id), doc_id, page_number (zero-based), markdown
Query:      query_id, language, text, answer, query_types, query_format, content_type, source_type
Relevance:  query_id, page_id, grade, content_type, boxes
```

The dataset has no field linking a translation to its English base question. Matching on qrels, query type, format, and source type links 1,580 of 1,590 translations uniquely; the rest are ambiguous between two English questions. Handle this in step 4.

### 4. Lock the evaluation protocol — done

Frozen protocol: [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md). The original requirements follow.


Do this before tuning retrieval.

- Freeze development and held-out question IDs. If translations are used, keep them with their base question; English questions whose translations cannot be told apart go in the same partition.
- Use the full 1,110-page corpus as the candidate pool.
- Fix retrieval budgets: top 5 and top 10.
- Define graded-relevance handling: grade 2 is a complete answer; grade 1 is required evidence needing other pages.
- Define any-page, relevant-page, and complete-evidence recall separately.

Implement:

- Recall@5, Recall@10, MRR@10, nDCG@10, evidence-set completeness.
- **Breakdowns** by the dataset's `query_types` and `content_type` (tables, charts, text, and so on). This tells a client which method suits their documents.
- **Bootstrap confidence intervals**, so small differences on 318 questions are not overclaimed.
- **Cost and latency** fields in every run record.

Test metrics against small hand-calculated examples. Describe results as our evaluation on a published test split, not an official benchmark score.

**Deliverable:** tested evaluator and frozen partitions.

### 5. Build the BM25 baseline — done

Own BM25 implementation (`retrieval/bm25.py`, k1 1.2, b 0.75, Snowball stemming) over the supplied Markdown, with per-term score explanations for the demo. Results: `artifacts/runs/bm25/report.md`; summary in `PROGRESS.md`.

Every method saves runs in one format (`retrieval/runs.py`):

```text
artifacts/runs/<name>/
    run.json        method, settings, dataset revision, index time, query latency p50/p95, cost
    rankings.jsonl  {"query_id", "pages", "scores"} per question, top 100, best first
    metrics.json    written by atlas-eval
    report.md       written by atlas-eval
```

### 6. Build the API provider layer — done

Code in `src/evidence_atlas/providers/`; check with `uv run atlas-smoke`. Original requirements follow.


A thin client per provider plus a shared response cache.

- Cache key: provider, model, model version or date, input hash, parameters.
- Store vectors on disk; never pay twice for the same input.
- Record per-call latency, token or image counts, and estimated cost.
- Retry with backoff; respect rate limits.
- Read keys from `.env`; never log or commit them.

**Deliverable:** one cached test call per provider, with cost recorded.

### 7. Add dense text retrieval — done

Qwen3-Embedding-8B via OpenRouter, one vector per page (`atlas-dense`); results in `PROGRESS.md`. Original requirements follow.


1. Choose one text embedding API.
2. Embed page Markdown (or page-linked chunks with a declared page-score aggregation rule).
3. Run the same evaluation.

**Deliverable:** BM25 versus dense-text comparison, including cost per 1,000 pages and queries.

### 8. Add visual retrieval — done

Voyage multimodal 3.5 (single-vector) and ColQwen3 4B (multi-vector, MaxSim) over page images (`atlas-visual`); results in `PROGRESS.md`. The match heatmap (item 4 below) moves to the frontend step, where patch positions are mapped onto the page image. Original requirements follow.


1. Validate the Superlinked ColQwen3 API on a handful of pages and queries.
2. Embed all page images once; cache the multi-vectors.
3. Implement late-interaction (MaxSim) scoring locally with NumPy.
4. Keep token-to-patch similarities so the demo can draw a **match heatmap** over the page.
5. Add one single-vector multimodal embedding API as a cheaper comparison.
6. Evaluate both with the same protocol.

Record image resolution, model and date, vector precision, embedding cost, and storage.

**Acceptance check:** a small end-to-end run works before embedding the full corpus.

**Deliverable:** text-versus-visual comparison.

### 9. Add fusion and reranking — done

RRF fusion (`atlas-fusion`) and reranking (`atlas-rerank`); final comparison table in `PROGRESS.md`. Original requirements follow.


- Fuse text and visual rankings with RRF; expose the text/visual weight as a setting.
- Add an optional reranking API over the fused top candidates.
- Choose defaults on development questions only; freeze before held-out evaluation.

| Method | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | p50/p95 latency | Cost / 1k queries | Index cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM25 | | | | | | | |
| Dense text | | | | | | | |
| Visual (multi-vector) | | | | | | | |
| Visual (single-vector) | | | | | | | |
| Hybrid | | | | | | | |
| Hybrid + rerank | | | | | | | |

**Deliverable:** the core result, including where visual or hybrid retrieval loses.

### 10. Precompute the configuration grid — done

`atlas-grid` writes `artifacts/demo/grid.json`; details in `PROGRESS.md`. Original requirements follow.


So the demo is instant and free for benchmark questions:

- Define the settings visitors can change: retriever, top-K, fusion weight (a few fixed values), reranker on/off.
- Precompute rankings and metrics for every question under every configuration.
- Store them in a compact results file the backend loads at startup.

**Deliverable:** results store with per-configuration scoreboards.

### 11. Add answer generation and citations — done

DeepSeek V4.1 Flash on page text (`atlas-answers`); results in `PROGRESS.md`; shown in the demo. Original requirements follow.


Use one fixed Claude model across retrieval methods.

- Pass retrieved page images and, where configured, their text; fix page and token budgets.
- Require citations to valid page IDs; allow abstention.
- Log prompts, pages, settings, answers, latency, and cost.
- Evaluate answer correctness (model-graded against reference answers, spot-checked by hand) and citation faithfulness (does the cited page support the claim?).
- Precompute answers for benchmark questions under the main configurations.

Keep gold labels, boxes, and reference answers out of the inference pipeline; they are for evaluation and post-answer display only.

**Deliverable:** cited answers users can verify against original pages.

### 12. Run the answer-reading experiment — partly answered

Text vs page images vs both, on 107 dev questions with DeepSeek: no measurable difference (see `PROGRESS.md`). The higher-resolution and region-OCR conditions below were not run. Original requirements follow.


Keep retrieved pages and the answer model fixed:

| Condition | Input |
| --- | --- |
| A | Standard-resolution page images |
| B | Higher-resolution versions of the same pages |
| C | Higher-resolution images plus query-relevant region OCR (regions chosen without ground-truth boxes) |

Measure answer quality, citation support, latency, image-token usage, and cost.

**Deliverable:** evidence separating retrieval failures from page-reading failures.

### 13. Build the backend — benchmark questions done

`api/app.py` serves the grid, questions, pages, and images (`atlas-serve`). Live custom questions, rate limits, and spend cap remain. Original requirements follow.


FastAPI service that:

- Serves precomputed rankings, answers, and scoreboards for benchmark questions.
- Runs custom questions live through the provider APIs, with per-visitor rate limits, a daily spend cap, and a clear message when the cap is reached.
- Serves page images, evidence boxes, and heatmaps.

**Deliverable:** documented, tested API.

### 14. Build the interactive frontend — done except heatmap

`web/`: question list, lanes, lane editor, page viewer with evidence boxes, scoreboard. Heatmap, cited answers, and the curated gallery remain. Original requirements follow.


The showcase experience:

- **Configuration panel:** retriever, top-K, fusion weight, reranker, answer input (image / text / both).
- **Side-by-side lanes:** BM25 | Dense | Visual | Hybrid, page thumbnails with ✅/❌ relevance marks in evaluation mode.
- **Match heatmap** showing which page regions matched the question.
- **Live scoreboard:** metrics, cost per 1,000 queries, and latency update as settings change.
- **Cited answer** with click-to-page citations and highlighted evidence.
- **Curated gallery:** about six labeled cases, including text-fails/visual-wins, hybrid-wins, and at least one honest failure.
- Works on mobile.

**Deliverable:** usable demo against the local backend.

### 15. Add client-facing pages — done

Findings & guide, cost calculator, and privacy & deployment pages in the demo. Original requirements follow.


- **Decision guide:** document type → recommended retrieval setup, backed by the measured breakdowns.
- **Cost calculator:** page count and monthly queries → estimated indexing and query cost.
- **Deployment and privacy note:** this demo uses public APIs; client deployments can run in a private cloud or on-premises.

**Deliverable:** pages a prospective client can act on.

### 16. Deploy and package

- Run the frozen held-out evaluation.
- Audit 30–50 stress questions; label failures (missing page, incomplete evidence, wrong rank, unreadable visual evidence, unsupported citation, generator error).
- Write the results report with denominators, confidence intervals, limitations, and reproducibility instructions.
- Deploy backend and frontend; set monitoring and spend alerts.
- Publish page assets only where document licenses permit.
- Record a 30–45 second demo including one failure.

**Deliverable:** live public demo, reproducible repository, results report.

## Next steps

In order. Steps 1–2 make the demo shareable; it costs nothing per visitor because everything is precomputed.

### 1. Deploy the benchmark demo publicly (step 16)

- Choose hosting for the FastAPI backend and built frontend; serve the 185 MB of page images from object storage or a CDN.
- Add a footer crediting the source reports (CC BY 4.0, European Commission) and linking to the dataset.
- Make the build reproducible from a clean checkout: which artifacts are rebuilt (grid, answers, page images) versus shipped.
- Add uptime monitoring and a simple health check.
- Check in a real browser: phone widths (390 px), the page viewer, keyboard use.

### 2. Package the results

- Write `docs/RESULTS.md`: the final comparison table, answer results, method, denominators, confidence intervals, limitations, and reproduction commands.
- Record a 30–45 second demo walkthrough of the showcase gallery, including the honest failure.

### 3. Live custom questions (rest of step 13)

- Use the fast setup (BM25 + Voyage + Cohere rerank, about 1.9 s retrieval) plus DeepSeek for answers.
- Per-visitor rate limits, a daily spend cap with a clear "limit reached" message, and input length limits.
- Decide what is logged: questions typed by visitors are third-party data.
- Mark live results as unevaluated (no relevance labels exist for new questions).

### 4. Match heatmap (rest of step 14)

- Show which page regions ColQwen3 matched. First establish how the 747 `:compact` vectors map to image patches; if that mapping is not documented or recoverable, drop the feature.

### Known limitations to keep visible

- One corpus; each comparison changes both input type and model.
- Answers are graded by the answering model's family (17 of 20 agreed with a hand check).
- Precomputed answers exist for the 7 preset setups only.
- The dense text API took 3.3 s per question, which rules it out for live use.

## Deferred work

- "Try your own PDF" sandbox with page and spend limits — strongest sales hook; add after the core demo works.
- Additional corpora, including ViDoRe V3 Computer Science.
- M3DocVQA or a bounded VL-DocIR evaluation.
- Fine-tuning and vector database infrastructure.
