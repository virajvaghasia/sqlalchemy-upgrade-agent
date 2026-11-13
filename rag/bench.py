"""How long each retrieval stage takes, over the 100 golden questions.

    RAG_DENSE=memory uv run python -m rag.bench               # dense search in memory, as the web server runs
    uv run python -m rag.bench                                # dense search in Qdrant (docker compose up -d qdrant)
    RAG_DENSE=memory uv run python -m rag.bench --device cpu  # both models on the CPU, as in the container
    ... --first 20                                            # only the first 20 golden questions
    uv run python -m rag.bench --show <saved file>            # print a saved run's table again
    ... --overwrite                                           # replace a saved run that covers more questions

Retrieval only: no answer model is called. Writes deliverables/latency.<machine>.<dense>.<device>.json,
with `n` in the file saying how many questions it covers.

The stages are the shipped `index.retrieve` defaults, in the order it runs them:

    embed    the question through BGE-M3
    dense    nearest vectors (Qdrant or in memory), cross-version twins collapsed
    bm25     keyword search over the same chunks
    fuse     reciprocal rank fusion of the two lists, twins collapsed again
    rerank   the cross-encoder scores the top 20 and may promote one into seat 5

Each stage is timed by making the same calls `index.retrieve` makes, one at a
time. After every question the top 5 are compared with what `index.retrieve`
itself returns, and the run stops on the first difference: timings of a path
that does not ship would describe nothing.

The first question is timed apart as `cold`, because it loads both models.
p50 and p95 use the nearest-rank method: with 100 questions, p95 is the 95th of
the sorted times, a value that was actually measured rather than an interpolation.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
from collections.abc import Callable, Sequence

from rag import corpus

STAGES = ("embed", "dense", "bm25", "fuse", "rerank")
DELIVERABLES = corpus.REPO_ROOT / "deliverables"


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest rank: the smallest value with at least p% of values at or below it."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


def summarize(rows: list[dict]) -> dict:
    out = {}
    for stage in (*STAGES, "total"):
        ms = [r[stage] for r in rows]
        out[stage] = {
            "p50_ms": round(percentile(ms, 50), 1),
            "p95_ms": round(percentile(ms, 95), 1),
            "mean_ms": round(statistics.fmean(ms), 1),
        }
    return out


def timed_retrieve(question: str, limit: int) -> tuple[list[str], dict[str, float]]:
    """`index.retrieve(question, limit)` with its default flags, stage by stage."""
    from rag import bm25, dedup, hybrid, index, rerank

    _, _, stats, chunks = index.load_inputs()
    channel = hybrid.CHANNEL_DEPTH
    fetch_limit = max(limit, rerank.CANDIDATE_DEPTH)
    ms: dict[str, float] = {}

    t = time.perf_counter()
    vec = index.query_vector(question)
    ms["embed"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    dense = index.dense_points_fn(stats, vec, dedup.overfetch_limit(channel), None, None)
    dense = dedup.dedupe_points(dense, channel)
    ms["dense"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    sparse = bm25.get_index().search(question, limit=channel, version=None)
    ms["bm25"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    dense_ids = [p.payload["chunk_id"] for p in dense]
    sparse_ids = [h.chunk_id for h in sparse]
    ordered = hybrid.rrf_fuse(dense_ids, sparse_ids, limit=dedup.overfetch_limit(fetch_limit))
    points = hybrid.materialize_hits(
        ordered,
        dense_by_id={p.payload["chunk_id"]: p for p in dense},
        chunks_by_id=chunks,
        rrf_scores=hybrid.rrf_scores_map(dense_ids, sparse_ids),
    )
    points = dedup.dedupe_points(points, fetch_limit)
    ms["fuse"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    points = rerank.rerank(question, points)
    ms["rerank"] = (time.perf_counter() - t) * 1000

    ms["total"] = sum(ms[s] for s in STAGES)
    return [p.payload["chunk_id"] for p in points[:limit]], ms


def run(
    items: list[dict],
    limit: int,
    timed: Callable[[str, int], tuple[list[str], dict[str, float]]] = timed_retrieve,
    reference: Callable[[str, int], list[str]] | None = None,
    log=print,
) -> dict:
    if reference is None:
        from rag import index

        def reference(q: str, k: int) -> list[str]:
            return [h.payload["chunk_id"] for h in index.retrieve(q, limit=k)]

    t = time.perf_counter()
    timed(items[0]["question"], limit)
    cold_ms = (time.perf_counter() - t) * 1000
    log(f"cold first question (loads both models): {cold_ms / 1000:.1f}s")

    rows = []
    for n, item in enumerate(items, 1):
        ids, ms = timed(item["question"], limit)
        expected = reference(item["question"], limit)
        if ids != expected:
            sys.exit(
                f"{item['id']}: the staged path returned {ids}, index.retrieve returned {expected}.\n"
                "  rag/bench.py no longer mirrors index.retrieve; fix it before trusting any timing."
            )
        rows.append({"id": item["id"], **{k: round(v, 2) for k, v in ms.items()}})
        if n % 25 == 0:
            log(f"  {n}/{len(items)}")
    return {"cold_ms": round(cold_ms, 1), "summary": summarize(rows), "rows": rows}


def report(result: dict, header: str) -> None:
    print(f"\n{header}\n")
    print(f"  {'stage':<8}{'p50 ms':>10}{'p95 ms':>10}{'mean ms':>10}")
    for stage, s in result["summary"].items():
        print(f"  {stage:<8}{s['p50_ms']:>10.1f}{s['p95_ms']:>10.1f}{s['mean_ms']:>10.1f}")
    print(f"\n  cold first question {result['cold_ms'] / 1000:.1f}s (model loading, not in the table)")


def header(saved: dict) -> str:
    return f"retrieval latency, {saved['machine']}, device={saved['device']}, dense={saved['dense']}, n={saved['n']}"


def saved_n(path) -> int:
    """How many questions the run already saved at `path` covers; 0 if there is none.

    The file name carries the machine, the dense backend and the device but not the
    question count, so a `--first 6` run lands on the same name as the full 100.
    A doc quotes the full run's table, and a shorter run must not replace it quietly.
    """
    try:
        return int(json.loads(path.read_text())["n"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def main() -> None:
    argv = sys.argv[1:]
    if "--show" in argv:
        saved = json.loads(open(argv[argv.index("--show") + 1]).read())
        report(saved, header(saved))
        return

    from rag import ask, embed, faithful, index, score

    if "--device" in argv:
        forced = argv[argv.index("--device") + 1]

        # Both models ask embed.pick_device(None) when they first load, so
        # answering for them here moves both, and nothing else.
        def pick_device(requested: str | None = None) -> str:
            return requested or forced

        embed.pick_device = pick_device
    device = embed.pick_device(None)
    dense = os.environ.get(index.DENSE_ENV, "qdrant")
    items = score.load_golden()
    if "--first" in argv:
        items = items[: int(argv[argv.index("--first") + 1])]
    limit = ask.DEFAULT_K

    print(f"{len(items)} golden questions, top {limit}, dense={dense}, device={device}, {faithful.machine()}")
    saved = {
        "generated_by": "rag/bench.py",
        "machine": faithful.machine(),
        "device": device,
        "dense": dense,
        "n": len(items),
        "k": limit,
        **run(items, limit),
    }
    report(saved, header(saved))

    out = DELIVERABLES / f"latency.{faithful.machine()}.{dense}.{device}.json"
    covered = saved_n(out)
    if covered > len(items) and "--overwrite" not in argv:
        print(
            f"\n  NOT saved: {out.relative_to(corpus.REPO_ROOT)} already covers {covered} questions and this run\n"
            f"  covers {len(items)}. Pass --overwrite to replace it."
        )
        return
    out.write_text(json.dumps(saved, indent=1) + "\n")
    print(f"\n  saved {out.relative_to(corpus.REPO_ROOT)}")


if __name__ == "__main__":
    main()
