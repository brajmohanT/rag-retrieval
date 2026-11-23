"""Generate and grade cited answers for demo presets.

Run: uv run atlas-answers --limit 20 --mode image --configs "bm25+dense+voyage+colqwen3|vw1|cohere"   (pilot)
     uv run atlas-answers                                       (all presets, all questions, text mode)

Each answer uses the top 5 pages of a configuration from artifacts/demo/grid.json.
--mode: the answer model reads page text, page images (the demo's 1100 px WebP), or both.
Writes artifacts/answers/answers.json: "<config>#<mode>" -> query_id -> answer record.
Calls are cached, so reruns and overlapping page sets are free.
"""

import argparse
import json
import sys

from evidence_atlas.api.app import PRESETS
from evidence_atlas.config import load_config
from evidence_atlas.data.records import load_dataset
from evidence_atlas.evaluation.partitions import load_partitions
from evidence_atlas.generation.answer import ABSTAIN, answer, grade
from evidence_atlas.providers.http import in_parallel

TOP_PAGES = 5


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", nargs="*", default=[p["config"] for p in PRESETS])
    parser.add_argument("--partition", default="all", choices=["dev", "heldout", "all"])
    parser.add_argument("--limit", type=int, help="only the first N questions of the partition (pilot)")
    parser.add_argument("--mode", default="text", choices=["text", "image", "both"])
    args = parser.parse_args()

    config = load_config()
    data = load_dataset(config["dataset"]["data_dir"])
    grid = json.loads((config["artifacts_dir"] / "demo" / "grid.json").read_text())
    partitions = load_partitions(config["evaluation"]["partitions_file"])
    query_ids = sorted(data.queries) if args.partition == "all" else partitions[args.partition]
    query_ids = query_ids[:args.limit] if args.limit else query_ids

    out = config["artifacts_dir"] / "answers" / "answers.json"
    store = json.loads(out.read_text()) if out.exists() else {}
    pages_dir = config["artifacts_dir"] / "demo" / "pages"
    for config_id in args.configs:
        records = {}
        images = {}
        if args.mode != "text":
            needed = {p for q in query_ids for p in grid["rankings"][config_id][str(q)][:TOP_PAGES]}
            images = {p: (pages_dir / f"{p}-large.webp").read_bytes() for p in needed}

        def run(batch):
            for q in batch:
                pages = grid["rankings"][config_id][str(q)][:TOP_PAGES]
                query = data.queries[q]
                result = answer(query.text, pages, data, args.mode, images)
                verdict, grade_cost = (("ABSTAINED", 0) if result["abstained"]
                                       else grade(query.text, query.answer, result["text"]))
                judged = {r.page_id for r in data.qrels[q]}
                records[q] = {**result, "pages": pages, "mode": args.mode, "verdict": verdict,
                              "grade_cost_usd": grade_cost, "cites_judged_page": any(p in judged for p in result["cited"])}

        in_parallel(run, query_ids, batch_size=1, workers=8)
        store.setdefault(f"{config_id}#{args.mode}", {}).update({str(q): records[q] for q in query_ids})

        rows = [records[q] for q in query_ids]
        n = len(rows)
        count = lambda v: sum(r["verdict"] == v for r in rows)  # noqa: E731
        cost = sum(r["cost_usd"] + r["grade_cost_usd"] for r in rows)
        print(f"{config_id}  mode={args.mode}  (n={n})")
        print(f"  correct {count('CORRECT') / n:.0%}  partial {count('PARTIAL') / n:.0%}  incorrect {count('INCORRECT') / n:.0%}"
              f"  abstained {count('ABSTAINED') / n:.0%}  unparsed {count('UNPARSED')}")
        print(f"  answers citing a judged page {sum(r['cites_judged_page'] for r in rows) / n:.0%}; "
              f"invalid citations {sum(bool(r['invalid_citations']) for r in rows)}; "
              f"answers with no citation {sum(not r['cited'] and not r['abstained'] for r in rows)}")
        print(f"  cost this batch ${cost:.4f} (${cost / n:.4f} per question, answer + grade; cached calls count again)")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(store, indent=1) + "\n")
    print(f"Wrote {out}. '{ABSTAIN}' answers are not graded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
