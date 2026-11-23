"""HTTP for paid APIs: keys from .env, retries, and a log of every billed call.

Keys are read from the environment (loaded from .env) and only ever sent in
request headers. They are never logged or written to disk.
"""

from datetime import datetime, timezone
import json
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time

from dotenv import load_dotenv
import httpx

from evidence_atlas.config import ROOT

load_dotenv(ROOT / ".env")
CALL_LOG = ROOT / "artifacts" / "api_calls.jsonl"
RETRY_STATUS = {429, 500, 502, 503, 504}
LOG_LOCK = threading.Lock()  # requests run in parallel threads


def api_key(name):
    key = os.environ.get(name)
    if not key:
        raise RuntimeError(f"{name} is not set; add it to .env")
    return key


def retry_delay(response, attempt):
    """Seconds to wait: the server's Retry-After if numeric, else 1, 2, 4, 8... s."""
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return 2 ** attempt


def post_json(url, payload, headers, attempts=5, timeout=180):
    """POST JSON and return (response JSON, seconds). Retries rate limits, server errors, and network errors."""
    for attempt in range(attempts):
        last = attempt == attempts - 1
        start = time.perf_counter()
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        except httpx.TransportError:
            if last:
                raise
            time.sleep(2 ** attempt)
            continue
        seconds = time.perf_counter() - start
        if response.status_code in RETRY_STATUS and not last:
            time.sleep(retry_delay(response, attempt))
            continue
        if response.is_error:
            raise RuntimeError(f"{url} returned {response.status_code}: {response.text[:500]}")
        return response.json(), seconds


def log_call(provider, model, kind, items, seconds, cost_usd, usage=None):
    """Append one billed call to artifacts/api_calls.jsonl. cost_usd is None when unknown."""
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "provider": provider,
              "model": model, "kind": kind, "items": items, "seconds": round(seconds, 3),
              "cost_usd": cost_usd, "usage": usage}
    with LOG_LOCK, open(CALL_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def logged_calls(model, kind):
    """Every logged call for a model and kind. The cache means each input is paid for once,
    so these sum to the true cost of everything encoded so far, even after cached reruns."""
    if not CALL_LOG.exists():
        return []
    calls = [json.loads(line) for line in CALL_LOG.read_text().splitlines()]
    return [c for c in calls if c["model"] == model and c["kind"] == kind]


def in_parallel(run, indices, batch_size, workers):
    """Call run(batch) for each batch of indices, up to `workers` at a time. Re-raises the first error."""
    batches = [indices[i:i + batch_size] for i in range(0, len(indices), batch_size)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(run, batch) for batch in batches]:
            future.result()
