# Evaluation protocol

**Frozen:** 22 November 2026, before any retriever was built.  
**Code:** `src/evidence_atlas/evaluation/`. **Tests:** `tests/test_evaluation.py`.

## Questions

- 318 English base questions from ViDoRe V3 HR at the pinned revision. Translations are not evaluated.
- Split once into **dev** (107) and **held-out** (211), stratified by question-type combination: seed 2026, dev fraction 0.33. IDs are in `configs/vidore_hr_partitions.json`, which the code refuses to overwrite.
- Tune every setting (fusion weight, reranker depth, defaults) on dev only. Report final numbers on held-out only, once settings are frozen.
- Results are our evaluation on a published test split, not an official ViDoRe score.

## Candidates and rankings

- Every method ranks pages from the full 1,110-page corpus.
- A run maps each question to page IDs, best first. Duplicate or unknown page IDs are errors.
- A question missing from a run scores 0 on every metric.
- Text methods that rank chunks must aggregate to pages with a declared rule before evaluation.

## Metrics (per question, then averaged)

Grades: **2** = page contains a complete answer; **1** = required evidence that needs other pages; unjudged pages = 0.

| Metric | Definition |
| --- | --- |
| Hit@k | 1 if any judged page is in the top k. |
| Recall@k | Judged pages in the top k ÷ all judged pages. |
| Complete@k | 1 if the top k contains a grade-2 page, or every grade-1 page. Strict proxy: labels do not say which grade-1 pages are jointly sufficient. |
| MRR@10 | 1 ÷ rank of the first judged page in the top 10. |
| nDCG@10 | Linear gain (the grade), log2 discount, as in `pytrec_eval`. **Primary metric**, matching ViDoRe. |

k = 5 and 10.

## Ceilings

Some questions have more judged pages than k (up to 30), so a perfect retriever cannot reach 1 on Recall@k or Complete@k. Held-out ceilings from a perfect ranking:

| Metric | Ceiling |
| --- | --- |
| Recall@5 / @10 | 0.845 / 0.942 |
| Complete@5 / @10 | 0.782 / 0.877 |
| Hit@k, MRR@10, nDCG@10 | 1.000 |

Reports show these ceilings beside every method. A random ranking scores 0.003 nDCG@10.

## Reporting

- Means with 95% percentile bootstrap intervals (1,000 resamples, seed 0).
- Method comparisons use a paired bootstrap of per-question differences; an interval excluding 0 indicates a real difference.
- Breakdowns by `query_types` and `content_type`. Multi-label questions count in each label; always show n. Small groups (Infographic n=23, Image n=6 on held-out) are indicative only.
- Every run also records cost and latency (defined with the run format in step 5).
