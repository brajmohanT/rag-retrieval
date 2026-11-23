"""Evaluate a saved run on the frozen partitions; write metrics.json and report.md.

Run: uv run atlas-eval artifacts/runs/bm25

Scores and breakdowns report held-out questions. Failure examples come from
dev only, so studying them cannot leak into held-out results.
"""

import argparse
import json
from pathlib import Path
import sys

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.evaluate import breakdown, evaluate, summarize
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.retrieval.runs import load_run

HEADLINE = ["ndcg@10", "mrr@10", "hit@5", "recall@5", "complete@5", "hit@10", "recall@10", "complete@10"]
FAILURES_SHOWN = 10


def perfect_rankings(data, query_ids):
    """Judged pages in grade order: the best any retriever can do."""
    return {q: [r.page_id for r in data.qrels[q]] for q in query_ids}


def page_label(data, page_id):
    page = data.pages[page_id]
    return f"{page_id} ({page.doc_id[:40]}, p.{page.page_number + 1})"


def failures(data, rankings, rows):
    """Dev questions with no judged page in the top 10."""
    lines = []
    for row in [r for r in rows if r["hit@10"] == 0][:FAILURES_SHOWN]:
        query_id = row["query_id"]
        ranking = rankings.get(query_id, [])
        judged = {r.page_id for r in data.qrels[query_id]}
        first = next((rank for rank, page in enumerate(ranking, 1) if page in judged), None)
        lines += [
            f"- **Q{query_id}** ({', '.join(row['query_types'])}; {', '.join(row['content_type'])}): "
            f"{data.queries[query_id].text}",
            f"  - First judged page at rank: {first or 'not retrieved'}",
            f"  - Retrieved top 3: {'; '.join(page_label(data, p) for p in ranking[:3]) or 'nothing'}",
            f"  - Judged: {'; '.join(page_label(data, r.page_id) + f' g{r.grade}' for r in data.qrels[query_id][:3])}",
        ]
    return lines


def fmt(stat):
    return f"{stat['mean']:.3f} [{stat['low']:.3f}–{stat['high']:.3f}]"


def breakdown_table(table, ceiling):
    lines = ["| Label | n | nDCG@10 | Complete@5 | Complete@5 ceiling |", "| --- | --- | --- | --- | --- |"]
    for label, row in table.items():
        lines.append(f"| {label} | {row['n']} | {row['ndcg@10']:.3f} | {row['complete@5']:.3f} | "
                     f"{ceiling[label]['complete@5']:.3f} |")
    return lines


def report_run(run_dir, data, partitions, ks=(5, 10), samples=1000):
    run_dir = Path(run_dir)
    meta, rankings = load_run(run_dir)
    results = {}
    for name in ("dev", "heldout"):
        ids = partitions[name]
        rows = evaluate(rankings, data, ids, ks)
        ceiling_rows = evaluate(perfect_rankings(data, ids), data, ids, ks)
        results[name] = {
            "rows": rows,
            "summary": summarize(rows, samples),
            "ceiling": {m: s["mean"] for m, s in summarize(ceiling_rows, samples=1).items()},
            "by_content_type": breakdown(rows, "content_type"),
            "by_query_type": breakdown(rows, "query_types"),
            "ceiling_by_content_type": breakdown(ceiling_rows, "content_type"),
            "ceiling_by_query_type": breakdown(ceiling_rows, "query_types"),
        }
    dev, held = results["dev"], results["heldout"]
    metrics = {"run": meta, **{name: {k: v for k, v in r.items() if k != "rows"} for name, r in results.items()}}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    latency = meta.get("query_latency", {})
    lines = [
        f"# Run report: {meta['name']}", "",
        f"Method: `{meta['method']}`. Settings: `{json.dumps(meta.get('settings', {}))}`.",
        f"Dataset revision `{meta['dataset_revision'][:12]}`; created {meta['created_at']}.",
        f"Index build: {meta.get('index_seconds', 0):.2f} s. Query latency: p50 {latency.get('p50_ms', 0):.1f} ms, "
        f"p95 {latency.get('p95_ms', 0):.1f} ms. Cost: ${meta.get('cost_usd', 0):.4f}"
        + (f" (index ${meta['index_cost_usd']:.4f}; queries ${meta['query_cost_per_1k_usd']:.4f} per 1,000)"
           if "index_cost_usd" in meta else "") + ".", "",
        "## Scores", "",
        f"Mean with 95% bootstrap interval. Dev n={len(partitions['dev'])}, held-out n={len(partitions['heldout'])}. "
        "Ceiling: a perfect ranking on held-out.", "",
        "| Metric | Dev | Held-out | Held-out ceiling |", "| --- | --- | --- | --- |",
    ]
    for m in HEADLINE:
        lines.append(f"| {m} | {fmt(dev['summary'][m])} | {fmt(held['summary'][m])} | {held['ceiling'][m]:.3f} |")
    lines += ["", "## Held-out by content type", "",
              *breakdown_table(held["by_content_type"], held["ceiling_by_content_type"]),
              "", "## Held-out by question type", "",
              *breakdown_table(held["by_query_type"], held["ceiling_by_query_type"]),
              "", "## Dev failures (no judged page in the top 10)", "",
              f"{sum(r['hit@10'] == 0 for r in dev['rows'])} of {len(dev['rows'])} dev questions. "
              f"First {FAILURES_SHOWN}:", "",
              *failures(data, rankings, dev["rows"]), ""]
    (run_dir / "report.md").write_text("\n".join(lines))
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    config = load_config()
    settings = config["evaluation"]
    data = load_dataset(config["dataset"]["data_dir"])
    metrics = report_run(args.run_dir, data, load_partitions(settings["partitions_file"]),
                         tuple(settings["ks"]), settings["bootstrap_samples"])
    held = metrics["heldout"]
    print(f"Held-out: nDCG@10 {fmt(held['summary']['ndcg@10'])}, "
          f"Complete@5 {fmt(held['summary']['complete@5'])} (ceiling {held['ceiling']['complete@5']:.3f})")
    print(f"Report: {args.run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
