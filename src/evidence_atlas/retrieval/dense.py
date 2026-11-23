"""Exact single-vector search: cosine similarity between a question and every page.

Vectors are L2-normalized once, so cosine similarity is a dot product and
scoring all 1,110 pages is one matrix-vector multiply.
"""

import numpy as np


def normalize(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


class DenseIndex:
    def __init__(self, page_vectors):
        """page_vectors: page_id -> vector. Pages without a vector are simply absent."""
        self.page_ids = list(page_vectors)
        self.matrix = normalize([page_vectors[p] for p in self.page_ids])

    def search(self, query_vector, k=100):
        """Top-k (page_id, cosine), best first; ties broken by page ID."""
        scores = self.matrix @ normalize(query_vector)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.page_ids[i]))[:k]
        return [(self.page_ids[i], float(scores[i])) for i in order]
