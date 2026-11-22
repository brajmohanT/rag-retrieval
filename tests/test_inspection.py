"""Run: uv run pytest"""
from pathlib import Path
import unittest
import tempfile
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image

from evidence_atlas.data import inspection as module


class InspectionTests(unittest.TestCase):
    def fixture(self):
        return (
            [{"corpus_id": 42, "doc_id": "doc", "page_number_in_doc": 0, "markdown": "text"}],
            [{"query_id": 99, "query": "Question?", "answer": "Answer"}],
            [{"query_id": 99, "corpus_id": 42, "score": 2, "bounding_boxes": [{"annotator": 0, "x1": 1, "y1": 2, "x2": 3, "y2": 4}]}],
            [{"doc_id": "doc"}],
        )

    def test_non_contiguous_ids_join(self):
        errors, warnings = module.check_records(*self.fixture())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_page_and_invalid_grade(self):
        pages, queries, qrels, docs = self.fixture()
        qrels[0].update(corpus_id=123, score=9)
        errors, _ = module.check_records(pages, queries, qrels, docs)
        self.assertTrue(any("Unresolved qrel" in x for x in errors))
        self.assertTrue(any("Unexpected relevance" in x for x in errors))

    def test_duplicate_query_and_missing_qrels(self):
        pages, queries, qrels, docs = self.fixture()
        queries.append(dict(queries[0]))
        errors, _ = module.check_records(pages, queries, [], docs)
        self.assertTrue(any("Duplicate query_id" in x for x in errors))
        self.assertTrue(any("without qrels" in x for x in errors))

    def test_missing_markdown_is_warning(self):
        pages, queries, qrels, docs = self.fixture()
        pages[0]["markdown"] = None
        errors, warnings = module.check_records(pages, queries, qrels, docs)
        self.assertEqual(errors, [])
        self.assertTrue(any("Empty Markdown" in x for x in warnings))

    def test_box_boundaries(self):
        self.assertTrue(module.valid_box({"x1": 0, "y1": 0, "x2": 100, "y2": 200}, 100, 200))
        for box in [
            {"x1": -1, "y1": 0, "x2": 10, "y2": 20},
            {"x1": 10, "y1": 0, "x2": 10, "y2": 20},
            {"x1": 0, "y1": 0, "x2": 101, "y2": 20},
            {},
        ]:
            self.assertFalse(module.valid_box(box, 100, 200))

    def test_html_export_escapes_text_and_preserves_ids(self):
        pages, queries, qrels, docs = self.fixture()
        queries[0].update(language="english", query_types=["extractive"], raw_answers=[])
        pages[0]["markdown"] = "<script>not executable</script>"
        docs[0].update(file_name="doc.pdf", license="cc-by-4.0")
        stream = BytesIO()
        Image.new("RGB", (100, 200), "white").save(stream, format="PNG")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "corpus").mkdir()
            pq.write_table(pa.Table.from_pylist([
                {"corpus_id": 42, "image": {"bytes": stream.getvalue()}}
            ]), root / "corpus/test.parquet")
            output = root / "artifacts/inspection/99"
            path = module.render_view(root, output, queries[0], qrels, pages, docs,
                                      {"errors": [], "warnings": [], "revision": "test"})
            html = path.read_text()
            self.assertIn("&lt;script&gt;not executable&lt;/script&gt;", html)
            self.assertNotIn("<script>", html)
            self.assertIn('<svg ', html)
            self.assertIn('href="page-42.png"', html)
            self.assertIn("#page=1", html)
            self.assertTrue((output / "page-42.png").is_file())
            self.assertEqual((output / "page-42.md").read_text(), pages[0]["markdown"])

    def test_relative_url_encodes_spaces(self):
        self.assertEqual(module.relative_url(Path('/tmp/a b.pdf'), Path('/tmp/view')), '../a%20b.pdf')


if __name__ == '__main__':
    unittest.main()
