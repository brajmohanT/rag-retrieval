"""Precompute every demo configuration so benchmark questions need no API calls at view time.

Run: uv run atlas-grid --dry-run   (estimate new reranking cost, spend nothing)
     uv run atlas-grid             (build artifacts/demo/grid.json)

A configuration is: which first-stage retrievers (any non-empty subset of the
four saved runs; two or more are fused with RRF, k as tuned in step 9), a
weight on the visual retrievers when text and visual are mixed, and whether
Cohere reranks the top 50. Scoreboards use held-out questions; per-question
results cover all 318.
"""

import argparse
from itertools import combinations
import json
import sys

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.evaluate import breakdown, evaluate, summarize
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.providers import openrouter
from evidence_atlas.providers.cache import Cache, digest
from evidence_atlas.providers.http import in_parallel, logged_calls
from evidence_atlas.retrieval.fusion import rrf
from evidence_atlas.retrieval.rerank import rerank_ranking
from evidence_atlas.retrieval.run_rerank import NO_TEXT
from evidence_atlas.retrieval.runs import load_run

RETRIEVERS = {  # short name -> (saved run, input)
    "bm25": ("bm25", "text"),
    "dense": ("dense-qwen3-embedding-8b", "text"),
    "voyage": ("visual-voyage-multimodal-3.5", "image"),
    "colqwen3": ("visual-colqwen3-4b", "image"),
}
VISUAL_WEIGHTS = [0.5, 1.0, 2.0]
RRF_K = 10  # tuned on dev in step 9
RERANKER = "cohere/rerank-5-pro"
RERANK_DEPTH = 50  # tuned on dev in step 9
SHOWN = 20  # pages stored per question and configuration
QUESTION_METRICS = ["ndcg@10", "hit@5", "recall@5", "complete@5"]


def configurations():
    """Every (members, visual_weight, rerank) the demo offers."""
    configs = []
    for size in range(1, len(RETRIEVERS) + 1):
        for members in combinations(RETRIEVERS, size):
            inputs = {RETRIEVERS[m][1] for m in members}
            weights = VISUAL_WEIGHTS if inputs == {"text", "image"} else [1.0]
            for weight in weights:
                for rerank in (False, True):
                    configs.append({"members": list(members), "visual_weight": weight, "rerank": rerank})
    for config in configs:
        config["id"] = "+".join(config["members"]) + f"|vw{config['visual_weight']:g}" + (
            "|cohere" if config["rerank"] else "")
    return configs


def first_stage(config, rankings):
    weights = [config["visual_weight"] if RETRIEVERS[m][1] == "image" else 1.0 for m in config["members"]]
    fused = rrf([rankings[m] for m in config["members"]], weights, k=RRF_K)
    return {q: [page for page, _ in pages] for q, pages in fused.items()}


def page_text(data, page_id):
    return data.pages[page_id].markdown.strip() or NO_TEXT


def uncached_pairs(shortlists, data):
    cache = Cache()
    missing = 0
    for query_id, pages in shortlists.items():
        query = digest(data.queries[query_id].text)
        for page in pages:
            key = Cache.key(provider="openrouter", model=RERANKER, query=query, input=digest(page_text(data, page)))
            missing += cache.get_json(key) is None
    return missing


def cost_and_latency(config, metas):
    """Members run in parallel (latency = slowest member); reranking runs after (latencies add)."""
    members = [metas[m] for m in config["members"]]
    index_cost = sum(m.get("index_cost_usd", 0) for m in members)
    query_cost = sum(m.get("query_cost_per_1k_usd", 0) for m in members)
    latency = max(m["query_latency"]["p50_ms"] for m in members)
    if config["rerank"]:
        calls = logged_calls(RERANKER, "rerank")
        pairs = sum(c["items"] for c in calls)
        query_cost += sum(c["cost_usd"] or 0 for c in calls) / pairs * RERANK_DEPTH * 1000
        latency += 1000 * sorted(c["seconds"] for c in calls)[len(calls) // 2]
    return {"index_cost_usd": round(index_cost, 4), "query_cost_per_1k_usd": round(query_cost, 4),
            "latency_p50_ms": round(latency)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="estimate new reranking cost only")
    args = parser.parse_args()

    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    partitions = load_partitions(config["evaluation"]["partitions_file"])
    query_ids = sorted(data.queries)
    loaded = {m: load_run(config["artifacts_dir"] / "runs" / run) for m, (run, _) in RETRIEVERS.items()}
    metas = {m: meta for m, (meta, _) in loaded.items()}
    rankings = {m: ranking for m, (_, ranking) in loaded.items()}
    configs = configurations()
    stages = {c["id"]: first_stage(c, rankings) for c in configs if not c["rerank"]}

    shortlists = {q: sorted({p for stage in stages.values() for p in stage[q][:RERANK_DEPTH]}) for q in query_ids}
    pairs = sum(len(pages) for pages in shortlists.values())
    missing = uncached_pairs(shortlists, data)
    calls = logged_calls(RERANKER, "rerank")
    per_pair = sum(c["cost_usd"] or 0 for c in calls) / max(sum(c["items"] for c in calls), 1)
    print(f"{len(configs)} configurations; {pairs} distinct question-page pairs to rerank, "
          f"{missing} not cached; estimated new cost ${missing * per_pair:.2f}")
    if args.dry_run:
        return 0

    scores = {}

    def run(batch):
        for q in batch:
            texts = [page_text(data, p) for p in shortlists[q]]
            scores[q] = dict(zip(shortlists[q], openrouter.rerank(data.queries[q].text, texts, RERANKER)))

    in_parallel(run, query_ids, batch_size=1, workers=8)

    grid = {"configs": [], "rankings": {}, "question_metrics": {}}
    for c in configs:
        base = stages[c["id"].removesuffix("|cohere")]
        if c["rerank"]:
            ranking = {q: rerank_ranking(base[q], [scores[q][p] for p in base[q][:RERANK_DEPTH]], RERANK_DEPTH)
                       for q in query_ids}
        else:
            ranking = base
        rows = evaluate(ranking, data, query_ids)
        by_id = {r["query_id"]: r for r in rows}
        held = [by_id[q] for q in partitions["heldout"]]
        grid["configs"].append({
            **c, **cost_and_latency(c, metas),
            "heldout": summarize(held, config["evaluation"]["bootstrap_samples"]),
            "heldout_by_content_type": breakdown(held, "content_type"),
            "heldout_by_query_type": breakdown(held, "query_types"),
        })
        grid["rankings"][c["id"]] = {q: ranking[q][:SHOWN] for q in query_ids}
        grid["question_metrics"][c["id"]] = {q: {m: round(by_id[q][m], 4) for m in QUESTION_METRICS}
                                             for q in query_ids}

    heldout = set(partitions["heldout"])
    grid["questions"] = [{"query_id": q.query_id, "text": q.text, "answer": q.answer,
                          "partition": "heldout" if q.query_id in heldout else "dev",
                          "query_types": q.query_types, "content_type": q.content_type,
                          "judged": [[r.page_id, r.grade] for r in data.qrels[q.query_id]]}
                         for q in sorted(data.queries.values(), key=lambda q: q.query_id)]
    grid["pages"] = {p.page_id: [p.doc_id, p.page_number] for p in data.pages.values()}
    grid["settings"] = {"rrf_k": RRF_K, "reranker": RERANKER, "rerank_depth": RERANK_DEPTH, "shown": SHOWN,
                        "visual_weights": VISUAL_WEIGHTS, "retrievers": RETRIEVERS,
                        "dataset_revision": config["dataset"]["revision"]}

    out = config["artifacts_dir"] / "demo" / "grid.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(grid, separators=(",", ":")))
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
