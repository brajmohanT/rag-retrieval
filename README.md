# Evidence Atlas

An interactive multimodal RAG showcase. It compares text, visual, and hybrid retrieval on the same questions over the [ViDoRe V3 HR](https://huggingface.co/datasets/vidore/vidore_v3_hr) corpus (14 EU labour-market reports, 1,110 pages), then shows the original page evidence behind each answer. All models run through hosted APIs.

Status: early build. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                      # create .venv and install the project
cp .env.example .env         # add API keys when a step needs them
```

The dataset (~495 MB) lives in `data/vidore_v3_hr/` and is not in Git.

## Commands

```sh
uv run pytest                        # run tests
uv run atlas-inspect --query-id 0    # audit the dataset; write an evidence viewer to artifacts/inspection/0/
uv run atlas-bm25                    # run BM25 on all questions; report in artifacts/runs/bm25/
uv run atlas-eval artifacts/runs/X   # (re)evaluate any saved run
```

## Layout

```text
configs/            dataset paths and pinned revision
src/evidence_atlas/ project code
  config.py         loads configs/*.yaml
  data/             dataset records, audit, evidence viewer
  evaluation/       partitions, metrics, run reports
  retrieval/        retrievers and the shared run format
tests/
docs/               plan, progress, research, discussion notes
data/, artifacts/   local only (ignored by Git)
```
