import numpy as np
import pytest

from evidence_atlas.providers import http
from evidence_atlas.retrieval.dense import DenseIndex, normalize
from evidence_atlas.retrieval.run_dense import query_text


def test_cosine_ranking_ignores_vector_length():
    index = DenseIndex({1: [1, 0], 2: [10, 10], 3: [0, 5]})
    results = index.search(np.array([1.0, 0.2]))
    assert [page for page, _ in results] == [1, 2, 3]
    assert results[0][1] == pytest.approx(1 / np.sqrt(1.04))  # cos([1,0],[1,0.2])


def test_ties_break_by_page_id_and_k_limits():
    index = DenseIndex({7: [1, 0], 3: [1, 0], 5: [0, 1]})
    assert [page for page, _ in index.search([1, 0], k=2)] == [3, 7]


def test_normalize_gives_unit_vectors():
    assert np.linalg.norm(normalize([[3, 4]]), axis=1).tolist() == pytest.approx([1.0])


def test_query_text_follows_qwen_instruction_format():
    assert query_text("What changed?").startswith("Instruct: ")
    assert query_text("What changed?").endswith("\nQuery:What changed?")


def test_logged_calls_filters_by_model_and_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CALL_LOG", tmp_path / "calls.jsonl")
    assert http.logged_calls("m", "query") == []
    http.log_call("p", "m", "query", 1, 0.5, 0.001)
    http.log_call("p", "m", "document", 8, 2.0, 0.01)
    http.log_call("p", "other", "query", 1, 0.5, 0.001)
    calls = http.logged_calls("m", "query")
    assert len(calls) == 1 and calls[0]["cost_usd"] == 0.001
