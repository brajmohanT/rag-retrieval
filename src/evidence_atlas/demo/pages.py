"""Export page images for the demo: a thumbnail and a readable large version of every page, as WebP.

Run: uv run atlas-export-pages
Writes artifacts/demo/pages/<page_id>-thumb.webp and <page_id>-large.webp, plus
sizes.json with each page's original pixel size (evidence boxes use original pixels).
"""

from io import BytesIO
import json
import sys

from PIL import Image

from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_page_images, load_rows

SIZES = {"thumb": (320, 70), "large": (1100, 82)}  # name -> (width in pixels, WebP quality)


def export(png, out_dir, page_id):
    with Image.open(BytesIO(png)) as image:
        original = image.size
        rgb = image.convert("RGB")
        for name, (width, quality) in SIZES.items():
            height = round(original[1] * width / original[0])
            rgb.resize((width, height), Image.Resampling.LANCZOS).save(
                out_dir / f"{page_id}-{name}.webp", "WEBP", quality=quality, method=6)
    return original


def main():
    config = load_config()
    root = config["dataset"]["data_dir"]
    out_dir = config["artifacts_dir"] / "demo" / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    page_ids = sorted(row["corpus_id"] for row in load_rows(root, "corpus", ["corpus_id"]))
    sizes = {}
    for start in range(0, len(page_ids), 100):  # 100 pages at a time keeps memory low
        batch = page_ids[start:start + 100]
        for page_id, png in load_page_images(root, batch).items():
            sizes[page_id] = export(png, out_dir, page_id)
        print(f"  {min(start + 100, len(page_ids))}/{len(page_ids)} pages")
    (out_dir / "sizes.json").write_text(json.dumps(sizes))
    total = sum(f.stat().st_size for f in out_dir.glob("*.webp"))
    print(f"Wrote {2 * len(sizes)} images to {out_dir} ({total / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
