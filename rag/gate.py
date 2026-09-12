"""Phase 6 — the quality gate: a pull request that loses a golden answer does not merge.

    uv run python -m rag.score --save /tmp/pr.json          # this checkout's rows
    uv run python -m rag.gate --baseline deliverables/gate-baseline.json --rows /tmp/pr.json
    uv run python -m rag.gate --stamp /tmp/pr.json deliverables/gate-baseline.json   # adopt

WHAT IT CHECKS, IN PYTHON AND SQL TERMS FIRST

Two tables with one row per golden question: the baseline (what the branch you
are merging INTO retrieves) and this run (what your change retrieves). Join them
on the question id. For each answerable row ask one yes/no question -- *was the
answer page in the top 5?* -- on both sides.

    was yes, now no    BROKEN   -> the gate fails
    was no,  now yes   FIXED    -> reported, never required
    same either way    unchanged

**A single broken item blocks the merge**, even if the same change fixes five
others. That is not new strictness invented for CI: it is Round 14's rule, the
one still holding prompt H back (`D83`), and `D61`'s reason for reading flipped
items rather than averages. A net gain that breaks `g043` has taken an answer
away from the developer who asks `g043`, and the gate makes that a decision a
human signs off rather than a side effect nobody saw.

WHAT IT DOES NOT CHECK

- **Generation.** No Ollama in CI, and `D83` measured generation not
  reproducing across machines at all. Retrieval did, exactly. So the gate grades
  the half that can be graded on a stranger's computer.
- **The average.** recall@5 is printed for context and gates nothing. A PR can
  drop it by breaking one item, and one broken item already fails.

THE RULER CANNOT BE MOVED BY THE THING BEING GRADED

If a PR deletes the golden item it breaks, there is nothing left to compare and
a naive join passes it. Same if it flips the item to `answerable: false`. Both
fail here as `ruler changed`: editing `deliverables/golden.json` is a human act
(`D06`), and it belongs in its own PR where it is the only thing being reviewed.
New items are allowed and reported as `unpaired` -- there is no baseline for
them yet, so they cannot be broken.

In CI the baseline is read from the BASE branch, never from the PR's own copy of
the file, for the same reason. See `D97`.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

from rag import score

K = score.HEADLINE_K


def _found(row: dict) -> bool:
    return row["rank"] is not None and row["rank"] <= K


def paired(baseline: list[dict], rows: list[dict]) -> dict:
    """Join on id and sort every item into exactly one bucket.

    `moved` is an item whose top-5 chunk ids changed without flipping -- not a
    failure, but the first thing to read when a gate result is surprising,
    because it separates "the code changed rankings" from "nothing moved".
    """
    base = {r["id"]: r for r in baseline}
    now = {r["id"]: r for r in rows}
    out = {"fixed": [], "broken": [], "moved": [], "unpaired": [],
           "missing": [], "relabelled": []}
    for i in sorted(base.keys() - now.keys()):
        if base[i]["answerable"]:
            out["missing"].append(i)
    for i in sorted(now.keys() - base.keys()):
        out["unpaired"].append(i)
    for i in sorted(base.keys() & now.keys()):
        b, r = base[i], now[i]
        if b["answerable"] != r["answerable"]:
            out["relabelled"].append(i)
            continue
        if not r["answerable"]:
            continue
        was, is_ = _found(b), _found(r)
        if was and not is_:
            out["broken"].append(i)
        elif is_ and not was:
            out["fixed"].append(i)
        elif b["hits"][:K] != r["hits"][:K]:
            out["moved"].append(i)
    return out


def blocked(result: dict) -> list[str]:
    """Reasons to fail. Empty means the gate passes."""
    reasons = []
    if result["broken"]:
        reasons.append(f"{len(result['broken'])} golden answer(s) left the top {K}: "
                       + " ".join(result["broken"]))
    if result["missing"]:
        reasons.append("ruler changed: answerable golden item(s) missing from this run: "
                       + " ".join(result["missing"]))
    if result["relabelled"]:
        reasons.append("ruler changed: answerable flag flipped on: "
                       + " ".join(result["relabelled"]))
    return reasons


def recall(rows: list[dict]) -> tuple[int, int]:
    answerable = [r for r in rows if r["answerable"]]
    return sum(_found(r) for r in answerable), len(answerable)


def render(baseline: list[dict], rows: list[dict]) -> tuple[str, list[str]]:
    """Plain text that reads the same in a terminal log and a job summary."""
    result = paired(baseline, rows)
    reasons = blocked(result)
    (bf, bn), (nf, nn) = recall(baseline), recall(rows)
    p = score.mcnemar_exact(len(result["fixed"]), len(result["broken"]))
    lines = [
        f"QUALITY GATE — retrieval, recall@{K}, paired by golden id",
        "",
        f"  baseline   {bf}/{bn} = {bf / bn:.2f}" if bn else "  baseline   (empty)",
        f"  this run   {nf}/{nn} = {nf / nn:.2f}" if nn else "  this run   (empty)",
        "",
        f"  fixed      {len(result['fixed']):>3}  {' '.join(result['fixed']) or '-'}",
        f"  broken     {len(result['broken']):>3}  {' '.join(result['broken']) or '-'}",
        f"  moved      {len(result['moved']):>3}  (top-{K} ids changed, found/not-found did not)",
        f"  unpaired   {len(result['unpaired']):>3}  (new items, no baseline yet)",
        f"  exact McNemar p = {p:.3f}  (context only; the gate reads `broken`)",
        "",
    ]
    lines += ([f"BLOCKED — {r}" for r in reasons] if reasons
              else ["PASSED — no golden answer lost"])
    return "\n".join(lines), reasons


def stamp(rows_path: pathlib.Path, out: pathlib.Path, provenance: dict) -> None:
    """Adopt a run as the baseline, recording what produced it.

    Provenance is not decoration: a baseline taken with a different reranker
    snapshot or on a different device is the first suspect when a later gate
    fails with `moved` items nobody's code explains.
    """
    rows = json.loads(rows_path.read_text())["rows"]
    out.write_text(json.dumps({"provenance": provenance, "rows": rows}, indent=1) + "\n")


def provenance() -> dict:
    from rag import embed, faithful, rerank

    stats = json.loads(embed.STATS_PATH.read_text())
    return {
        "machine": faithful.machine(),
        "embed_model": stats["model"], "embed_revision": stats["revision"],
        "embed_device": stats["run"]["device"],
        "rerank_model": rerank.MODEL_ID, "rerank_revision": rerank.MODEL_REVISION,
    }


def main() -> None:
    argv = sys.argv[1:]
    if "--stamp" in argv:
        i = argv.index("--stamp")
        stamp(pathlib.Path(argv[i + 1]), pathlib.Path(argv[i + 2]), provenance())
        print(f"baseline written to {argv[i + 2]}")
        return
    baseline = json.loads(pathlib.Path(argv[argv.index("--baseline") + 1]).read_text())
    rows = json.loads(pathlib.Path(argv[argv.index("--rows") + 1]).read_text())["rows"]
    text, reasons = render(baseline["rows"], rows)
    print(text)
    if baseline.get("provenance"):
        print(f"\nbaseline provenance: {json.dumps(baseline['provenance'])}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(f"```\n{text}\n```\n")
    sys.exit(1 if reasons else 0)


if __name__ == "__main__":
    main()
