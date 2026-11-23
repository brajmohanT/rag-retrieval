"""Dense text retrieval: embed each page's Markdown and each question, rank by cosine.

Run: uv run atlas-dense
Writes artifacts/runs/dense-qwen3-embedding-8b/. The first run pays for
embeddings (under $0.05); reruns come from the cache.
"""

import sys
import time

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.providers import openrouter
from evidence_atlas.retrieval.api_run import finish_run
from evidence_atlas.retrieval.dense import DenseIndex

MODEL = "qwen/qwen3-embedding-8b"
# Qwen3-Embedding expects an instruction on queries only; pages are embedded as-is.
INSTRUCTION = "Given a question about EU labour-market reports, retrieve the report pages that answer it"
NAME = "dense-qwen3-embedding-8b"
DEPTH = 100


def query_text(question):
    return f"Instruct: {INSTRUCTION}\nQuery:{question}"


def main():
    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])

    pages = {p.page_id: p.markdown for p in data.pages.values() if p.markdown.strip()}
    print(f"Embedding {len(pages)} pages ({len(data.pages) - len(pages)} without text are skipped)...")
    vectors = openrouter.embed(list(pages.values()), MODEL, kind="document", batch_size=16)
    index = DenseIndex(dict(zip(pages, vectors)))

    print(f"Embedding {len(data.queries)} questions, one request each...")
    questions = list(data.queries.values())
    query_vectors = openrouter.embed([query_text(q.text) for q in questions], MODEL, kind="query", batch_size=1)
    results, search_seconds = {}, []
    for query, vector in zip(questions, query_vectors):
        start = time.perf_counter()
        results[query.query_id] = index.search(vector, DEPTH)
        search_seconds.append(time.perf_counter() - start)

    settings = {"model": MODEL, "provider": "openrouter", "unit": "whole page markdown",
                "query_instruction": INSTRUCTION, "dimensions": int(index.matrix.shape[1]),
                "pages_embedded": len(pages), "depth": DEPTH}
    finish_run(config, data, NAME, "dense", settings, results, MODEL, len(pages), search_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
