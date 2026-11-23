"""Second-stage reranking: re-sort a first-stage shortlist by a reranker's scores.

The top `depth` pages of the first-stage ranking are re-sorted by reranker
score (ties keep first-stage order); pages below the shortlist keep their
first-stage order after it. A reranker cannot recover a page that is not on
the shortlist.
"""


def rerank_ranking(ranking, scores, depth):
    """ranking: page IDs best first; scores: reranker scores for ranking[:depth], in that order."""
    shortlist = ranking[:depth]
    order = sorted(range(len(shortlist)), key=lambda i: (-scores[i], i))
    return [shortlist[i] for i in order] + ranking[depth:]
