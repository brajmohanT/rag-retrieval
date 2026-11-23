"""Finish a run whose embeddings came from a paid API: cost and latency from the call log, save, report.

The cache means a rerun makes few or no calls, so costs come from the call log
rather than from this run. Cost per item (logged cost / logged items) times the
corpus or question count gives the full cost even if some items were cached
earlier, for example by the smoke test.
"""

from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.evaluation.report import fmt, report_run
from evidence_atlas.providers.http import logged_calls
from evidence_atlas.retrieval.runs import latency_summary, save_run


def cost_per_item(model, kind):
    calls = logged_calls(model, kind)
    items = sum(c["items"] for c in calls)
    return sum(c["cost_usd"] or 0 for c in calls) / items if items else 0.0


def finish_run(config, data, name, method, settings, results, model, pages_encoded, search_seconds):
    """Save the run with cost and latency, write its report, and print a summary."""
    index_cost = cost_per_item(model, "document") * pages_encoded
    query_cost_per_1k = cost_per_item(model, "query") * 1000
    document_calls = logged_calls(model, "document")
    # Questions are sent one per request, so each single-item call is one question's API latency.
    query_seconds = [c["seconds"] for c in logged_calls(model, "query") if c["items"] == 1]
    run_dir = config["artifacts_dir"] / "runs" / name
    save_run(run_dir, results, {
        "name": name, "method": method, "settings": settings,
        "dataset_revision": config["dataset"]["revision"],
        "index_seconds": sum(c["seconds"] for c in document_calls),  # summed request time, not wall clock
        "query_latency": latency_summary(query_seconds),
        "search_latency": latency_summary(search_seconds),
        "index_cost_usd": index_cost,
        "query_cost_per_1k_usd": query_cost_per_1k,
        "cost_usd": index_cost + query_cost_per_1k * len(results) / 1000,
    })
    evaluation = config["evaluation"]
    metrics = report_run(run_dir, data, load_partitions(evaluation["partitions_file"]),
                         tuple(evaluation["ks"]), evaluation["bootstrap_samples"])
    held = metrics["heldout"]
    print(f"Index cost ${index_cost:.4f} for {pages_encoded} pages; queries ${query_cost_per_1k:.4f} per 1,000. "
          f"Query latency p50 {latency_summary(query_seconds)['p50_ms']:.0f} ms (API) "
          f"+ {latency_summary(search_seconds)['p50_ms']:.2f} ms (search).")
    print(f"Held-out nDCG@10 {fmt(held['summary']['ndcg@10'])}; "
          f"Complete@5 {fmt(held['summary']['complete@5'])} (ceiling {held['ceiling']['complete@5']:.3f})")
    print(f"Report: {run_dir / 'report.md'}")
    return metrics
