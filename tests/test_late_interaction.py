import numpy as np
import pytest

from evidence_atlas.providers import http
from evidence_atlas.retrieval.api_run import cost_per_item
from evidence_atlas.retrieval.late_interaction import MaxSimIndex


def test_hand_calculated_maxsim():
    # Page 1 has patches e1 and e2; page 2 has one patch halfway between them.
    half = np.array([1, 1]) / np.sqrt(2)
    index = MaxSimIndex({1: np.array([[1.0, 0], [0, 1]]), 2: np.array([half])})
    query = np.array([[1.0, 0], [0, 1]])  # two query tokens: e1, e2
    # Page 1: each token finds an exact match -> 1 + 1 = 2. Page 2: each token's best is 0.707 -> 1.414.
    assert index.scores(query).tolist() == pytest.approx([2.0, np.sqrt(2)])
    assert [page for page, _ in index.search(query)] == [1, 2]


def test_pages_with_different_vector_counts_stay_separate():
    index = MaxSimIndex({5: np.array([[0.0, 1]]), 9: np.array([[1.0, 0], [0.6, 0.8], [0, 1]])})
    # A query matching only page 9's middle patch must not leak into page 5's score.
    scores = index.scores(np.array([[0.6, 0.8]]))
    assert scores.tolist() == pytest.approx([0.8, 1.0])


def test_cost_per_item_uses_logged_items(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CALL_LOG", tmp_path / "calls.jsonl")
    assert cost_per_item("m", "document") == 0.0
    http.log_call("p", "m", "document", 4, 1.0, 0.004)
    http.log_call("p", "m", "document", 2, 1.0, 0.002)
    assert cost_per_item("m", "document") == pytest.approx(0.001)


def test_in_parallel_runs_every_batch_once():
    seen = []
    http.in_parallel(seen.append, list(range(10)), batch_size=3, workers=4)
    assert sorted(map(tuple, seen)) == [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9,)]
