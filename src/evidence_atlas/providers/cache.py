"""Disk cache for API results, so the same input is never paid for twice.

A key is a SHA-256 hash of everything that determines the result: provider,
model, settings, and the input itself (image bytes are hashed, not stored).
Vectors are saved as .npy files; chat responses as .json.
"""

import hashlib
import json
from pathlib import Path

import numpy as np

from evidence_atlas.config import ROOT

DEFAULT_ROOT = ROOT / "artifacts" / "cache"


def digest(data):
    """SHA-256 hex of bytes or text."""
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


class Cache:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root)

    @staticmethod
    def key(**parts):
        return digest(json.dumps(parts, sort_keys=True))

    def path(self, key, suffix):
        return self.root / key[:2] / f"{key}{suffix}"

    def write(self, path, save):
        """Write via a temporary file so an interrupted run never leaves a half-written entry."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as f:
            save(f)
        tmp.replace(path)

    def get_array(self, key):
        path = self.path(key, ".npy")
        return np.load(path) if path.exists() else None

    def put_array(self, key, array):
        self.write(self.path(key, ".npy"), lambda f: np.save(f, array))

    def get_json(self, key):
        path = self.path(key, ".json")
        return json.loads(path.read_text()) if path.exists() else None

    def put_json(self, key, value):
        self.write(self.path(key, ".json"), lambda f: f.write(json.dumps(value).encode()))
