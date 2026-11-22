"""Score a retrieval run and summarize it with confidence intervals and breakdowns.

A run's rankings map query_id -> page IDs, best first. Every question in the
partition is scored; a question missing from the run scores 0 on every metric.
"""

from collections import defaultdict
import random

from evidence_atlas.evaluation.metrics import score_question


def evaluate(rankings, data, query_ids, ks=(5, 10)):
    """One row per question: IDs, question/content types, and metric scores."""
    rows = []
    for query_id in query_ids:
        ranking = list(rankings.get(query_id, []))
        unknown = [page for page in ranking if page not in data.pages]
        if unknown:
            raise ValueError(f"Query {query_id} ranks unknown page IDs: {unknown[:5]}")
        judged = {r.page_id: r.grade for r in data.qrels[query_id]}
        query = data.queries[query_id]
        rows.append({"query_id": query_id, "query_types": query.query_types,
                     "content_type": query.content_type, **score_question(ranking, judged, ks)})
    return rows


def metric_names(rows):
    return [name for name in rows[0] if "@" in name]


def bootstrap_ci(values, samples=1000, seed=0, level=0.95):
    """Percentile bootstrap interval for the mean of per-question values."""
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(samples))
    tail = (1 - level) / 2
    return means[int(tail * samples)], means[int((1 - tail) * samples) - 1]


def summarize(rows, samples=1000, seed=0):
    """metric -> {mean, low, high} over all rows."""
    summary = {}
    for name in metric_names(rows):
        values = [row[name] for row in rows]
        low, high = bootstrap_ci(values, samples, seed)
        summary[name] = {"mean": sum(values) / len(values), "low": low, "high": high}
    return summary


def breakdown(rows, field):
    """label -> {n, metric means}. Multi-label questions count in each of their labels."""
    groups = defaultdict(list)
    for row in rows:
        for label in row[field]:
            groups[label].append(row)
    return {
        label: {"n": len(group), **{name: sum(r[name] for r in group) / len(group) for name in metric_names(group)}}
        for label, group in sorted(groups.items(), key=lambda item: -len(item[1]))
    }


def paired_difference(rows_a, rows_b, metric, samples=1000, seed=0):
    """Mean of (A - B) per question, with a paired bootstrap interval.

    If the interval excludes 0, the difference is unlikely to be resampling noise.
    """
    b_by_id = {row["query_id"]: row[metric] for row in rows_b}
    if set(b_by_id) != {row["query_id"] for row in rows_a}:
        raise ValueError("Runs must cover the same questions")
    diffs = [row[metric] - b_by_id[row["query_id"]] for row in rows_a]
    low, high = bootstrap_ci(diffs, samples, seed)
    return {"mean": sum(diffs) / len(diffs), "low": low, "high": high}
