"""Demo API against the real grid and dataset (skipped when they have not been built)."""

import pytest

from evidence_atlas.config import load_config

config = load_config()
if not (config["artifacts_dir"] / "demo" / "grid.json").exists() or not config["dataset"]["data_dir"].exists():
    pytest.skip("demo grid or dataset not built", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from evidence_atlas.api.app import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_meta_and_lists(client):
    meta = client.get("/api/meta").json()
    assert meta["questions"] == 318 and meta["configs"] == 66
    configs = client.get("/api/configs").json()
    assert all(0 < c["heldout"]["ndcg@10"]["mean"] < 1 for c in configs)
    assert configs[0]["ceiling"]["ndcg@10"] == pytest.approx(1.0)
    assert len(client.get("/api/questions").json()) == 318


def test_question_lanes_mark_judged_pages(client):
    body = client.get("/api/questions/208", params={"configs": "bm25|vw1,colqwen3|vw1"}).json()
    assert [lane["config"] for lane in body["lanes"]] == ["bm25|vw1", "colqwen3|vw1"]
    assert body["question"]["judged"][0]["page_id"] == 403 and body["question"]["judged"][0]["boxes"]
    colqwen = body["lanes"][1]["pages"]
    assert len(colqwen) == 10 and any(p["page_id"] == 403 and p["grade"] == 2 for p in colqwen)


def test_unknown_ids_are_404(client):
    assert client.get("/api/questions/99999").status_code == 404
    assert client.get("/api/questions/208", params={"configs": "nope"}).status_code == 404
    assert client.get("/api/pages/99999").status_code == 404


def test_page_details(client):
    page = client.get("/api/pages/403").json()
    assert page["pdf_page"] == 169 and page["width"] == 2339 and page["license"]


def test_answers_attach_to_lanes_and_scoreboard():
    fusion = "bm25+dense+voyage+colqwen3|vw1|cohere"
    record = {"text": "73% [p403].", "cited": [403], "invalid_citations": [], "abstained": False,
              "verdict": "CORRECT", "pages": [403], "cites_judged_page": True, "cost_usd": 0.001}
    app = create_app(answers={f"{fusion}#text": {"208": record}})
    c = TestClient(app)
    lanes = c.get("/api/questions/208", params={"configs": f"{fusion},bm25|vw1"}).json()["lanes"]
    assert lanes[0]["answer"]["verdict"] == "CORRECT" and lanes[0]["answer"]["cited"] == [403]
    assert lanes[1]["answer"] is None
    summaries = {s["id"]: s["answers"] for s in c.get("/api/configs").json()}
    assert summaries["bm25|vw1"] is None  # Q208 is a dev question; held-out answers are what count


def test_showcase_and_storage(client):
    items = client.get("/api/showcase").json()
    assert [i["query_id"] for i in items][:1] == [208] and len(items) == 6
    lanes = client.get("/api/questions/204", params={"configs": ",".join(items[2]["lanes"])}).json()["lanes"]
    assert len(lanes) == 4
    storage = client.get("/api/meta").json()["vector_bytes_per_page"]
    assert storage["voyage"] == 4096 and storage["colqwen3"] > 900_000
