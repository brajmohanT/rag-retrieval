import json
from math import log

import pytest

from evidence_atlas.data.records import Dataset, Page, Query, Relevance
from evidence_atlas.evaluation.report import report_run
from evidence_atlas.retrieval.bm25 import BM25, tokenize
from evidence_atlas.retrieval.runs import load_run, percentile, save_run


def test_tokenize_stems_drops_stopwords_and_keeps_numbers():
    assert tokenize("The Workers' wages rose 4.5% in 2023, to 1,200 EUR") == \
        ["worker", "wage", "rose", "4.5", "2023", "1,200", "eur"]


def test_hand_calculated_score():
    # Two pages of 2 tokens each, so length normalization is 1.
    index = BM25({1: "wage wage", 2: "wage growth"}, k1=1.2, b=0.75)
    # "growth": df=1, N=2 -> idf = ln(1 + 1.5/1.5) = ln 2; tf=1 -> 1 * 2.2 / (1 + 1.2) = 1
    assert index.term_score("growth", 2) == pytest.approx(log(2))
    # "wage" on page 1: df=2 -> idf = ln(1 + 0.5/2.5) = ln 1.2; tf=2 -> 2 * 2.2 / (2 + 1.2) = 1.375
    assert index.term_score("wage", 1) == pytest.approx(log(1.2) * 1.375)


def test_search_ranks_rarer_terms_higher_and_explains():
    index = BM25({1: "wage policy", 2: "wage growth in germany", 3: "unrelated text"})
    results = index.search("wage growth")
    assert [page for page, _ in results] == [2, 1]  # page 3 shares no term
    terms = [term for term, _ in index.explain("wage growth", 2)]
    assert terms == ["growth", "wage"]  # rarer term contributes more
    assert sum(s for _, s in index.explain("wage growth", 2)) == pytest.approx(results[0][1])


def test_long_pages_are_penalized():
    index = BM25({1: "wage", 2: "wage " + "filler " * 20})
    assert index.search("wage")[0][0] == 1


def test_percentile_nearest_rank():
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile(list(range(1, 101)), 95) == 95


def test_run_roundtrip_and_report(tmp_path):
    pages = {i: Page(i, "doc", i, "") for i in (1, 2, 3)}
    queries = {q: Query(q, "english", f"q{q}", "", ("extractive",), "question", ("Text",), "image") for q in (10, 11)}
    data = Dataset({}, pages, queries, {10: [Relevance(10, 1, 2, (), ())], 11: [Relevance(11, 2, 2, (), ())]})
    meta = {"name": "test", "method": "test", "dataset_revision": "abc", "cost_usd": 0.0}
    save_run(tmp_path, {10: [(1, 2.0), (3, 1.0)], 11: [(3, 5.0)]}, meta)
    loaded_meta, rankings = load_run(tmp_path)
    assert rankings == {10: [1, 3], 11: [3]}
    assert loaded_meta["name"] == "test" and "created_at" in loaded_meta

    metrics = report_run(tmp_path, data, {"dev": [11], "heldout": [10]}, samples=10)
    assert metrics["heldout"]["summary"]["ndcg@10"]["mean"] == 1.0
    assert metrics["dev"]["summary"]["hit@10"]["mean"] == 0.0
    assert json.loads((tmp_path / "metrics.json").read_text())["heldout"]["ceiling"]["ndcg@10"] == 1.0
    report = (tmp_path / "report.md").read_text()
    assert "1 of 1 dev questions" in report and "**Q11**" in report
