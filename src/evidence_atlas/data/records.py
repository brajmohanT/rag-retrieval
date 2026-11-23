"""Typed records for the ViDoRe V3 HR corpus, keyed by the dataset's own IDs.

Page images stay in the corpus Parquet file; only the columns needed for
retrieval and evaluation are loaded here.
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


@dataclass(frozen=True)
class Document:
    doc_id: str
    file_name: str
    url: str
    doc_type: str
    year: int
    visual_types: tuple[str, ...]
    license: str


@dataclass(frozen=True)
class Page:
    page_id: int  # dataset corpus_id
    doc_id: str
    page_number: int  # zero-based; the PDF viewer page is page_number + 1
    markdown: str  # empty when the dataset has no extracted text


@dataclass(frozen=True)
class Query:
    query_id: int
    language: str
    text: str
    answer: str
    query_types: tuple[str, ...]
    query_format: str
    content_type: tuple[str, ...]
    source_type: str


@dataclass(frozen=True)
class Box:
    annotator: int
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class Relevance:
    query_id: int
    page_id: int
    grade: int  # 2: complete answer; 1: required evidence needing other pages
    content_type: tuple[str, ...]
    boxes: tuple[Box, ...]  # kept as published, including malformed boxes


@dataclass
class Dataset:
    documents: dict[str, Document]
    pages: dict[int, Page]
    queries: dict[int, Query]
    qrels: dict[int, list[Relevance]]  # query_id -> judged pages, best grade first


def load_rows(root, config, columns=None):
    paths = sorted((Path(root) / config).glob("*.parquet"))
    if not paths:
        raise ValueError(f"No Parquet files in {Path(root) / config}")
    return pa.concat_tables([pq.read_table(p, columns=columns) for p in paths]).to_pylist()


def load_page_images(root, page_ids):
    """page_id -> PNG bytes, reading only the requested rows."""
    images = {}
    for path in sorted((Path(root) / "corpus").glob("*.parquet")):
        table = pq.read_table(path, columns=["corpus_id", "image"], filters=[("corpus_id", "in", list(page_ids))])
        images.update({row["corpus_id"]: row["image"]["bytes"] for row in table.to_pylist()})
    return images


def load_dataset(root, languages=("english",)):
    """Load records; keep only queries (and their qrels) in the given languages."""
    documents = {
        d["doc_id"]: Document(d["doc_id"], d["file_name"], d["url"], d["doc_type"], d["doc_year"],
                              tuple(d["visual_types"] or ()), d["license"] or "")
        for d in load_rows(root, "documents_metadata")
    }
    pages = {
        p["corpus_id"]: Page(p["corpus_id"], p["doc_id"], p["page_number_in_doc"], p["markdown"] or "")
        for p in load_rows(root, "corpus", ["corpus_id", "doc_id", "page_number_in_doc", "markdown"])
    }
    queries = {
        q["query_id"]: Query(q["query_id"], q["language"], q["query"], q["answer"] or "",
                             tuple(q["query_types"] or ()), q["query_format"],
                             tuple(q["content_type"] or ()), q["source_type"])
        for q in load_rows(root, "queries") if q["language"] in languages
    }
    qrels = defaultdict(list)
    for r in load_rows(root, "qrels"):
        if r["query_id"] in queries:
            boxes = tuple(Box(**b) for b in r["bounding_boxes"] or ())
            qrels[r["query_id"]].append(
                Relevance(r["query_id"], r["corpus_id"], r["score"], tuple(r["content_type"] or ()), boxes))
    for judged in qrels.values():
        judged.sort(key=lambda r: (-r.grade, r.page_id))
    return Dataset(documents, pages, queries, dict(qrels))
