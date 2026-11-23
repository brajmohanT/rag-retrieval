"""Provider tests use fake HTTP responses: no network, no keys, no cost."""

import httpx
import numpy as np
import pytest

from evidence_atlas.providers import http, openrouter, superlinked
from evidence_atlas.providers.cache import Cache


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CALL_LOG", tmp_path / "calls.jsonl")
    monkeypatch.setenv("OPEN_ROUTER_KEY", "test-key")
    monkeypatch.setenv("SUPERLINKED_API_KEY", "test-key")
    monkeypatch.setattr(http.time, "sleep", lambda seconds: None)
    return Cache(tmp_path / "cache")


def test_cache_roundtrip_and_stable_keys(isolated):
    key = Cache.key(model="m", input="x")
    assert key == Cache.key(input="x", model="m")
    assert isolated.get_array(key) is None
    isolated.put_array(key, np.arange(3, dtype=np.float32))
    assert isolated.get_array(key).tolist() == [0, 1, 2]
    isolated.put_json(key, {"text": "hi"})
    assert isolated.get_json(key) == {"text": "hi"}


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("OPEN_ROUTER_KEY")
    with pytest.raises(RuntimeError, match="OPEN_ROUTER_KEY is not set"):
        http.api_key("OPEN_ROUTER_KEY")


def test_post_json_retries_rate_limits_then_succeeds(monkeypatch):
    responses = iter([httpx.Response(429, headers={"Retry-After": "1"}), httpx.Response(200, json={"ok": True})])
    monkeypatch.setattr(http.httpx, "post", lambda *args, **kwargs: next(responses))
    body, _ = http.post_json("https://example.test", {}, {})
    assert body == {"ok": True}


def test_post_json_raises_on_client_error(monkeypatch):
    monkeypatch.setattr(http.httpx, "post", lambda *args, **kwargs: httpx.Response(401, text="bad key"))
    with pytest.raises(RuntimeError, match="401"):
        http.post_json("https://example.test", {}, {})


def test_superlinked_batches_caches_and_logs_cost(isolated, monkeypatch):
    sent = []

    def fake_post(url, payload, headers):
        sent.append(payload)
        items = [{"multivector": {"values": [[float(len(sent))] * 2] * 3}} for _ in payload["items"]]
        return {"items": items, "usage": {"credits_charged_decimal": "20.0"}}, 0.5

    monkeypatch.setattr(superlinked, "post_json", fake_post)
    first = superlinked.encode([b"png-a", b"png-b", b"png-c"], is_query=False, cache=isolated, batch_size=2)
    assert len(sent) == 2 and [a.shape for a in first] == [(3, 2)] * 3
    assert sent[0]["params"]["options"]["is_query"] is False
    again = superlinked.encode([b"png-c", b"png-a"], is_query=False, cache=isolated)
    assert len(sent) == 2  # nothing re-sent
    assert again[0].tolist() == first[2].tolist()
    assert '"cost_usd": 0.0002' in http.CALL_LOG.read_text()


def test_openrouter_embed_keeps_input_order(isolated, monkeypatch):
    def fake_post(url, payload, headers):
        n = len(payload["input"])  # answer out of order, as the API may
        data = [{"index": i, "embedding": [float(i)]} for i in reversed(range(n))]
        return {"data": data, "usage": {"cost": 0.001}}, 0.2

    monkeypatch.setattr(openrouter, "post_json", fake_post)
    vectors = openrouter.embed(["question", b"png"], cache=isolated)
    assert [v.tolist() for v in vectors] == [[0.0], [1.0]]


def test_chat_is_cached(isolated, monkeypatch):
    calls = []

    def fake_post(url, payload, headers):
        calls.append(payload)
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"cost": 0.0001}}, 0.1

    monkeypatch.setattr(openrouter, "post_json", fake_post)
    messages = [{"role": "user", "content": "hi"}]
    assert openrouter.chat(messages, cache=isolated)["text"] == "ok"
    assert openrouter.chat(messages, cache=isolated)["text"] == "ok"
    assert len(calls) == 1 and calls[0]["temperature"] == 0
