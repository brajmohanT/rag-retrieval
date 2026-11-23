"""Exact late-interaction (MaxSim) search over multi-vector page embeddings.

score(page, question) = sum over question vectors q of  max over page vectors p of  q · p

Each question token finds its best-matching patch on the page; the page score
adds those best matches. All page vectors are stacked into one matrix, so a
question is scored against every page with one matrix multiply, then a
per-page maximum.
"""

import numpy as np


class MaxSimIndex:
    def __init__(self, page_vectors):
        """page_vectors: page_id -> array [vectors, dimensions], already L2-normalized."""
        self.page_ids = list(page_vectors)
        arrays = [page_vectors[p] for p in self.page_ids]
        self.matrix = np.concatenate(arrays).astype(np.float32)
        lengths = [len(a) for a in arrays]
        self.starts = np.cumsum([0] + lengths[:-1])  # first row of each page in the matrix

    def scores(self, query_vectors):
        """MaxSim score for every page, in page_ids order."""
        similarity = np.asarray(query_vectors, dtype=np.float32) @ self.matrix.T  # [query tokens, all page vectors]
        best_per_page = np.maximum.reduceat(similarity, self.starts, axis=1)  # [query tokens, pages]
        return best_per_page.sum(axis=0)

    def search(self, query_vectors, k=100):
        """Top-k (page_id, score), best first; ties broken by page ID."""
        scores = self.scores(query_vectors)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.page_ids[i]))[:k]
        return [(self.page_ids[i], float(scores[i])) for i in order]
