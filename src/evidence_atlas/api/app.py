"""Demo backend: serves the precomputed grid, questions, pages, and page images as a JSON API.

Run: uv run atlas-serve   (http://127.0.0.1:8000; the built frontend is served at / when web/dist exists)

Benchmark questions only: every answer comes from artifacts/demo/grid.json, so
no API is called and nothing is paid at view time.
"""

import json
import sys

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from evidence_atlas.config import ROOT, load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.evaluate import evaluate, summarize
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.evaluation.report import perfect_rankings

LABELS = {"bm25": "Keyword (BM25)", "dense": "Text embeddings", "voyage": "Visual · single-vector",
          "colqwen3": "Visual · multi-vector"}
# Lanes the demo opens with, and named shortcuts for common setups.
PRESETS = [
    {"name": "Keyword search", "config": "bm25|vw1"},
    {"name": "Text embeddings", "config": "dense|vw1"},
    {"name": "Visual · single-vector", "config": "voyage|vw1"},
    {"name": "Visual · multi-vector", "config": "colqwen3|vw1"},
    {"name": "Hybrid", "config": "bm25+dense+voyage+colqwen3|vw1"},
    {"name": "Hybrid + rerank", "config": "bm25+dense+voyage+colqwen3|vw1|cohere"},
    {"name": "Fast hybrid + rerank", "config": "bm25+voyage|vw1|cohere"},
]
DEFAULT_LANES = ["bm25|vw1", "dense|vw1", "colqwen3|vw1", "bm25+dense+voyage+colqwen3|vw1|cohere"]
SUMMARY_METRICS = ["ndcg@10", "mrr@10", "hit@5", "recall@5", "complete@5", "complete@10"]
LANE_PAGES = 10


def config_summary(config, ceiling):
    return {
        "id": config["id"], "members": config["members"], "visual_weight": config["visual_weight"],
        "rerank": config["rerank"], "index_cost_usd": config["index_cost_usd"],
        "query_cost_per_1k_usd": config["query_cost_per_1k_usd"], "latency_p50_ms": config["latency_p50_ms"],
        "heldout": {m: config["heldout"][m] for m in SUMMARY_METRICS},
        "heldout_by_content_type": {label: {"n": row["n"], "ndcg@10": row["ndcg@10"], "complete@5": row["complete@5"]}
                                    for label, row in config["heldout_by_content_type"].items()},
        "ceiling": ceiling,
    }


def create_app(grid=None, data=None, pages_dir=None):
    config = load_config()
    grid = grid or json.loads((config["artifacts_dir"] / "demo" / "grid.json").read_text())
    data = data or load_dataset(config["dataset"]["data_dir"])
    pages_dir = pages_dir or config["artifacts_dir"] / "demo" / "pages"
    sizes = json.loads((pages_dir / "sizes.json").read_text()) if (pages_dir / "sizes.json").exists() else {}
    questions = {q["query_id"]: q for q in grid["questions"]}
    configs = {c["id"]: c for c in grid["configs"]}
    # Best any retriever could score on held-out (judged pages in grade order); the same for every configuration.
    heldout = load_partitions(config["evaluation"]["partitions_file"])["heldout"]
    perfect = summarize(evaluate(perfect_rankings(data, heldout), data, heldout), samples=1)
    ceiling = {m: perfect[m]["mean"] for m in SUMMARY_METRICS}

    app = FastAPI(title="Evidence Atlas demo API")

    @app.get("/api/meta")
    def meta():
        return {"retrievers": LABELS, "presets": PRESETS, "default_lanes": DEFAULT_LANES,
                "settings": grid["settings"], "questions": len(questions), "configs": len(configs)}

    @app.get("/api/configs")
    def list_configs():
        return [config_summary(c, ceiling) for c in grid["configs"]]

    @app.get("/api/questions")
    def list_questions():
        return [{"query_id": q["query_id"], "text": q["text"], "partition": q["partition"],
                 "query_types": q["query_types"], "content_type": q["content_type"], "judged": len(q["judged"])}
                for q in grid["questions"]]

    @app.get("/api/questions/{query_id}")
    def question(query_id: int, configs_param: str = Query("", alias="configs")):
        if query_id not in questions:
            raise HTTPException(404, f"Unknown question {query_id}")
        lane_ids = [c for c in configs_param.split(",") if c] or DEFAULT_LANES
        unknown = [c for c in lane_ids if c not in configs]
        if unknown:
            raise HTTPException(404, f"Unknown configuration(s): {', '.join(unknown)}")
        q = questions[query_id]
        grades = dict((page, grade) for page, grade in q["judged"])
        boxes = {r.page_id: [[b.x1, b.y1, b.x2, b.y2] for b in r.boxes] for r in data.qrels[query_id]}
        lanes = []
        for config_id in lane_ids:
            ranking = grid["rankings"][config_id][str(query_id)][:LANE_PAGES]
            lanes.append({"config": config_id, "metrics": grid["question_metrics"][config_id][str(query_id)],
                          "pages": [{"page_id": p, "rank": i + 1, "grade": grades.get(p, 0)}
                                    for i, p in enumerate(ranking)]})
        return {"question": {**q, "judged": [{"page_id": p, "grade": g, "boxes": boxes.get(p, [])}
                                             for p, g in q["judged"]]},
                "lanes": lanes}

    @app.get("/api/pages/{page_id}")
    def page(page_id: int):
        if page_id not in data.pages:
            raise HTTPException(404, f"Unknown page {page_id}")
        p = data.pages[page_id]
        doc = data.documents[p.doc_id]
        width, height = sizes.get(str(page_id), (None, None))
        return {"page_id": page_id, "doc_id": p.doc_id, "page_number": p.page_number,
                "pdf_page": p.page_number + 1, "markdown": p.markdown, "width": width, "height": height,
                "license": doc.license, "url": doc.url, "doc_year": doc.year,
                "thumb": f"/page-images/{page_id}-thumb.webp", "image": f"/page-images/{page_id}-large.webp"}

    if pages_dir.exists():
        app.mount("/page-images", StaticFiles(directory=pages_dir), name="page-images")
    dist = ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


def main():
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
