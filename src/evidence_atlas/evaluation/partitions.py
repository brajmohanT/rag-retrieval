"""Freeze development and held-out question IDs.

Run once: uv run python -m evidence_atlas.evaluation.partitions
The file is committed and never regenerated; tune on "dev", report on "heldout".
"""

from collections import defaultdict
import json
import random
import sys

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset


def make_partitions(queries, dev_fraction, seed):
    """Split query IDs, stratified by question-type combination."""
    strata = defaultdict(list)
    for query in queries.values():
        strata[tuple(sorted(query.query_types))].append(query.query_id)
    rng = random.Random(seed)
    dev, heldout = [], []
    for key in sorted(strata):
        ids = sorted(strata[key])
        rng.shuffle(ids)
        cut = round(len(ids) * dev_fraction)
        dev += ids[:cut]
        heldout += ids[cut:]
    return {"dev": sorted(dev), "heldout": sorted(heldout)}


def load_partitions(path):
    return json.loads(path.read_text())


def main():
    config = load_config()
    settings = config["evaluation"]
    path = settings["partitions_file"]
    if path.exists():
        print(f"{path} already exists; partitions are frozen.", file=sys.stderr)
        return 1
    data = load_dataset(config["dataset"]["data_dir"])
    partitions = make_partitions(data.queries, settings["dev_fraction"], settings["seed"])
    record = {"dataset_revision": config["dataset"]["revision"], "language": "english",
              "dev_fraction": settings["dev_fraction"], "seed": settings["seed"], **partitions}
    path.write_text(json.dumps(record, indent=1) + "\n")
    print(f"Wrote {path}: {len(partitions['dev'])} dev, {len(partitions['heldout'])} held-out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
