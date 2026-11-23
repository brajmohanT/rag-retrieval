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
