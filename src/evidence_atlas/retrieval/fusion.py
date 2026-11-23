"""Reciprocal rank fusion (RRF): combine rankings from several methods using ranks only.

fused(page) = sum over methods m of  weight_m / (k + rank_m(page))

Raw scores (BM25, cosine, MaxSim) are on different scales, so only ranks are
used. A page missing from a method's list gets nothing from that method.
Smaller k lets top ranks dominate; larger k flattens the vote.
"""

from collections import defaultdict


def rrf(rankings, weights=None, k=60, depth=100):
    """rankings: list of {query_id: [page_id, ...]} (best first). Returns {query_id: [(page_id, score), ...]}."""
    weights = weights or [1.0] * len(rankings)
    query_ids = set().union(*rankings)
    fused = {}
    for query_id in query_ids:
        scores = defaultdict(float)
        for ranking, weight in zip(rankings, weights):
            for rank, page in enumerate(ranking.get(query_id, []), start=1):
                scores[page] += weight / (k + rank)
        fused[query_id] = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:depth]
    return fused
