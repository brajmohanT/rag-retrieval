"""Rerank the fusion shortlist with each reranker and compare against fusion on dev questions.

Run: uv run atlas-rerank [--partition dev] [--depth 20] [reranker ...]
Rerankers: vl (Qwen3-VL-Reranker-2B on page images, Superlinked),
cohere (Cohere Rerank 5 Pro on page text), qwen (Qwen3-Reranker-8B on page text).

Dev only by default: held-out is evaluated only after a reranker is chosen on dev.
Rankings are saved to artifacts/runs/rerank-<name>-d<depth>-<partition>/ for inspection.
--partition all reranks every question, prints the held-out comparison, and saves a
standard run with cost, latency, and report: artifacts/runs/fusion-rerank-<name>-d<depth>/.
"""

import argparse
import sys

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset, load_page_images
from evidence_atlas.evaluation.evaluate import evaluate, paired_difference, summarize
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.evaluation.report import report_run
from evidence_atlas.providers import openrouter, superlinked
from evidence_atlas.providers.http import in_parallel, logged_calls
from evidence_atlas.retrieval.rerank import rerank_ranking
from evidence_atlas.retrieval.runs import latency_summary, load_run, save_run

FIRST_STAGE = "fusion"
NO_TEXT = "[This page has no extracted text.]"
RERANKERS = {
    "vl": (superlinked.VL_RERANKER, "image"),
    "cohere": ("cohere/rerank-5-pro", "text"),
    "qwen": ("qwen/qwen3-reranker-8b", "text"),
}
METRICS = ["ndcg@10", "mrr@10", "hit@5", "recall@5", "complete@5", "complete@10"]


def score_shortlist(model, kind, question, page_ids, data, images):
    if kind == "image":
        return superlinked.rerank(question, [images[p] for p in page_ids], model)
    return openrouter.rerank(question, [data.pages[p].markdown.strip() or NO_TEXT for p in page_ids], model)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rerankers", nargs="*", default=list(RERANKERS), choices=list(RERANKERS))
    parser.add_argument("--partition", default="dev", choices=["dev", "heldout", "all"])
    parser.add_argument("--depth", type=int, default=20)
    args = parser.parse_args()

    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    partitions = load_partitions(config["evaluation"]["partitions_file"])
    final = args.partition == "all"
    query_ids = partitions["dev"] + partitions["heldout"] if final else partitions[args.partition]
    compare_ids = partitions["heldout"] if final else query_ids
    first_meta, first_stage = load_run(config["artifacts_dir"] / "runs" / FIRST_STAGE)
    shortlists = {q: first_stage[q][:args.depth] for q in query_ids}
    needed = {p for pages in shortlists.values() for p in pages}
    images = load_page_images(config["dataset"]["data_dir"], needed) if any(
        RERANKERS[r][1] == "image" for r in args.rerankers) else {}

    base_rows = evaluate(first_stage, data, compare_ids)
    base = summarize(base_rows, samples=1)
    print(f"{'heldout' if final else args.partition} questions compared: {len(compare_ids)}; "
          f"shortlist: top {args.depth} of {FIRST_STAGE}")
    print(f"  {FIRST_STAGE:10}" + "".join(f"  {m} {base[m]['mean']:.3f}" for m in METRICS))

    for name in args.rerankers:
        model, kind = RERANKERS[name]
        scores = {}

        def run(batch):
            for q in batch:
                scores[q] = score_shortlist(model, kind, data.queries[q].text, shortlists[q], data, images)

        in_parallel(run, query_ids, batch_size=1, workers=8)
        rankings = {q: rerank_ranking(first_stage[q], scores[q], args.depth) for q in query_ids}
        rows = evaluate(rankings, data, compare_ids)
        summary = summarize(rows, samples=1)
        print(f"  {name:10}" + "".join(f"  {m} {summary[m]['mean']:.3f}" for m in METRICS))
        for m in ("ndcg@10", "complete@5"):
            d = paired_difference(rows, base_rows, m)
            verdict = "significant" if d["low"] > 0 or d["high"] < 0 else "not significant"
            print(f"    vs {FIRST_STAGE} {m}: {d['mean']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}] {verdict}")
        calls = logged_calls(model, "rerank")
        pairs = sum(c["items"] for c in calls)
        cost_per_pair = sum(c["cost_usd"] or 0 for c in calls) / pairs if pairs else 0
        latency = sorted(c["seconds"] for c in calls)
        print(f"    cost ${cost_per_pair * args.depth * 1000:.2f} per 1,000 questions; "
              f"request p50 {latency[len(latency) // 2]:.1f} s" if latency else "")
        if final:
            run_name = f"{FIRST_STAGE}-rerank-{name}-d{args.depth}"
            rerank_per_1k = cost_per_pair * args.depth * 1000
            save_run(config["artifacts_dir"] / "runs" / run_name,
                     {q: [(p, 0.0) for p in rankings[q]] for q in query_ids},
                     {"name": run_name, "method": "rerank",
                      "settings": {"reranker": model, "input": kind, "first_stage": FIRST_STAGE,
                                   "first_stage_settings": first_meta["settings"], "depth": args.depth,
                                   "depth_selected_on": "dev nDCG@10 among 10, 20, 50"},
                      "dataset_revision": config["dataset"]["revision"],
                      # Reranking runs after retrieval, so latencies add: first-stage p50 + rerank request p50.
                      "query_latency": {"p50_ms": first_meta["query_latency"]["p50_ms"]
                                        + 1000 * latency[len(latency) // 2], "n": len(latency)},
                      "rerank_latency": latency_summary(latency),
                      "index_cost_usd": first_meta["index_cost_usd"],
                      "query_cost_per_1k_usd": first_meta["query_cost_per_1k_usd"] + rerank_per_1k,
                      "cost_usd": first_meta["cost_usd"] + rerank_per_1k * len(query_ids) / 1000})
            evaluation = config["evaluation"]
            report_run(config["artifacts_dir"] / "runs" / run_name, data, partitions,
                       tuple(evaluation["ks"]), evaluation["bootstrap_samples"])
            print(f"    report: {config['artifacts_dir'] / 'runs' / run_name / 'report.md'}")
            continue
        save_run(config["artifacts_dir"] / "runs" / f"rerank-{name}-d{args.depth}-{args.partition}",
                 {q: [(p, 0.0) for p in rankings[q]] for q in query_ids},
                 {"name": f"rerank-{name}-d{args.depth}-{args.partition}", "method": "rerank",
                  "settings": {"reranker": model, "input": kind, "first_stage": FIRST_STAGE, "depth": args.depth,
                               "partition": args.partition},
                  "dataset_revision": config["dataset"]["revision"],
                  "rerank_cost_per_1k_queries_usd": cost_per_pair * args.depth * 1000})
    return 0


if __name__ == "__main__":
    sys.exit(main())
