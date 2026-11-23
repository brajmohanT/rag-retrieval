"""Superlinked serverless encoding: ColQwen3 multi-vector embeddings.

One page image -> about 750 vectors of 320 dimensions; one question -> one
vector per token. Score with MaxSim (in the retrieval step).
Billing is in credits; at the list price ($0.20 per 1,000 images), 1 credit = $0.00001.
"""

import base64
from urllib.parse import quote

import numpy as np

from evidence_atlas.providers.cache import Cache, digest
from evidence_atlas.providers.http import api_key, in_parallel, log_call, post_json

BASE_URL = "https://api.superlinked.com/v1/encode/"
COLQWEN3 = "TomoroAI/tomoro-colqwen3-embed-4b:compact"
VL_RERANKER = "Qwen/Qwen3-VL-Reranker-2B"
SCORE_URL = "https://api.superlinked.com/v1/score/"
USD_PER_CREDIT = 0.00001


def encode(items, is_query, model=COLQWEN3, cache=None, batch_size=4, workers=8):
    """Multi-vectors for texts (questions) or PNG bytes (pages), in input order.

    Uncached items are sent in batches, up to `workers` requests at a time.
    Returns a list of float32 arrays shaped [vectors, dimensions].
    """
    cache = cache or Cache()
    keys = [Cache.key(provider="superlinked", model=model, is_query=is_query, input=digest(item)) for item in items]
    results = [cache.get_array(key) for key in keys]

    def run(batch):
        for i, array in zip(batch, request(model, [items[i] for i in batch], is_query)):
            cache.put_array(keys[i], array)
            results[i] = array

    in_parallel(run, [i for i, result in enumerate(results) if result is None], batch_size, workers)
    return results


def request(model, items, is_query):
    payload = {
        "items": [{"text": item} if isinstance(item, str)
                  else {"images": [{"data": base64.b64encode(item).decode(), "format": "png"}]}
                  for item in items],
        "params": {"output_types": ["multivector"], "options": {"is_query": is_query}},
    }
    headers = {"Authorization": f"Bearer {api_key('SUPERLINKED_API_KEY')}", "Accept": "application/json"}
    response, seconds = post_json(BASE_URL + quote(model, safe=""), payload, headers)
    usage = response.get("usage", {})
    credits = float(usage.get("credits_charged_decimal", usage.get("credits_charged", 0)))
    log_call("superlinked", model, "query" if is_query else "document", len(items), seconds,
             credits * USD_PER_CREDIT, usage)
    return [np.asarray(item["multivector"]["values"], dtype=np.float32) for item in response["items"]]


def rerank(query, images, model=VL_RERANKER, cache=None, batch_size=4):
    """Relevance score for each (query, PNG page) pair, in input order. Pairs are cached one by one.

    Pages go `batch_size` per request: full-size PNGs are ~0.5 MB each in base64 and the
    endpoint rejects large bodies (HTTP 413). Each pair is scored independently, so
    splitting a shortlist across requests does not change its scores.
    """
    cache = cache or Cache()
    keys = [Cache.key(provider="superlinked", model=model, query=digest(query), input=digest(image)) for image in images]
    scores = [cache.get_json(key) for key in keys]
    missing = [i for i, score in enumerate(scores) if score is None]
    headers = {"Authorization": f"Bearer {api_key('SUPERLINKED_API_KEY')}", "Accept": "application/json"}
    for start in range(0, len(missing), batch_size):
        batch = missing[start:start + batch_size]
        payload = {"query": {"text": query},
                   "items": [{"id": str(i), "images": [{"data": base64.b64encode(images[i]).decode(), "format": "png"}]}
                             for i in batch]}
        response, seconds = post_json(SCORE_URL + quote(model, safe=""), payload, headers)
        usage = response.get("usage", {})
        credits = float(usage.get("credits_charged_decimal", usage.get("credits_charged", 0)))
        log_call("superlinked", model, "rerank", len(batch), seconds, credits * USD_PER_CREDIT, usage)
        for row in response["scores"]:
            i = int(row["item_id"])
            scores[i] = row["score"]
            cache.put_json(keys[i], row["score"])
    return scores
