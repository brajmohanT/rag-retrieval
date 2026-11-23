"""Run BM25 over every English question and evaluate it.

Run: uv run atlas-bm25
Writes artifacts/runs/bm25/{run.json, rankings.jsonl, metrics.json, report.md}.
"""

import sys
import time

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.evaluation.report import fmt, report_run
from evidence_atlas.retrieval.bm25 import BM25
from evidence_atlas.retrieval.runs import latency_summary, save_run

SETTINGS = {"k1": 1.2, "b": 0.75, "text": "dataset markdown", "depth": 100,
            "tokenizer": "lowercase, words and numbers, English stopwords removed, Snowball stem"}


def main():
    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])

    start = time.perf_counter()
    index = BM25({p.page_id: p.markdown for p in data.pages.values()}, SETTINGS["k1"], SETTINGS["b"])
    index_seconds = time.perf_counter() - start

    results, latencies = {}, []
    for query in data.queries.values():
        start = time.perf_counter()
        results[query.query_id] = index.search(query.text, SETTINGS["depth"])
        latencies.append(time.perf_counter() - start)

    run_dir = config["artifacts_dir"] / "runs" / "bm25"
    save_run(run_dir, results, {
        "name": "bm25", "method": "bm25", "settings": SETTINGS,
        "dataset_revision": config["dataset"]["revision"],
        "index_seconds": index_seconds, "vocabulary_size": len(index.postings),
        "query_latency": latency_summary(latencies), "cost_usd": 0.0,
    })
    settings = config["evaluation"]
    metrics = report_run(run_dir, data, load_partitions(settings["partitions_file"]),
                         tuple(settings["ks"]), settings["bootstrap_samples"])
    held = metrics["heldout"]
    print(f"Indexed {len(data.pages)} pages in {index_seconds:.2f} s; {len(index.postings)} terms.")
    print(f"Held-out nDCG@10 {fmt(held['summary']['ndcg@10'])}; "
          f"Complete@5 {fmt(held['summary']['complete@5'])} (ceiling {held['ceiling']['complete@5']:.3f})")
    print(f"Report: {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
