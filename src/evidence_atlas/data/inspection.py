"""Audit the local HR dataset and export one query's gold evidence as HTML.

Run: uv run atlas-inspect --query-id 0
No network calls, embeddings, or model inference.
"""

import argparse
from collections import Counter
from html import escape
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
from pypdf import PdfReader

from evidence_atlas.config import load_config

CSS = Path(__file__).with_name("inspection.css")


def load_rows(root, config, columns=None):
    paths = sorted((root / config).glob("*.parquet"))
    if not paths:
        raise ValueError(f"No Parquet files in {root / config}")
    return pa.concat_tables([pq.read_table(p, columns=columns) for p in paths]).to_pylist()


def duplicate_values(values):
    return [value for value, count in Counter(values).items() if count > 1]


def valid_box(box, width, height):
    try:
        return 0 <= box["x1"] < box["x2"] <= width and 0 <= box["y1"] < box["y2"] <= height
    except (KeyError, TypeError):
        return False


def check_records(pages, queries, qrels, documents):
    """Check joins without assuming that IDs equal row positions."""
    errors, warnings = [], []
    for label, values in [
        ("corpus_id", [p["corpus_id"] for p in pages]),
        ("query_id", [q["query_id"] for q in queries]),
        ("document doc_id", [d["doc_id"] for d in documents]),
        ("document/page", [(p["doc_id"], p["page_number_in_doc"]) for p in pages]),
        ("qrel pair", [(r["query_id"], r["corpus_id"]) for r in qrels]),
    ]:
        duplicates = duplicate_values(values)
        if duplicates:
            errors.append(f"Duplicate {label}: {duplicates[:10]}")
    page_ids = {p["corpus_id"] for p in pages}
    query_ids = {q["query_id"] for q in queries}
    doc_ids = {d["doc_id"] for d in documents}
    for r in qrels:
        if r["query_id"] not in query_ids or r["corpus_id"] not in page_ids:
            errors.append(f"Unresolved qrel: query={r['query_id']}, page={r['corpus_id']}")
        if r["score"] not in (1, 2):
            errors.append(f"Unexpected relevance grade: {r['score']}")
    missing_docs = {p["doc_id"] for p in pages} - doc_ids
    if missing_docs:
        errors.append(f"Pages without document metadata: {sorted(missing_docs)}")
    no_qrels = query_ids - {r["query_id"] for r in qrels}
    if no_qrels:
        errors.append(f"Queries without qrels: {sorted(no_qrels)}")
    for field in ("query", "answer"):
        missing = [q["query_id"] for q in queries if not (q.get(field) or "").strip()]
        if missing:
            warnings.append(f"Empty {field}: {len(missing)} queries; examples {missing[:10]}")
    empty_md = [p["corpus_id"] for p in pages if not (p.get("markdown") or "").strip()]
    if empty_md:
        warnings.append(f"Empty Markdown: {len(empty_md)} pages; examples {empty_md[:10]}")
    no_boxes = sum(not r.get("bounding_boxes") for r in qrels)
    if no_boxes:
        warnings.append(f"Qrels without evidence boxes: {no_boxes}")
    return errors, warnings


def audit(root, pages, queries, qrels, documents):
    errors, warnings = check_records(pages, queries, qrels, documents)
    boxes_by_page = {}
    for r in qrels:
        boxes_by_page.setdefault(r["corpus_id"], []).extend(r.get("bounding_boxes") or [])
    dimensions = {}
    # Decode every embedded image in small batches rather than loading 442 MB at once.
    for path in sorted((root / "corpus").glob("*.parquet")):
        for batch in pq.ParquetFile(path).iter_batches(batch_size=16, columns=["corpus_id", "image"]):
            for row in batch.to_pylist():
                page_id = row["corpus_id"]
                try:
                    with Image.open(BytesIO(row["image"]["bytes"])) as image:
                        image.load()
                        dimensions[page_id] = image.size
                except Exception as exc:
                    errors.append(f"Unreadable image {page_id}: {exc}")
    bad_boxes = []
    for page_id, boxes in boxes_by_page.items():
        if page_id in dimensions:
            bad_boxes.extend({"corpus_id": page_id, "box": b} for b in boxes
                             if not valid_box(b, *dimensions[page_id]))
    if bad_boxes:
        warnings.append(f"Out-of-bounds or malformed boxes: {len(bad_boxes)}; no automatic clipping")

    pdf_counts = {}
    for d in documents:
        path = root / "pdfs" / d["file_name"]
        try:
            count = len(PdfReader(path).pages)
            pdf_counts[d["doc_id"]] = count
            if count != d["page_number"]:
                warnings.append(f"PDF/metadata page count differs: {d['doc_id']}: {count} vs {d['page_number']}")
        except Exception as exc:
            errors.append(f"Unreadable or missing PDF {d['file_name']}: {exc}")
        if not d.get("license"):
            warnings.append(f"Missing license: {d['doc_id']}")
    for p in pages:
        count = pdf_counts.get(p["doc_id"])
        # This pinned corpus uses zero-based PDF page indices (including covers).
        if count is not None and not 0 <= p["page_number_in_doc"] < count:
            errors.append(f"Page index outside PDF: corpus_id={p['corpus_id']}")
    manifest_path = root / "download_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return {
        "revision": manifest.get("revision"),
        "counts": {"pages": len(pages), "documents": len(documents), "queries": len(queries),
                   "english_queries": sum(q["language"] == "english" for q in queries),
                   "qrels": len(qrels), "decoded_images": len(dimensions), "readable_pdfs": len(pdf_counts)},
        "query_languages": dict(Counter(q["language"] for q in queries)),
        "relevance_grades": dict(Counter(r["score"] for r in qrels)),
        "errors": errors, "warnings": warnings, "invalid_boxes": bad_boxes,
        "scope": "Structural checks only. Humans must inspect answer support, OCR fidelity, and box alignment.",
    }


def relative_url(path, start):
    return quote(os.path.relpath(path, start), safe="/")


def render_view(root, output, query, qrels, pages, documents, report):
    output.mkdir(parents=True, exist_ok=True)
    page_by_id = {p["corpus_id"]: p for p in pages}
    doc_by_id = {d["doc_id"]: d for d in documents}
    relevant = sorted((r for r in qrels if r["query_id"] == query["query_id"]),
                      key=lambda r: (-r["score"], r["corpus_id"]))
    ids = [r["corpus_id"] for r in relevant]
    images = {}
    for path in sorted((root / "corpus").glob("*.parquet")):
        table = pq.read_table(path, columns=["corpus_id", "image"], filters=[("corpus_id", "in", ids)])
        images.update({r["corpus_id"]: r["image"]["bytes"] for r in table.to_pylist()})
    sections = []
    for r in relevant:
        p = page_by_id[r["corpus_id"]]
        doc = doc_by_id[p["doc_id"]]
        stem = f"page-{p['corpus_id']}"
        with Image.open(BytesIO(images[p["corpus_id"]])) as image:
            image.save(output / f"{stem}.png")
            width, height = image.size
        md_path = output / f"{stem}.md"
        md_path.write_text(p.get("markdown") or "", encoding="utf-8")
        rects = []
        for b in r.get("bounding_boxes") or []:
            if valid_box(b, width, height):
                rects.append(f'<rect x="{b["x1"]}" y="{b["y1"]}" width="{b["x2"] - b["x1"]}" '
                             f'height="{b["y2"] - b["y1"]}"><title>Annotator {b["annotator"]}</title></rect>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
               f'role="img" aria-label="Evidence page {p["corpus_id"]} with annotated regions">'
               f'<image href="{stem}.png" width="{width}" height="{height}"/>'
               f'<g fill="none" stroke="#b00040" stroke-width="4">{"".join(rects)}</g></svg>')
        (output / f"{stem}.svg").write_text(svg)
        pdf_url = relative_url(root / "pdfs" / doc["file_name"], output)
        pdf_page = p["page_number_in_doc"] + 1
        label = "Complete-answer page" if r["score"] == 2 else "Contributing evidence; needs additional information"
        sections.append(f'''<section>
<h2>Page ID {p['corpus_id']} · Grade {r['score']}</h2>
<p>{label}</p><p>{escape(p['doc_id'])}<br>
Dataset page index: {p['page_number_in_doc']} (zero-based); PDF viewer page: {pdf_page}.
<a href="{pdf_url}#page={pdf_page}">Open original PDF</a> |
<a href="{stem}.png">Original image</a> | <a href="{stem}.md">Raw Markdown</a></p>
<p>License: {escape(doc.get('license') or 'Not specified')}. Evidence boxes: {len(r.get('bounding_boxes') or [])}.</p>
<div class="evidence"><figure><figcaption>Page image with gold evidence boxes</figcaption>
{svg}</figure>
<div><h3>OCR-derived Markdown</h3><pre>{escape(p.get('markdown') or '[No Markdown]')}</pre></div></div>
</section>''')
    css = relative_url(CSS, output)
    audit_url = relative_url(output.parent.parent / "dataset_audit.json", output)
    raw_answers = "".join(f"<li>{escape(a)}</li>" for a in query.get("raw_answers") or [])
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Inspect a benchmark question, its reference answer, and annotated source pages beside OCR text.">
<title>Query {query['query_id']} evidence inspection</title><link rel="stylesheet" href="{css}"></head>
<body><main>
<header><h1>Query {query['query_id']}: evidence inspection</h1>
<p>Gold labels, not retrieval results. Inspect source support before indexing.</p></header>
<h2>{escape(query['query'])}</h2>
<p>Language: {escape(query['language'])}. Types: {escape(', '.join(query['query_types']))}.</p>
<h3>Reference answer</h3><p>{escape(query.get('answer') or '[Missing]')}</p>
<details><summary>Original annotator answers</summary><ul>{raw_answers}</ul></details>
<p>{len(relevant)} labeled pages. Grade 2 means a complete answer; grade 1 means contributing evidence.
Alternative complete-answer pages need not all appear in a retrieval result.</p>
<p>Audit: {len(report['errors'])} errors, {len(report['warnings'])} warnings.
<a href="{audit_url}">Read structural audit</a>. Humans still need to check answer correctness and OCR fidelity.</p>
{''.join(sections)}
<footer>Revision: {escape(report.get('revision') or 'unknown')}. Boxes use original image-pixel coordinates.
Invalid boxes stay in the audit; this viewer does not draw or clip them.</footer>
</main></body></html>'''
    (output / "index.html").write_text(document, encoding="utf-8")
    (output / "query.json").write_text(json.dumps({"query": query, "qrels": relevant}, indent=2, ensure_ascii=False) + "\n")
    return output / "index.html"


def main():
    config = load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-id", type=int, default=0)
    parser.add_argument("--data-dir", type=Path, default=config["dataset"]["data_dir"])
    parser.add_argument("--output-dir", type=Path, default=config["artifacts_dir"])
    args = parser.parse_args()
    root, artifacts = args.data_dir.resolve(), args.output_dir.resolve()
    try:
        pages = load_rows(root, "corpus", ["corpus_id", "doc_id", "page_number_in_doc", "markdown"])
        queries = load_rows(root, "queries")
        qrels = load_rows(root, "qrels")
        documents = load_rows(root, "documents_metadata")
        query = next((q for q in queries if q["query_id"] == args.query_id), None)
        if query is None:
            raise ValueError(f"Unknown query ID {args.query_id}")
        report = audit(root, pages, queries, qrels, documents)
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "dataset_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(report["counts"], indent=2))
        for message in report["errors"]:
            print(f"ERROR: {message}", file=sys.stderr)
        for message in report["warnings"]:
            print(f"WARNING: {message}", file=sys.stderr)
        if report["errors"]:
            return 1
        output = artifacts / "inspection" / str(args.query_id)
        path = render_view(root, output, query, qrels, pages, documents, report)
        print(f"Viewer: {path}")
        print("Structural checks complete. Answer support still needs human review.")
        return 0
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Inspection failed: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
