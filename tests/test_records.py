import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from evidence_atlas.config import load_config
from evidence_atlas.data.records import Box, load_dataset


def write(root, config, rows):
    (root / config).mkdir()
    pq.write_table(pa.Table.from_pylist(rows), root / config / "test.parquet")


def query(query_id, language):
    return {"query_id": query_id, "language": language, "query": "Q?", "answer": "A",
            "query_types": ["extractive"], "query_format": "question", "content_type": ["Table"],
            "source_type": "image", "raw_answers": ["A"]}


def qrel(query_id, corpus_id, score, boxes=None):
    return {"query_id": query_id, "corpus_id": corpus_id, "score": score,
            "content_type": ["Table"], "bounding_boxes": boxes or []}


@pytest.fixture
def root(tmp_path):
    write(tmp_path, "documents_metadata", [{
        "file_name": "doc.pdf", "doc_id": "doc", "url": "https://example.org/doc.pdf", "doc_type": "report",
        "doc_language": "english", "doc_year": 2024, "visual_types": ["Table"], "page_number": 2,
        "license": "cc-by-4.0"}])
    write(tmp_path, "corpus", [
        {"corpus_id": 7, "image": {"bytes": b""}, "doc_id": "doc", "markdown": "page text", "page_number_in_doc": 0},
        {"corpus_id": 3, "image": {"bytes": b""}, "doc_id": "doc", "markdown": None, "page_number_in_doc": 1},
    ])
    write(tmp_path, "queries", [query(10, "english"), query(11, "french")])
    write(tmp_path, "qrels", [
        qrel(10, 7, 1),
        qrel(10, 3, 2, [{"annotator": 0, "x1": 1, "x2": 5, "y1": 2, "y2": 6}]),
        qrel(11, 7, 2),
    ])
    return tmp_path


def test_load_keeps_ids_and_fills_missing_markdown(root):
    data = load_dataset(root)
    assert set(data.pages) == {3, 7}
    assert data.pages[7].markdown == "page text"
    assert data.pages[3].markdown == ""
    assert data.documents["doc"].license == "cc-by-4.0"


def test_filters_language_with_its_qrels(root):
    data = load_dataset(root)
    assert set(data.queries) == {10}
    assert set(data.qrels) == {10}
    assert set(load_dataset(root, languages=("english", "french")).queries) == {10, 11}


def test_qrels_sorted_best_grade_first_with_boxes(root):
    judged = load_dataset(root).qrels[10]
    assert [(r.page_id, r.grade) for r in judged] == [(3, 2), (7, 1)]
    assert judged[0].boxes == (Box(annotator=0, x1=1, y1=2, x2=5, y2=6),)


def test_real_dataset_counts():
    data_dir = load_config()["dataset"]["data_dir"]
    if not data_dir.exists():
        pytest.skip("dataset not downloaded")
    data = load_dataset(data_dir)
    assert (len(data.documents), len(data.pages), len(data.queries)) == (14, 1110, 318)
    assert set(data.qrels) == set(data.queries)
    assert all(r.page_id in data.pages for judged in data.qrels.values() for r in judged)
