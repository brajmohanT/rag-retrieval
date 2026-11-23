from evidence_atlas.demo.grid import configurations, cost_and_latency, first_stage


def test_configuration_grid_shape():
    configs = configurations()
    ids = [c["id"] for c in configs]
    assert len(ids) == len(set(ids)) == 66  # 6 single-input subsets + 9 mixed x 3 weights = 33, x rerank on/off
    mixed = [c for c in configs if c["id"].startswith("bm25+colqwen3|")]
    assert sorted({c["visual_weight"] for c in mixed}) == [0.5, 1.0, 2.0]
    assert {c["visual_weight"] for c in configs if c["members"] == ["voyage", "colqwen3"]} == {1.0}


def test_visual_weight_applies_only_to_image_retrievers():
    rankings = {"bm25": {1: ["T"]}, "voyage": {1: ["V"]}}
    config = {"members": ["bm25", "voyage"], "visual_weight": 2.0}
    assert first_stage(config, rankings)[1] == ["V", "T"]
    assert first_stage({**config, "visual_weight": 0.5}, rankings)[1] == ["T", "V"]


def test_cost_adds_and_latency_takes_slowest_member():
    metas = {"bm25": {"query_latency": {"p50_ms": 1}},
             "voyage": {"index_cost_usd": 1.3, "query_cost_per_1k_usd": 0.003, "query_latency": {"p50_ms": 565}}}
    result = cost_and_latency({"members": ["bm25", "voyage"], "rerank": False}, metas)
    assert result == {"index_cost_usd": 1.3, "query_cost_per_1k_usd": 0.003, "latency_p50_ms": 565}
