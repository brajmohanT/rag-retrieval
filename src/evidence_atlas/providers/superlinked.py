"""Superlinked serverless encoding: ColQwen3 multi-vector embeddings.

One page image -> about 750 vectors of 320 dimensions; one question -> one
vector per token. Score with MaxSim (in the retrieval step).
Billing is in credits; at the list price ($0.20 per 1,000 images), 1 credit = $0.00001.
"""

import base64
from urllib.parse import quote

import numpy as np

from evidence_atlas.providers.cache import Cache, digest
from evidence_atlas.providers.http import api_key, log_call, post_json

BASE_URL = "https://api.superlinked.com/v1/encode/"
COLQWEN3 = "TomoroAI/tomoro-colqwen3-embed-4b:compact"
USD_PER_CREDIT = 0.00001


def encode(items, is_query, model=COLQWEN3, cache=None, batch_size=8):
    """Multi-vectors for texts (questions) or PNG bytes (pages), in input order.

    Returns a list of float32 arrays shaped [vectors, dimensions].
    """
    cache = cache or Cache()
    keys = [Cache.key(provider="superlinked", model=model, is_query=is_query, input=digest(item)) for item in items]
    results = [cache.get_array(key) for key in keys]
    missing = [i for i, result in enumerate(results) if result is None]
    for start in range(0, len(missing), batch_size):
        batch = missing[start:start + batch_size]
        vectors = request(model, [items[i] for i in batch], is_query)
        for i, array in zip(batch, vectors):
            cache.put_array(keys[i], array)
            results[i] = array
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
