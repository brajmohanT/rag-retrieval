from math import log2

import pytest

from evidence_atlas.config import load_config
from evidence_atlas.data.records import Dataset, Page, Query, Relevance, load_dataset
from evidence_atlas.evaluation.evaluate import bootstrap_ci, breakdown, evaluate, paired_difference, summarize
from evidence_atlas.evaluation.metrics import complete_at_k, ndcg_at_k, score_question
from evidence_atlas.evaluation.partitions import load_partitions, make_partitions

# Page A fully answers; B and C are partial evidence. X, Y, Z are unjudged.
JUDGED = {"A": 2, "B": 1, "C": 1}
RANKING = ["X", "B", "Y", "A", "Z"]


def test_hand_calculated_metrics():
    scores = score_question(RANKING, JUDGED, ks=(3, 5))
    assert scores["hit@3"] == 1  # B at rank 2
    assert scores["recall@3"] == pytest.approx(1 / 3)  # B of {A, B, C}
    assert scores["recall@5"] == pytest.approx(2 / 3)  # B and A
    assert scores["complete@3"] == 0  # no grade-2 page, and C missing
    assert scores["complete@5"] == 1  # A is a complete answer
    assert scores["mrr@10"] == 0.5  # first judged page at rank 2
    # DCG  = 1/log2(3) [B at 2] + 2/log2(5) [A at 4]
    # IDCG = 2/log2(2) + 1/log2(3) + 1/log2(4)   [ideal order A, B, C]
    dcg = 1 / log2(3) + 2 / log2(5)
    idcg = 2 + 1 / log2(3) + 0.5
    assert scores["ndcg@10"] == pytest.approx(dcg / idcg)
    assert scores["ndcg@10"] == pytest.approx(0.4766, abs=1e-4)


def test_complete_needs_every_partial_page_without_a_full_answer():
    judged = {"B": 1, "C": 1}
    assert complete_at_k(["C", "X", "B"], judged, 3) == 1
    assert complete_at_k(["C", "X", "B"], judged, 2) == 0


def test_perfect_and_empty_rankings():
    assert ndcg_at_k(["A", "B", "C"], JUDGED, 10) == pytest.approx(1)
    assert all(value == 0 for value in score_question([], JUDGED).values())


def test_duplicate_pages_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        score_question(["A", "A"], JUDGED)


def tiny_dataset():
    pages = {i: Page(i, "doc", i, "") for i in range(1, 6)}
    queries = {
        1: Query(1, "english", "q1", "a", ("numerical",), "question", ("Table",), "image"),
        2: Query(2, "english", "q2", "a", ("boolean",), "question", ("Chart", "Table"), "image"),
    }
    qrels = {1: [Relevance(1, 1, 2, (), ())], 2: [Relevance(2, 2, 2, (), ())]}
    return Dataset({}, pages, queries, qrels)


def test_missing_question_scores_zero_and_unknown_page_rejected():
    data = tiny_dataset()
    rows = evaluate({1: [1, 3]}, data, [1, 2])
    assert rows[0]["ndcg@10"] == 1 and rows[1]["ndcg@10"] == 0
    with pytest.raises(ValueError, match="unknown page"):
        evaluate({1: [99]}, data, [1])


def test_breakdown_counts_multi_label_questions_in_each_label():
    rows = evaluate({1: [1], 2: [3]}, tiny_dataset(), [1, 2])
    table = breakdown(rows, "content_type")
    assert table["Table"]["n"] == 2 and table["Table"]["hit@5"] == 0.5
    assert table["Chart"] == {"n": 1, **{k: 0.0 for k in table["Chart"] if k != "n"}}


def test_bootstrap_and_paired_difference():
    assert bootstrap_ci([0.5] * 20) == (0.5, 0.5)
    low, high = bootstrap_ci([0, 1] * 50, seed=1)
    assert low < 0.5 < high
    data = tiny_dataset()
    better = evaluate({1: [1], 2: [2]}, data, [1, 2])
    worse = evaluate({1: [1], 2: [3]}, data, [1, 2])
    assert paired_difference(better, worse, "hit@5")["mean"] == 0.5
    assert summarize(better)["hit@5"] == {"mean": 1.0, "low": 1.0, "high": 1.0}
    with pytest.raises(ValueError):
        paired_difference(better, worse[:1], "hit@5")


def test_partitions_are_deterministic_disjoint_and_stratified():
    queries = {i: Query(i, "english", "", "", ("numerical",) if i < 60 else ("boolean",), "", (), "")
               for i in range(90)}
    first = make_partitions(queries, 1 / 3, seed=7)
    assert first == make_partitions(queries, 1 / 3, seed=7)
    assert not set(first["dev"]) & set(first["heldout"])
    assert sorted(first["dev"] + first["heldout"]) == list(range(90))
    assert sum(i < 60 for i in first["dev"]) == 20 and sum(i >= 60 for i in first["dev"]) == 10


def test_frozen_partitions_match_the_config():
    config = load_config()
    settings = config["evaluation"]
    if not config["dataset"]["data_dir"].exists():
        pytest.skip("dataset not downloaded")
    frozen = load_partitions(settings["partitions_file"])
    data = load_dataset(config["dataset"]["data_dir"])
    rebuilt = make_partitions(data.queries, settings["dev_fraction"], settings["seed"])
    assert (frozen["dev"], frozen["heldout"]) == (rebuilt["dev"], rebuilt["heldout"])
    assert frozen["dataset_revision"] == config["dataset"]["revision"]
