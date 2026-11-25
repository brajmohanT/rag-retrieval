"""Static export: every route the frontend reads becomes a JSON file holding the API's exact response."""

import json

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from evidence_atlas.demo.static import export_json


def tiny_app():
    app = FastAPI()
    configs = ["bm25|vw1", "dense|vw1"]
    app.get("/api/meta")(lambda: {"default_lanes": configs[:1]})
    app.get("/api/showcase")(lambda: [])
    app.get("/api/configs")(lambda: [{"id": c} for c in configs])
    app.get("/api/questions")(lambda: [{"query_id": 7}])

    @app.get("/api/questions/{query_id}")
    def question(query_id: int, lanes: str = Query("", alias="configs")):
        return {"question": {"query_id": query_id}, "lanes": [{"config": c} for c in lanes.split(",")]}

    @app.get("/api/pages/{page_id}")
    def page(page_id: int):
        return {"page_id": page_id, "thumb": f"/page-images/{page_id}-thumb.webp"}

    return app


def test_export_writes_one_file_per_route(tmp_path):
    app = tiny_app()
    total = export_json(app, tmp_path, [3, 4])
    files = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*.json"))
    assert files == ["api/configs.json", "api/meta.json", "api/pages/3.json", "api/pages/4.json",
                     "api/questions.json", "api/questions/7.json", "api/showcase.json"]
    question = json.loads((tmp_path / "api/questions/7.json").read_text())
    assert [lane["config"] for lane in question["lanes"]] == ["bm25|vw1", "dense|vw1"]
    live = TestClient(app).get("/api/pages/3").content
    assert (tmp_path / "api/pages/3.json").read_bytes() == live
    assert total == sum(p.stat().st_size for p in tmp_path.rglob("*.json"))
