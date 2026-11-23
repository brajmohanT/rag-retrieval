from evidence_atlas.data.records import Dataset, Page
from evidence_atlas.generation import answer as gen
from evidence_atlas.providers import openrouter

DATA = Dataset({}, {1: Page(1, "doc", 0, "Employment rose to 75% [table]"), 2: Page(2, "doc", 4, "")}, {}, {})


def fake_chat(replies):
    calls = []

    def chat(messages, model, max_tokens):
        calls.append(max_tokens)
        return {"text": replies[len(calls) - 1], "usage": {"cost": 0.001}}

    return chat, calls


def test_answer_extracts_citations_and_flags_invalid_ones(monkeypatch):
    chat, _ = fake_chat(["Employment rose to 75% [p1], see also [p9]."])
    monkeypatch.setattr(openrouter, "chat", chat)
    result = gen.answer("What rate?", [1, 2], DATA)
    assert result["cited"] == [1, 9] and result["invalid_citations"] == [9]
    assert not result["abstained"] and result["cost_usd"] == 0.001


def test_abstention_is_detected(monkeypatch):
    monkeypatch.setattr(openrouter, "chat", fake_chat([f"{gen.ABSTAIN}."])[0])
    assert gen.answer("What rate?", [2], DATA)["abstained"]


def test_empty_reply_retries_with_a_larger_budget(monkeypatch):
    chat, calls = fake_chat(["", "PARTIAL"])
    monkeypatch.setattr(openrouter, "chat", chat)
    assert gen.grade("q", "ref", "ans") == ("PARTIAL", 0.002)
    assert calls == [1000, 2000]


def test_verdict_parsing_does_not_confuse_incorrect_with_correct(monkeypatch):
    for reply, expected in [("INCORRECT", "INCORRECT"), ("**Correct**.", "CORRECT"), ("I think so", "UNPARSED")]:
        monkeypatch.setattr(openrouter, "chat", fake_chat([reply])[0])
        assert gen.grade("q", "ref", "ans")[0] == expected


def test_page_block_labels_and_marks_empty_pages():
    assert gen.page_block(1, DATA).startswith("[p1] doc, PDF page 1\nEmployment")
    assert "no extracted text" in gen.page_block(2, DATA)


def test_image_mode_sends_labelled_page_images(monkeypatch):
    sent = []

    def chat(messages, model, max_tokens):
        sent.append(messages)
        return {"text": "Rate 75% [p1].", "usage": {"cost": 0.001}}

    monkeypatch.setattr(openrouter, "chat", chat)
    gen.answer("What rate?", [1], DATA, mode="image", images={1: b"webp-bytes"})
    parts = sent[0][1]["content"]
    assert [p["type"] for p in parts] == ["text", "text", "image_url", "text"]
    assert parts[1]["text"].startswith("[p1]") and "Employment" not in parts[1]["text"]  # image mode: no page text
    assert parts[2]["image_url"]["url"].startswith("data:image/webp;base64,")
