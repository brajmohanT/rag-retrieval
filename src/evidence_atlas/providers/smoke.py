"""Check every provider end to end with one question and one page.

Run: uv run atlas-smoke
The first run makes a few paid calls (well under $0.01); a second run is served
from the cache and costs $0.
"""

import json
import sys

import numpy as np

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset, load_page_images
from evidence_atlas.providers import openrouter, superlinked
from evidence_atlas.providers.http import CALL_LOG

QUERY_ID, PAGE_ID = 0, 485  # page 485 holds query 0's decisive evidence
UNRELATED_PAGE_ID = 34  # a page with no judged relevance to query 0


def logged_calls():
    return CALL_LOG.read_text().splitlines() if CALL_LOG.exists() else []


def maxsim(query, page):
    """Late interaction: each query vector takes its best-matching page vector; sum those maxima."""
    return float((query @ page.T).max(axis=1).sum())


def cosine(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    question = data.queries[QUERY_ID].text
    images = load_page_images(config["dataset"]["data_dir"], [PAGE_ID, UNRELATED_PAGE_ID])
    before = len(logged_calls())

    q_mv, = superlinked.encode([question], is_query=True)
    page_mv, other_mv = superlinked.encode([images[PAGE_ID], images[UNRELATED_PAGE_ID]], is_query=False)
    print(f"Superlinked ColQwen3: question {q_mv.shape}, page {page_mv.shape}")
    print(f"  MaxSim relevant page {maxsim(q_mv, page_mv):.2f} vs unrelated page {maxsim(q_mv, other_mv):.2f}")

    q_vec, page_vec, other_vec = openrouter.embed([question, images[PAGE_ID], images[UNRELATED_PAGE_ID]])
    print(f"OpenRouter Voyage multimodal: vectors {q_vec.shape}")
    print(f"  cosine relevant page {cosine(q_vec, page_vec):.3f} vs unrelated page {cosine(q_vec, other_vec):.3f}")

    reply = openrouter.chat([{"role": "user", "content": "Reply with exactly one word: ready"}], max_tokens=50)
    print(f"OpenRouter DeepSeek chat: {reply['text']!r} (served by {reply['served_by']})")

    new = [json.loads(line) for line in logged_calls()[before:]]
    cost = sum(call["cost_usd"] or 0 for call in new)
    print(f"\nPaid calls this run: {len(new)}, cost ${cost:.6f}" + ("" if new else " (all served from cache)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
