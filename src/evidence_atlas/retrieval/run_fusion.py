"""Tune RRF fusion on dev questions, then evaluate the chosen setting on held-out.

Run: uv run atlas-fusion
Tries every combination of two or more saved runs with equal weights and
k in {10, 30, 60}; picks the best by dev nDCG@10. Held-out questions play no
part in the choice. Costs nothing: it reuses saved rankings.
Writes artifacts/runs/fusion/ (the chosen run) and its tuning.json (every setting tried).
"""

from itertools import combinations
import json
import sys

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.evaluate import evaluate, summarize
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.evaluation.report import fmt, report_run
from evidence_atlas.retrieval.fusion import rrf
from evidence_atlas.retrieval.runs import load_run, save_run

RUNS = ["bm25", "dense-qwen3-embedding-8b", "visual-voyage-multimodal-3.5", "visual-colqwen3-4b"]
KS = [10, 30, 60]
DEPTH = 100


def mean_ndcg(rankings, data, query_ids):
    return summarize(evaluate(rankings, data, query_ids), samples=1)["ndcg@10"]["mean"]


def main():
    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    partitions = load_partitions(config["evaluation"]["partitions_file"])
    runs = {name: load_run(config["artifacts_dir"] / "runs" / name) for name in RUNS}

    trials = []
    for size in range(2, len(RUNS) + 1):
        for members in combinations(RUNS, size):
            for k in KS:
                fused = rrf([runs[m][1] for m in members], k=k, depth=DEPTH)
                ranked = {q: [page for page, _ in pages] for q, pages in fused.items()}
                trials.append({"members": list(members), "k": k, "dev_ndcg@10": mean_ndcg(ranked, data, partitions["dev"])})
    trials.sort(key=lambda t: -t["dev_ndcg@10"])
    best = trials[0]
    single = {m: mean_ndcg(runs[m][1], data, partitions["dev"]) for m in RUNS}

    print("Dev nDCG@10, single methods:")
    for m, score in sorted(single.items(), key=lambda item: -item[1]):
        print(f"  {score:.3f}  {m}")
    print("Dev nDCG@10, top 8 fusion settings of", len(trials))
    for t in trials[:8]:
        print(f"  {t['dev_ndcg@10']:.3f}  k={t['k']:<2}  {' + '.join(t['members'])}")

    metas = [runs[m][0] for m in best["members"]]
    run_dir = config["artifacts_dir"] / "runs" / "fusion"
    results = rrf([runs[m][1] for m in best["members"]], k=best["k"], depth=DEPTH)
    save_run(run_dir, results, {
        "name": "fusion", "method": "rrf",
        "settings": {"members": best["members"], "weights": "equal", "k": best["k"], "depth": DEPTH,
                     "selected_on": "dev nDCG@10", "settings_tried": len(trials)},
        "dataset_revision": config["dataset"]["revision"],
        # Members run in parallel at query time, so latency is the slowest member's; costs add up.
        "query_latency": max((m["query_latency"] for m in metas), key=lambda lat: lat["p50_ms"]),
        "index_cost_usd": sum(m.get("index_cost_usd", 0) for m in metas),
        "query_cost_per_1k_usd": sum(m.get("query_cost_per_1k_usd", 0) for m in metas),
        "cost_usd": sum(m.get("cost_usd", 0) for m in metas),
    })
    (run_dir / "tuning.json").write_text(json.dumps({"single_dev_ndcg@10": single, "trials": trials}, indent=1) + "\n")
    evaluation = config["evaluation"]
    metrics = report_run(run_dir, data, partitions, tuple(evaluation["ks"]), evaluation["bootstrap_samples"])
    held = metrics["heldout"]
    print(f"\nChosen: {' + '.join(best['members'])}, k={best['k']}")
    print(f"Held-out nDCG@10 {fmt(held['summary']['ndcg@10'])}; "
          f"Complete@5 {fmt(held['summary']['complete@5'])} (ceiling {held['ceiling']['complete@5']:.3f})")
    print(f"Report: {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
