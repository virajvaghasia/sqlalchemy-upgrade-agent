"""
Phase 2, Step 4 — one command, one score, and the parts of it that flatter us.

    uv run python -m rag.score                 # score deliverables/golden.json
    uv run python -m rag.score --validate      # check the file, retrieve nothing
    uv run python -m rag.score --baseline f    # paired comparison against an earlier run
    uv run python -m rag.score --save f        # write rows, to be a later run's baseline

Refusal accuracy on the unanswerable items is decided (D62) and NOT YET BUILT.
It needs generation rather than retrieval; the flag will be `--refusals`. It is
named here as missing rather than left to be discovered.

WHAT THIS MEASURES, AND WHAT IT REFUSES TO

Retrieval only, by default. `recall@k` and MRR answer *did the right page reach the
prompt* — a set-membership test a script can settle. Whether the resulting
answer was any good is a judgement, it is Phase 4's subject, and nothing here
pretends otherwise (§R4.1).

The four decisions this file implements, so they cannot drift back into prose:

  D58  a hit is any chunk sharing (heading_path, text) with a golden answer
       chunk, version tag ignored -- because 437 duplicate pairs have
       BYTE-IDENTICAL vectors and therefore identical scores against every
       possible query. No ranker can prefer the right copy, so penalising it
       measures the corpus. Items marked `version_sensitive` opt out.
  D59  retrieve top-20 once, report the whole curve. Depth is free: latency is
       the query embedding (~88 ms) and is the same at k=5 and k=50.
  D60  report every number with and without the `breakages` items, whose
       vocabulary overlaps their own answers 0.57 against 0.33 for developer
       phrasing.
  D61  a run is comparable to another run item by item. Two recall figures at
       n=50 have +/-0.131 intervals; the flipped items are the evidence.
  D62  refusal accuracy is printed apart from retrieval, never averaged in.

WHY IT READS chunks.jsonl AND NEVER FAILURES.md

`deliverables/FAILURES.md` truncates each shown chunk at 700 characters and
carries no chunk ids. Measuring duplicate slots off it returns 6 of 19; the
real figure from full text is 2. A rendered report is not the data (D58).
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys

from rag import corpus

GOLDEN_PATH = corpus.REPO_ROOT / "deliverables" / "golden.json"
CHUNKS_PATH = corpus.CORPUS_DIR / "chunks.jsonl"

# D59: one retrieval depth, deep enough that every reported k is a slice of it.
DEPTH = 20
REPORT_AT = (1, 3, 5, 10, 20)
# D54 ships DEFAULT_K = 5, so recall@5 is the headline and the rest is context.
HEADLINE_K = 5


# --- loading ---------------------------------------------------------------

def load_chunks() -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, CHUNKS_PATH.read_text().splitlines()) if r}


def dedup_key(chunk: dict) -> tuple:
    """The unit that decides a vector, and therefore the unit of a 'hit'.

    `rag/embed.py` prepends the heading path before embedding, so two chunks
    match iff BOTH their heading path and text match -- measured: 437 such
    pairs, 437 of 437 with byte-identical vectors, against 31 same-text
    different-heading pairs of which 0 of 31 are identical (D58).
    """
    return (tuple(chunk["heading_path"]), chunk["text"])


def load_golden(path: pathlib.Path = GOLDEN_PATH) -> list[dict]:
    if not path.exists():
        sys.exit(f"no golden set at {path.relative_to(corpus.REPO_ROOT)} — see phases/PHASE-2.md")
    return json.loads(path.read_text())["items"]


# --- validation ------------------------------------------------------------

REQUIRED = ("id", "question", "provenance", "answerable", "verified_by")
PROVENANCE = {"github", "stackoverflow", "migration_guide", "breakages"}


def validate(items: list[dict], chunks: dict[str, dict]) -> list[str]:
    """Every way a hand-written file can be wrong, checked before it is scored.

    This exists because the golden set is the ruler. A bent ruler does not
    announce itself -- it produces plausible numbers that are wrong in the same
    direction every time.
    """
    problems, seen = [], set()
    for i, it in enumerate(items):
        where = it.get("id", f"index {i}")
        for f in REQUIRED:
            if f not in it:
                problems.append(f"{where}: missing required field {f!r}")
        if it.get("id") in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(it.get("id"))
        if it.get("provenance") not in PROVENANCE:
            problems.append(f"{where}: provenance {it.get('provenance')!r} not in {sorted(PROVENANCE)}")
        # D06: a script may not decide an item is verified.
        if it.get("verified_by") != "human":
            problems.append(f"{where}: verified_by is {it.get('verified_by')!r}, not 'human' — "
                            "D06, only a person verifies. Unverified items are not scored.")
        if it.get("answerable"):
            ids = it.get("answer_chunks") or []
            if not ids:
                problems.append(f"{where}: answerable with no answer_chunks")
            for cid in ids:
                if cid not in chunks:
                    problems.append(f"{where}: answer_chunks names {cid!r}, which is not in the index")
            if not (it.get("answer_note") or "").strip():
                problems.append(f"{where}: no answer_note — nobody can tell verified from guessed")
        else:
            if it.get("answer_chunks"):
                problems.append(f"{where}: answerable is false but answer_chunks is set")
    return problems


# --- scoring one item ------------------------------------------------------

def rank_of_first_hit(hit_ids: list[str], item: dict, chunks: dict[str, dict]) -> int | None:
    """1-based rank of the first retrieved chunk that counts as the answer.

    None means it was not in the retrieved depth at all -- which is a different
    fact from 'ranked low', and Phase 1 is the reason this is recorded: rank 6
    was a wrong constant, rank 23 was search finding nothing (R4.3).
    """
    wanted_ids = set(item.get("answer_chunks") or [])
    if item.get("version_sensitive"):
        # D58's opt-out: for these, the version IS the answer (D10), so only the
        # exact chunk counts and a duplicate under the other tag is a miss.
        match = lambda cid: cid in wanted_ids
    else:
        wanted_keys = {dedup_key(chunks[c]) for c in wanted_ids if c in chunks}
        match = lambda cid: cid in wanted_ids or (
            cid in chunks and dedup_key(chunks[cid]) in wanted_keys)
    for i, cid in enumerate(hit_ids, start=1):
        if match(cid):
            return i
    return None


def duplicate_slots(hit_ids: list[str], chunks: dict[str, dict], upto: int) -> int:
    """Slots in the top-`upto` consumed by a second copy of a chunk already there.

    Reported as its own number rather than inferred from the gap between the
    permissive and strict recall figures, because a gap is a subtraction and
    this is a count (D58).
    """
    keys = [dedup_key(chunks[c]) for c in hit_ids[:upto] if c in chunks]
    return len(keys) - len(set(keys))


# --- aggregate -------------------------------------------------------------

def aggregate(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["answerable"]]
    ranks = [r["rank"] for r in answerable]
    found = [r for r in ranks if r is not None]
    out = {
        "n": len(rows),
        "n_answerable": len(answerable),
        "recall": {k: (sum(1 for r in ranks if r is not None and r <= k) / len(ranks)
                       if ranks else 0.0) for k in REPORT_AT},
        "recall_strict": {k: (sum(1 for r in answerable
                                  if r["rank_strict"] is not None and r["rank_strict"] <= k)
                              / len(answerable) if answerable else 0.0) for k in REPORT_AT},
        # MRR over answerable items; a miss contributes 0, which is the standard
        # and is worth stating because "average of 1/rank over the ones we found"
        # is a different and much flattering number.
        "mrr": (sum(1 / r for r in found) / len(ranks)) if ranks else 0.0,
        "median_rank_when_found": statistics.median(found) if found else None,
        "not_found_at_depth": sum(1 for r in ranks if r is None),
        "slots_lost_to_duplicates": sum(r["dup_slots"] for r in rows),
    }
    return out


def wilson_half_width(p: float, n: int, z: float = 1.96) -> float:
    """95% interval half-width. Printed next to recall so a 10-point move at
    n=50 is not mistaken for a result (D61)."""
    if n == 0:
        return 0.0
    d = 1 + z * z / n
    return z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d


def mcnemar_exact(fixed: int, broken: int) -> float:
    """Two-sided exact binomial on the discordant pairs.

    The right test for 'did this change help', because both runs answer the SAME
    questions. At n=50 the bar is roughly six clean fixes with no regressions
    (D61) -- stating that up front is better than discovering it after a sprint.
    """
    from math import comb
    n = fixed + broken
    if n == 0:
        return 1.0
    k = min(fixed, broken)
    return min(1.0, sum(comb(n, i) for i in range(k + 1)) / 2 ** n * 2)


# --- running ---------------------------------------------------------------

def score_items(items: list[dict], chunks: dict[str, dict], retrieve=None) -> list[dict]:
    """One row per item. `retrieve` is injected so tests need no Qdrant."""
    if retrieve is None:
        from rag import index
        retrieve = lambda q: [h.payload["chunk_id"] for h in index.retrieve(q, limit=DEPTH)]

    rows = []
    for it in items:
        hit_ids = retrieve(it["question"])[:DEPTH]
        strict = dict(it, version_sensitive=True)
        rows.append({
            "id": it["id"],
            "provenance": it["provenance"],
            "answerable": bool(it.get("answerable")),
            "hits": hit_ids,
            "rank": rank_of_first_hit(hit_ids, it, chunks) if it.get("answerable") else None,
            "rank_strict": rank_of_first_hit(hit_ids, strict, chunks) if it.get("answerable") else None,
            "dup_slots": duplicate_slots(hit_ids, chunks, HEADLINE_K),
        })
    return rows


def report(rows: list[dict]) -> None:
    def block(label: str, subset: list[dict]) -> None:
        if not subset:
            return
        a = aggregate(subset)
        h = wilson_half_width(a["recall"][HEADLINE_K], a["n_answerable"])
        print(f"\n{label}  —  {a['n']} items, {a['n_answerable']} answerable")
        print("  recall@k   " + "  ".join(f"@{k}={a['recall'][k]:.2f}" for k in REPORT_AT))
        print("  strict     " + "  ".join(f"@{k}={a['recall_strict'][k]:.2f}" for k in REPORT_AT))
        print(f"  MRR        {a['mrr']:.3f}")
        print(f"  recall@{HEADLINE_K}    {a['recall'][HEADLINE_K]:.2f}  ±{h:.3f}  (95%, Wilson)")
        med = a["median_rank_when_found"]
        print(f"  median rank when found  {med if med is not None else '—'}"
              f"   not in top-{DEPTH}: {a['not_found_at_depth']}")
        print(f"  slots lost to duplicates in top-{HEADLINE_K}: {a['slots_lost_to_duplicates']}")

    block("ALL ITEMS", rows)
    # D60: the breakages-derived items are the leakiest and must be separable.
    block("EXCLUDING provenance=breakages", [r for r in rows if r["provenance"] != "breakages"])
    by = {}
    for r in rows:
        by.setdefault(r["provenance"], []).append(r)
    for prov in sorted(by):
        block(f"provenance={prov}", by[prov])


def compare(rows: list[dict], baseline: list[dict]) -> None:
    """Paired comparison: which items flipped, and whether that is a result.

    Two recall percentages are not the evidence at n=50 -- their intervals
    overlap. The flipped items are (D61).
    """
    base = {r["id"]: r for r in baseline}
    fixed, broken = [], []
    for r in rows:
        b = base.get(r["id"])
        if not b or not r["answerable"]:
            continue
        was = b["rank"] is not None and b["rank"] <= HEADLINE_K
        now = r["rank"] is not None and r["rank"] <= HEADLINE_K
        if now and not was:
            fixed.append(r["id"])
        elif was and not now:
            broken.append(r["id"])
    p = mcnemar_exact(len(fixed), len(broken))
    print(f"\nPAIRED against baseline  (recall@{HEADLINE_K})")
    print(f"  fixed  {len(fixed):>3}  {', '.join(fixed) or '—'}")
    print(f"  broken {len(broken):>3}  {', '.join(broken) or '—'}")
    print(f"  exact McNemar p = {p:.3f}  "
          f"{'— significant' if p < 0.05 else '— NOT distinguishable from noise'}")


def main() -> None:
    argv = sys.argv[1:]
    chunks = load_chunks()
    items = load_golden()

    problems = validate(items, chunks)
    if problems:
        print(f"golden set has {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        if "--validate" in argv:
            sys.exit(1)
        # D06 in code: unverified items are dropped, loudly, not scored quietly.
        items = [i for i in items if i.get("verified_by") == "human"]
        print(f"\nscoring the {len(items)} verified item(s) only.\n")
    if "--validate" in argv:
        print(f"golden set OK: {len(items)} items, "
              f"{sum(1 for i in items if not i.get('answerable'))} unanswerable")
        return
    if not items:
        sys.exit("nothing verified to score — D06 says a human writes the verdicts.")

    rows = score_items(items, chunks)
    report(rows)
    if "--baseline" in argv:
        path = pathlib.Path(argv[argv.index("--baseline") + 1])
        compare(rows, json.loads(path.read_text())["rows"])
    if "--save" in argv:
        out = pathlib.Path(argv[argv.index("--save") + 1])
        out.write_text(json.dumps({"rows": rows}, indent=1) + "\n")
        print(f"\nsaved {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
