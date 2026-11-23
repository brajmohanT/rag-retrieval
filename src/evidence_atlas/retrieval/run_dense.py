"""Dense text retrieval: embed each page's Markdown and each question, rank by cosine.

Run: uv run atlas-dense
Writes artifacts/runs/dense-qwen3-embedding-8b/. The first run pays for
embeddings (under $0.05); reruns come from the cache.
"""

import sys
import time

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.evaluation.report import fmt, report_run
from evidence_atlas.providers import openrouter
from evidence_atlas.providers.http import logged_calls
from evidence_atlas.retrieval.dense import DenseIndex
from evidence_atlas.retrieval.runs import latency_summary, save_run

MODEL = "qwen/qwen3-embedding-8b"
# Qwen3-Embedding expects an instruction on queries only; pages are embedded as-is.
INSTRUCTION = "Given a question about EU labour-market reports, retrieve the report pages that answer it"
NAME = "dense-qwen3-embedding-8b"
DEPTH = 100


def query_text(question):
    return f"Instruct: {INSTRUCTION}\nQuery:{question}"


def cost_summary(model, kind):
    calls = logged_calls(model, kind)
    items = sum(c["items"] for c in calls)
    return sum(c["cost_usd"] or 0 for c in calls), items, [c["seconds"] for c in calls if c["items"] == 1]


def main():
    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])

    pages = {p.page_id: p.markdown for p in data.pages.values() if p.markdown.strip()}
    print(f"Embedding {len(pages)} pages ({len(data.pages) - len(pages)} without text are skipped)...")
    vectors = openrouter.embed(list(pages.values()), MODEL, kind="document", batch_size=16)
    index = DenseIndex(dict(zip(pages, vectors)))

    print(f"Embedding and searching {len(data.queries)} questions, one request each...")
    results, search_seconds = {}, []
    for query in data.queries.values():
        vector, = openrouter.embed([query_text(query.text)], MODEL, kind="query", batch_size=1)
        start = time.perf_counter()
        results[query.query_id] = index.search(vector, DEPTH)
        search_seconds.append(time.perf_counter() - start)

    index_cost, index_items, _ = cost_summary(MODEL, "document")
    query_cost, query_items, query_seconds = cost_summary(MODEL, "query")
    run_dir = config["artifacts_dir"] / "runs" / NAME
    save_run(run_dir, results, {
        "name": NAME, "method": "dense",
        "settings": {"model": MODEL, "provider": "openrouter", "unit": "whole page markdown",
                     "query_instruction": INSTRUCTION, "dimensions": int(index.matrix.shape[1]),
                     "pages_embedded": len(pages), "depth": DEPTH},
        "dataset_revision": config["dataset"]["revision"],
        "index_seconds": sum(c["seconds"] for c in logged_calls(MODEL, "document")),
        "query_latency": latency_summary(query_seconds),
        "search_latency": latency_summary(search_seconds),
        "index_cost_usd": index_cost,
        "query_cost_per_1k_usd": 1000 * query_cost / max(query_items, 1),
        "cost_usd": index_cost + query_cost,
    })
    settings = config["evaluation"]
    metrics = report_run(run_dir, data, load_partitions(settings["partitions_file"]),
                         tuple(settings["ks"]), settings["bootstrap_samples"])
    held = metrics["heldout"]
    print(f"Index cost ${index_cost:.4f} for {index_items} pages; queries ${1000 * query_cost / max(query_items, 1):.4f}"
          f" per 1,000. Query latency p50 {latency_summary(query_seconds)['p50_ms']:.0f} ms (API) "
          f"+ {latency_summary(search_seconds)['p50_ms']:.2f} ms (search).")
    print(f"Held-out nDCG@10 {fmt(held['summary']['ndcg@10'])}; "
          f"Complete@5 {fmt(held['summary']['complete@5'])} (ceiling {held['ceiling']['complete@5']:.3f})")
    print(f"Report: {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
