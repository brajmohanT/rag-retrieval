"""Per-question retrieval metrics over a ranked list of page IDs.

`judged` maps page_id -> grade for one question: 2 is a complete answer,
1 is required evidence that needs other pages. Unjudged pages count as 0.
"""

from math import log2


def hit_at_k(ranking, judged, k):
    """1 if any judged page is in the top k (any-page recall)."""
    return float(any(page in judged for page in ranking[:k]))


def recall_at_k(ranking, judged, k):
    """Fraction of all judged pages found in the top k (relevant-page recall)."""
    return sum(page in judged for page in ranking[:k]) / len(judged)


def complete_at_k(ranking, judged, k):
    """1 if the top k holds a complete-answer page, or every grade-1 page.

    A strict proxy: the labels do not say which grade-1 pages are jointly
    sufficient, so all of them are required.
    """
    top = set(ranking[:k])
    if any(judged.get(page) == 2 for page in top):
        return 1.0
    partial = {page for page, grade in judged.items() if grade == 1}
    return float(bool(partial) and partial <= top)


def mrr_at_k(ranking, judged, k):
    """Reciprocal rank of the first judged page within the top k."""
    for rank, page in enumerate(ranking[:k], start=1):
        if page in judged:
            return 1 / rank
    return 0.0


def ndcg_at_k(ranking, judged, k):
    """nDCG with linear gain (grade) and log2 discount, as in pytrec_eval."""
    dcg = sum(judged.get(page, 0) / log2(rank + 1) for rank, page in enumerate(ranking[:k], start=1))
    ideal = sorted(judged.values(), reverse=True)[:k]
    idcg = sum(grade / log2(rank + 1) for rank, grade in enumerate(ideal, start=1))
    return dcg / idcg


def score_question(ranking, judged, ks=(5, 10)):
    """All metrics for one question, keyed like 'recall@5'."""
    if len(set(ranking)) != len(ranking):
        raise ValueError("Ranking contains duplicate page IDs")
    scores = {}
    for k in ks:
        scores[f"hit@{k}"] = hit_at_k(ranking, judged, k)
        scores[f"recall@{k}"] = recall_at_k(ranking, judged, k)
        scores[f"complete@{k}"] = complete_at_k(ranking, judged, k)
    scores["mrr@10"] = mrr_at_k(ranking, judged, 10)
    scores["ndcg@10"] = ndcg_at_k(ranking, judged, 10)
    return scores
