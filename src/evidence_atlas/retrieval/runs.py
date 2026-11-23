"""Save and load retrieval runs in one format for every method.

artifacts/runs/<name>/
    run.json        method, settings, dataset revision, timings, cost
    rankings.jsonl  one line per question: {"query_id", "pages", "scores"}, best first
"""

from datetime import datetime, timezone
import json
from math import ceil
from pathlib import Path


def percentile(values, q):
    """Nearest-rank percentile, q in [0, 100]."""
    ordered = sorted(values)
    return ordered[max(0, ceil(q / 100 * len(ordered)) - 1)]


def latency_summary(seconds):
    ms = [s * 1000 for s in seconds]
    return {"p50_ms": percentile(ms, 50), "p95_ms": percentile(ms, 95), "n": len(ms)}


def save_run(run_dir, results, meta):
    """results: query_id -> [(page_id, score), ...] best first."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n")
    with open(run_dir / "rankings.jsonl", "w") as f:
        for query_id in sorted(results):
            pages = [page for page, _ in results[query_id]]
            scores = [round(score, 6) for _, score in results[query_id]]
            f.write(json.dumps({"query_id": query_id, "pages": pages, "scores": scores}) + "\n")
    return run_dir


def load_run(run_dir):
    """(meta, rankings) with rankings: query_id -> [page_id, ...] best first."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_text())
    rankings = {}
    with open(run_dir / "rankings.jsonl") as f:
        for line in f:
            row = json.loads(line)
            rankings[row["query_id"]] = row["pages"]
    return meta, rankings
