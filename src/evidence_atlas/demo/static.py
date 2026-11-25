"""Export the demo as a static site: the built frontend, every API response as a JSON file, and the page images.

Run: uv run atlas-export-static   (writes site/; --out elsewhere)
Serve site/ from any static host, also under a sub-path such as GitHub Pages' /<repo>/. Each JSON file is
the live API's response byte for byte; a question file holds lanes for all configurations and the frontend
keeps the requested ones.
"""

import argparse
import os
import shutil
import subprocess
import sys

from fastapi.testclient import TestClient

from evidence_atlas.api.app import create_app
from evidence_atlas.config import ROOT, load_config
from evidence_atlas.data.records import load_dataset


def export_json(app, out_dir, page_ids):
    """Write api/<route>.json for every GET the frontend makes; returns the bytes written."""
    client = TestClient(app)
    total = 0

    def save(route, params=None):
        nonlocal total
        response = client.get(route, params=params)
        response.raise_for_status()
        path = out_dir / f"{route.lstrip('/')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        total += len(response.content)
        return response.json()

    save("/api/meta")
    save("/api/showcase")
    config_ids = [c["id"] for c in save("/api/configs")]
    for q in save("/api/questions"):
        save(f"/api/questions/{q['query_id']}", {"configs": ",".join(config_ids)})
    for page_id in page_ids:
        save(f"/api/pages/{page_id}")
    return total


def build_frontend(out_dir):
    web = ROOT / "web"
    if not (web / "node_modules").exists():
        subprocess.run(["npm", "ci"], cwd=web, check=True)
    subprocess.run(["npm", "run", "build", "--", "--outDir", str(out_dir), "--emptyOutDir"], cwd=web, check=True,
                   env={**os.environ, "VITE_STATIC": "1"})


def copy_images(pages_dir, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for image in sorted(pages_dir.glob("*.webp")):
        shutil.copyfile(image, out_dir / image.name)
        total += image.stat().st_size
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "site"), help="output directory (emptied first)")
    out_dir = ROOT / parser.parse_args().out  # absolute paths stay as given
    if out_dir.exists() and any(out_dir.iterdir()) and not (out_dir / "index.html").exists():
        parser.error(f"{out_dir} is not empty and holds no earlier export; refusing to empty it")

    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    app = create_app(data=data)  # fails early when the grid or dataset is missing, before the slow build
    build_frontend(out_dir)
    json_bytes = export_json(app, out_dir, sorted(data.pages))
    image_bytes = copy_images(config["artifacts_dir"] / "demo" / "pages", out_dir / "page-images")
    (out_dir / ".nojekyll").touch()  # GitHub Pages: serve files as they are
    print(f"Wrote {out_dir}: JSON {json_bytes / 1e6:.1f} MB, page images {image_bytes / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
