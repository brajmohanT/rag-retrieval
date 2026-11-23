"""Visual retrieval: embed page images (not text) and rank pages for each question.

Run: uv run atlas-visual [voyage|colqwen3 ...]   (default: both)

voyage    Voyage multimodal 3.5 via OpenRouter: one vector per page image, cosine.
colqwen3  ColQwen3 4B via Superlinked: ~750 vectors per page image, MaxSim.

Pages are sent as the dataset's original PNGs (mostly 1654 x 2339). The first
run pays for embeddings (about $1.60 for both); reruns come from the cache.
"""

import sys
import time

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset, load_page_images
from evidence_atlas.providers import openrouter, superlinked
from evidence_atlas.retrieval.api_run import finish_run
from evidence_atlas.retrieval.dense import DenseIndex
from evidence_atlas.retrieval.late_interaction import MaxSimIndex

DEPTH = 100
IMAGE_INPUT = "original dataset PNG, mostly 1654x2339"


def voyage(page_ids, images, questions):
    print(f"Voyage: embedding {len(page_ids)} page images...")
    page_vectors = openrouter.embed(images, openrouter.VOYAGE_MULTIMODAL, kind="document")
    print(f"Voyage: embedding {len(questions)} questions, one request each...")
    query_vectors = openrouter.embed([q.text for q in questions], openrouter.VOYAGE_MULTIMODAL, kind="query",
                                     batch_size=1)
    index = DenseIndex(dict(zip(page_ids, page_vectors)))
    settings = {"model": openrouter.VOYAGE_MULTIMODAL, "provider": "openrouter", "vectors": "single",
                "image_input": IMAGE_INPUT, "dimensions": int(index.matrix.shape[1]), "depth": DEPTH}
    return "visual-voyage-multimodal-3.5", openrouter.VOYAGE_MULTIMODAL, index, query_vectors, settings


def colqwen3(page_ids, images, questions):
    print(f"ColQwen3: encoding {len(page_ids)} page images...")
    page_vectors = superlinked.encode(images, is_query=False)
    print(f"ColQwen3: encoding {len(questions)} questions, one request each...")
    query_vectors = superlinked.encode([q.text for q in questions], is_query=True, batch_size=1)
    index = MaxSimIndex(dict(zip(page_ids, page_vectors)))
    settings = {"model": superlinked.COLQWEN3, "provider": "superlinked", "vectors": "multi",
                "scoring": "MaxSim", "image_input": IMAGE_INPUT, "dimensions": int(index.matrix.shape[1]),
                "vectors_per_page_mean": round(len(index.matrix) / len(page_ids), 1), "depth": DEPTH}
    return "visual-colqwen3-4b", superlinked.COLQWEN3, index, query_vectors, settings


METHODS = {"voyage": voyage, "colqwen3": colqwen3}


def main():
    chosen = sys.argv[1:] or list(METHODS)
    unknown = set(chosen) - set(METHODS)
    if unknown:
        print(f"Unknown method(s): {', '.join(sorted(unknown))}. Choose from {', '.join(METHODS)}.", file=sys.stderr)
        return 2
    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    page_ids = sorted(data.pages)
    stored = load_page_images(config["dataset"]["data_dir"], page_ids)
    images = [stored[p] for p in page_ids]
    questions = list(data.queries.values())

    for method in chosen:
        name, model, index, query_vectors, settings = METHODS[method](page_ids, images, questions)
        results, search_seconds = {}, []
        for query, vectors in zip(questions, query_vectors):
            start = time.perf_counter()
            results[query.query_id] = index.search(vectors, DEPTH)
            search_seconds.append(time.perf_counter() - start)
        finish_run(config, data, name, "visual", settings, results, model, len(page_ids), search_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
