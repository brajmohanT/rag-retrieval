from evidence_atlas.providers import http, openrouter, superlinked
from evidence_atlas.retrieval.rerank import rerank_ranking
from tests.test_providers import isolated  # noqa: F401  (shared fixture: fake keys, temp log)


def test_rerank_resorts_only_the_shortlist():
    ranking = ["A", "B", "C", "D", "E"]
    assert rerank_ranking(ranking, [0.1, 0.9, 0.5], depth=3) == ["B", "C", "A", "D", "E"]


def test_rerank_ties_keep_first_stage_order():
    assert rerank_ranking(["A", "B", "C"], [0.5, 0.5, 0.9], depth=3) == ["C", "A", "B"]


def test_openrouter_rerank_maps_indices_and_caches_pairs(isolated, monkeypatch):  # noqa: F811
    sent = []

    def fake_post(url, payload, headers):
        sent.append(payload["documents"])
        results = [{"index": i, "relevance_score": float(len(d))} for i, d in enumerate(payload["documents"])]
        return {"results": list(reversed(results)), "usage": {"cost": 0.001}}, 0.1

    monkeypatch.setattr(openrouter, "post_json", fake_post)
    assert openrouter.rerank("q", ["aa", "b"], "m", cache=isolated) == [2.0, 1.0]
    assert openrouter.rerank("q", ["b", "ccc"], "m", cache=isolated) == [1.0, 3.0]
    assert sent == [["aa", "b"], ["ccc"]]  # "b" was cached for this query


def test_superlinked_rerank_splits_large_shortlists(isolated, monkeypatch):  # noqa: F811
    sizes = []

    def fake_post(url, payload, headers):
        sizes.append(len(payload["items"]))
        scores = [{"item_id": item["id"], "score": 0.1 * int(item["id"])} for item in payload["items"]]
        return {"scores": scores, "usage": {"credits_charged_decimal": "10"}}, 1.0

    monkeypatch.setattr(superlinked, "post_json", fake_post)
    scores = superlinked.rerank("q", [b"p0", b"p1", b"p2", b"p3", b"p4"], cache=isolated, batch_size=2)
    assert sizes == [2, 2, 1]
    assert [round(s, 1) for s in scores] == [0.0, 0.1, 0.2, 0.3, 0.4]
    assert http.logged_calls(superlinked.VL_RERANKER, "rerank")[0]["items"] == 2
