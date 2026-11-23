"""OpenRouter: single-vector embeddings (text or page images) and chat completions.

Every response reports its own cost in usage.cost (OpenRouter credits are US dollars).
"""

import base64
import json

import numpy as np

from evidence_atlas.providers.cache import Cache, digest
from evidence_atlas.providers.http import api_key, in_parallel, log_call, post_json

BASE_URL = "https://openrouter.ai/api/v1"
VOYAGE_MULTIMODAL = "mongodb/voyage-multimodal-3.5"
DEEPSEEK_FLASH = "deepseek/deepseek-v4.1-flash-1017"


def headers():
    return {"Authorization": f"Bearer {api_key('OPEN_ROUTER_KEY')}"}


def content(item):
    """A text or PNG-bytes item as an OpenRouter multimodal input."""
    if isinstance(item, str):
        return {"content": [{"type": "text", "text": item}]}
    url = "data:image/png;base64," + base64.b64encode(item).decode()
    return {"content": [{"type": "image_url", "image_url": {"url": url}}]}


def embed(items, model=VOYAGE_MULTIMODAL, kind="document", cache=None, batch_size=8, workers=8):
    """One float32 vector per item (text or PNG bytes), in input order.

    kind ("query" or "document") labels the call log, so costs can be read back per kind.
    Uncached items are sent in batches, up to `workers` requests at a time.
    """
    cache = cache or Cache()
    keys = [Cache.key(provider="openrouter", model=model, input=digest(item)) for item in items]
    results = [cache.get_array(key) for key in keys]

    def run(batch):
        inputs = [items[i] for i in batch]
        if not all(isinstance(item, str) for item in inputs):
            inputs = [content(item) for item in inputs]
        payload = {"model": model, "input": inputs, "encoding_format": "float"}
        response, seconds = post_json(f"{BASE_URL}/embeddings", payload, headers())
        usage = response.get("usage", {})
        log_call("openrouter", model, kind, len(batch), seconds, usage.get("cost"), usage)
        for row in response["data"]:
            i = batch[row["index"]]
            results[i] = np.asarray(row["embedding"], dtype=np.float32)
            cache.put_array(keys[i], results[i])

    in_parallel(run, [i for i, result in enumerate(results) if result is None], batch_size, workers)
    return results


def rerank(query, documents, model, cache=None):
    """Relevance score for each (query, text document) pair, in input order. Pairs are cached one by one."""
    cache = cache or Cache()
    keys = [Cache.key(provider="openrouter", model=model, query=digest(query), input=digest(d)) for d in documents]
    scores = [cache.get_json(key) for key in keys]
    missing = [i for i, score in enumerate(scores) if score is None]
    if missing:
        payload = {"model": model, "query": query, "documents": [documents[i] for i in missing]}
        response, seconds = post_json(f"{BASE_URL}/rerank", payload, headers())
        usage = response.get("usage", {})
        log_call("openrouter", model, "rerank", len(missing), seconds, usage.get("cost"), usage)
        for row in response["results"]:
            i = missing[row["index"]]
            scores[i] = row["relevance_score"]
            cache.put_json(keys[i], row["relevance_score"])
    return scores


def chat(messages, model=DEEPSEEK_FLASH, cache=None, **params):
    """{"text", "usage"} for one chat completion. Cached, so reruns with identical input are free."""
    cache = cache or Cache()
    params = {"temperature": 0, **params}
    key = Cache.key(provider="openrouter", model=model, params=params,
                    messages=digest(json.dumps(messages, sort_keys=True)))
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    response, seconds = post_json(f"{BASE_URL}/chat/completions", {"model": model, "messages": messages, **params},
                                  headers())
    usage = response.get("usage", {})
    log_call("openrouter", model, "chat", 1, seconds, usage.get("cost"), usage)
    result = {"text": response["choices"][0]["message"].get("content") or "", "usage": usage,
              "served_by": response.get("provider")}
    if result["text"].strip():  # an empty reply (e.g. output budget spent on reasoning) is never cached
        cache.put_json(key, result)
    return result
