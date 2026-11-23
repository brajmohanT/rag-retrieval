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


ANSWER_MODE = "text"  # answers in artifacts/answers/answers.json are keyed "<config>#<mode>"


def answer_summary(records, query_ids):
    """Share of held-out answers graded correct / partial / incorrect / abstained."""
    rows = [records[str(q)] for q in query_ids if str(q) in records]
    if not rows:
        return None
    share = lambda v: sum(r["verdict"] == v for r in rows) / len(rows)  # noqa: E731
    return {"n": len(rows), "correct": share("CORRECT"), "partial": share("PARTIAL"),
            "incorrect": share("INCORRECT"), "abstained": share("ABSTAINED"),
            "cites_judged_page": sum(r["cites_judged_page"] for r in rows) / len(rows),
            "cost_per_1k_usd": 1000 * sum(r["cost_usd"] for r in rows) / len(rows)}


def config_summary(config, ceiling, answers=None):
    return {
        "answers": answers,
        "id": config["id"], "members": config["members"], "visual_weight": config["visual_weight"],
        "rerank": config["rerank"], "index_cost_usd": config["index_cost_usd"],
        "query_cost_per_1k_usd": config["query_cost_per_1k_usd"], "latency_p50_ms": config["latency_p50_ms"],
        "heldout": {m: config["heldout"][m] for m in SUMMARY_METRICS},
        "heldout_by_content_type": {label: {"n": row["n"], "ndcg@10": row["ndcg@10"], "complete@5": row["complete@5"]}
                                    for label, row in config["heldout_by_content_type"].items()},
        "ceiling": ceiling,
    }


def vector_storage(artifacts_dir, retrievers):
    """Float32 bytes of stored vectors per page for each embedding retriever (BM25 keeps an inverted index instead)."""
    sizes = {}
    for name, (run, _) in retrievers.items():
        path = artifacts_dir / "runs" / run / "run.json"
        settings = json.loads(path.read_text())["settings"] if path.exists() else {}
        if "dimensions" in settings:
            sizes[name] = round(4 * settings["dimensions"] * settings.get("vectors_per_page_mean", 1))
    return sizes


def create_app(grid=None, data=None, pages_dir=None, answers=None):
    config = load_config()
    grid = grid or json.loads((config["artifacts_dir"] / "demo" / "grid.json").read_text())
    data = data or load_dataset(config["dataset"]["data_dir"])
    pages_dir = pages_dir or config["artifacts_dir"] / "demo" / "pages"
    answers_file = config["artifacts_dir"] / "answers" / "answers.json"
    if answers is None:
        answers = json.loads(answers_file.read_text()) if answers_file.exists() else {}
    sizes = json.loads((pages_dir / "sizes.json").read_text()) if (pages_dir / "sizes.json").exists() else {}
    questions = {q["query_id"]: q for q in grid["questions"]}
    configs = {c["id"]: c for c in grid["configs"]}
    # Best any retriever could score on held-out (judged pages in grade order); the same for every configuration.
    heldout = load_partitions(config["evaluation"]["partitions_file"])["heldout"]
    perfect = summarize(evaluate(perfect_rankings(data, heldout), data, heldout), samples=1)
    ceiling = {m: perfect[m]["mean"] for m in SUMMARY_METRICS}
    answer_stats = {c: answer_summary(answers.get(f"{c}#{ANSWER_MODE}", {}), heldout) for c in configs}
    showcase = json.loads((ROOT / "configs" / "showcase.json").read_text())
    for item in showcase:
        unknown = [c for c in item["lanes"] if c not in configs]
        if item["query_id"] not in questions or unknown:
            raise ValueError(f"Showcase item Q{item['query_id']} refers to unknown question or lanes {unknown}")
    storage = vector_storage(config["artifacts_dir"], grid["settings"]["retrievers"])

    app = FastAPI(title="Evidence Atlas demo API")

    @app.get("/api/meta")
    def meta():
        return {"retrievers": LABELS, "presets": PRESETS, "default_lanes": DEFAULT_LANES,
                "settings": grid["settings"], "questions": len(questions), "configs": len(configs),
                "pages": len(data.pages), "vector_bytes_per_page": storage}

    @app.get("/api/showcase")
    def get_showcase():
        return showcase

    @app.get("/api/configs")
    def list_configs():
        return [config_summary(c, ceiling, answer_stats[c["id"]]) for c in grid["configs"]]

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
            record = answers.get(f"{config_id}#{ANSWER_MODE}", {}).get(str(query_id))
            answer = record and {k: record[k] for k in ("text", "cited", "invalid_citations", "abstained", "verdict",
                                                         "pages", "cites_judged_page")}
            lanes.append({"config": config_id, "metrics": grid["question_metrics"][config_id][str(query_id)],
                          "pages": [{"page_id": p, "rank": i + 1, "grade": grades.get(p, 0)}
                                    for i, p in enumerate(ranking)],
                          "answer": answer})
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
