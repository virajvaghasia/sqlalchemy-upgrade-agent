"""
Phase 2, Step 4 — one command, one score, and the parts of it that flatter us.

    uv run python -m rag.score                 # score deliverables/golden.json
    uv run python -m rag.score --validate      # check the file, retrieve nothing
    uv run python -m rag.score --baseline f    # paired comparison against an earlier run
    uv run python -m rag.score --save f        # write rows, to be a later run's baseline

    uv run python -m rag.score --refusals      # D62, generation, printed apart
    uv run python -m rag.score --absents       # D70, why the missed items are missed

Two flags freeze an earlier row for a re-measure, and they are NOT interchangeable:

    --no-rerank                 hybrid without seat-5 CE  -- the D67 row
    --dense-only --no-rerank    dense + twin collapse     -- the D66 row

`--dense-only` ALONE is neither row. It turns off BM25 and leaves the reranker
on, a combination that has never shipped; it scores 0.53 where the D66 row is
0.52. Three docs told you to reproduce D66 with it until 2026-08-22.

Refusal accuracy on the unanswerable items (D62) is the one section that needs
generation rather than retrieval, so it is behind `--refusals` and costs ~50
model calls. It is never averaged into recall: a combined figure would rise as
the system got more cautious.

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
from rag.dedup import dedup_key

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

def score_items(
    items: list[dict],
    chunks: dict[str, dict],
    retrieve=None,
    *,
    hybrid: bool | None = None,
    rerank: bool | None = None,
) -> list[dict]:
    """One row per item. `retrieve` is injected so tests need no Qdrant.

    `hybrid`/`rerank` are passed to index.retrieve ONLY when set. None means "whatever
    index.retrieve ships", which is what rag.ask and the live page call. The quality
    gate's demo PR (#30) turned the reranker off in index.retrieve and PASSED, because
    this function used to pass rerank=True explicitly: the gate graded its own settings.
    """
    if retrieve is None:
        from rag import index
        overrides = {k: v for k, v in (("hybrid", hybrid), ("rerank", rerank)) if v is not None}
        retrieve = lambda q: [
            h.payload["chunk_id"]
            for h in index.retrieve(q, limit=DEPTH, **overrides)
        ]

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


# --- refusals (D62) --------------------------------------------------------
#
# This is the ONE section that needs generation. Everything above is retrieval:
# set membership, decidable by a script with no model running. A refusal only
# exists once something has been asked to answer.
#
# It retrieves at DEFAULT_K, not at DEPTH. The rest of this file takes 20 and
# slices it, because depth is free (D59) -- but refusal is a property of what
# SHIPS, and what ships is 5 (D54, which measured k=10 buying two over-fires
# and a fabrication). Scoring refusals at 20 would report the behaviour of a
# system nobody is running.

def refusal_rows(items: list[dict], chunks: dict[str, dict],
                 generate=None, retrieve=None, k: int | None = None) -> list[dict]:
    """Ask each question for real, and record whether the model declined.

    Both collaborators are injected so the tests need neither Qdrant nor Ollama.
    `k` defaults to what SHIPS -- see the note above; it is deliberately not
    DEPTH, and a test pins the difference.
    """
    from rag import ask as ask_mod

    if k is None:
        k = ask_mod.DEFAULT_K
    if retrieve is None:
        from rag import index
        retrieve = lambda q: index.retrieve(q, limit=k)
    if generate is None:
        generate = lambda prompt: ask_mod.generate(prompt)[0]

    rows = []
    for it in items:
        hits = retrieve(it["question"])
        hit_ids = [h.payload["chunk_id"] for h in hits]
        answer = generate(ask_mod.build_prompt(it["question"], hits))
        rows.append({
            "id": it["id"],
            "answerable": bool(it.get("answerable")),
            "refused": ask_mod.refused(answer),
            # Was the answer actually in front of the model when it declined?
            # This is the whole reason the section is worth printing: the same
            # word covers two unrelated defects, and only one of them is
            # generation's fault.
            "answer_in_prompt": (
                rank_of_first_hit(hit_ids, it, chunks) is not None
                if it.get("answerable") else False),
        })
    return rows


def report_refusals(rows: list[dict]) -> None:
    """Printed apart from retrieval and never averaged into it (D62).

    A combined 'accuracy' would go UP as the system got more cautious, because
    correct refusals and correct answers would land in the same numerator. The
    two columns move in opposite directions on purpose.
    """
    unanswerable = [r for r in rows if not r["answerable"]]
    answerable = [r for r in rows if r["answerable"]]

    correct = [r for r in unanswerable if r["refused"]]
    fabricated = [r for r in unanswerable if not r["refused"]]
    over = [r for r in answerable if r["refused"]]
    # The Q18/Q19 class: it refused with the answer sitting in the prompt.
    over_with = [r for r in over if r["answer_in_prompt"]]
    over_without = [r for r in over if not r["answer_in_prompt"]]

    def pct(n, d):
        return f"{n}/{d}" + (f"  ({n / d:.0%})" if d else "")

    print(f"\nREFUSALS  —  generation, at k={_ship_k()} (D62; not averaged into recall)")
    print(f"  unanswerable items                {len(unanswerable)}")
    print(f"    refused — correct               {pct(len(correct), len(unanswerable))}")
    print(f"    answered — FABRICATED           {pct(len(fabricated), len(unanswerable))}"
          + (f"   {', '.join(r['id'] for r in fabricated)}" if fabricated else ""))
    print(f"  answerable items                  {len(answerable)}")
    print(f"    refused — over-refusal          {pct(len(over), len(answerable))}")
    print(f"      with the answer IN the prompt {len(over_with):>3}"
          f"   generation defect (the Q18/Q19 class)"
          + (f"   {', '.join(r['id'] for r in over_with)}" if over_with else ""))
    print(f"      with the answer absent        {len(over_without):>3}"
          f"   honest — retrieval never supplied it")

    # END TO END, and it is computed here rather than in a doc.
    #
    # This figure was hand-derived in the docs twice (0.36 on the 50, 0.35 on
    # the 100) by subtracting one printed number from another. That is exactly
    # the arithmetic CLAUDE.md's measurement rule exists to stop -- a count
    # nobody can reproduce with a command. It is the single most important
    # number in the Phase 4 scorecard, because it is the only one describing
    # what a user actually receives, so it prints.
    #
    # Retrieval's recall is a CEILING. An item counts here only if the answer
    # chunk reached the prompt AND the model did not decline: getting the page
    # in front of the model and getting an answer out of it are separate
    # problems, and this is where the second one is priced.
    in_prompt = [r for r in answerable if r["answer_in_prompt"]]
    end_to_end = [r for r in in_prompt if not r["refused"]]
    n = len(answerable)
    print(f"\n  answer reached the prompt         {len(in_prompt):>3}/{n}"
          f"   <- retrieval's ceiling, at k={_ship_k()}")
    print(f"  ...and was answered, not refused  {len(end_to_end):>3}/{n}"
          f"   = {len(end_to_end) / n:.2f}   END TO END" if n else "")
    if n and in_prompt:
        lost = len(in_prompt) - len(end_to_end)
        print(f"  generation loses                  {lost:>3}/{n}"
              f"   = {lost / n:.2f} of the ceiling, invisible to every recall figure")


def absent_shapes(rows: list[dict], items: list[dict], chunks: dict[str, dict]) -> dict:
    """D70: are the answer chunks we cannot retrieve BROKEN, or just worded differently?

    An item absent from the top-20 is beyond reranking by construction — the
    reranker only reorders what retrieval already returned. So the absents are
    the only population that can justify recall-side work, and "improve chunking"
    is a recall-side lever. This asks whether they are shaped like the chunker's
    known defects.

    The three shapes are chunk.py's own predicates (D56 A and B, plus §R5.3's
    severed listing as shape C), so this survey and `chunk.py --audit` cannot
    disagree. The corpus-wide rate is carried alongside every count because a
    count without a base rate is not evidence: 4 of 30 would be alarming against
    a 0.2% corpus and unremarkable against a 10.7% one.

    The FOUND items are the control. Without it this measures how eagerly three
    regexes fire, not whether broken chunks are why retrieval missed.
    """
    from rag import chunk as chunk_mod

    by_id = {i["id"]: i for i in items}
    allc = list(chunks.values())
    nxt, _ = chunk_mod.neighbours(allc)

    def flags(c: dict) -> list[str]:
        out = []
        if chunk_mod.ends_open_shape(c):
            out.append("A")
        if chunk_mod.opens_backward_shape(c):
            out.append("B")
        n = nxt.get(c["id"])
        if n is not None and chunk_mod.severed_listing(c, n):
            out.append("C")
        return out

    def survey(subset: list[dict]) -> tuple[list[tuple[str, str, list[str]]], int]:
        seen = []
        for r in sorted(subset, key=lambda r: r["id"]):
            for cid in by_id[r["id"]]["answer_chunks"]:
                c = chunks.get(cid)
                if c is not None:
                    seen.append((r["id"], cid, flags(c)))
        return seen, sum(1 for _, _, f in seen if f)

    answerable = [r for r in rows if r["answerable"]]
    absent_survey, absent_flagged = survey([r for r in answerable if r["rank"] is None])
    found_survey, found_flagged = survey([r for r in answerable if r["rank"] is not None])

    n_boundaries = sum(1 for c in allc if c["id"] in nxt
                       and nxt[c["id"]]["char_start"] >= c["char_end"])
    base = chunk_mod.audit(allc)
    return {
        "absent_ids": sorted(r["id"] for r in answerable if r["rank"] is None),
        "found_items": sum(1 for r in answerable if r["rank"] is not None),
        "absent_chunks": absent_survey,
        "absent_flagged": absent_flagged,
        "found_chunks": found_survey,
        "found_flagged": found_flagged,
        # Corpus-wide rates, so every count above has something to be judged against.
        "base": {
            "A": base["ends_open"] / base["n_chunks"],
            "B": base["opens_backward"] / base["n_chunks"],
            "either": base["either"] / base["n_chunks"],
            "C": sum(1 for c in allc if c["id"] in nxt
                     and chunk_mod.severed_listing(c, nxt[c["id"]])) / max(n_boundaries, 1),
        },
    }


def report_absents(a: dict) -> None:
    n = len(a["absent_chunks"])
    print(f"\nABSENT FROM TOP-{DEPTH} — are their answer chunks BROKEN, or just worded "
          f"differently?  (D70)")
    print(f"  {len(a['absent_ids'])} answerable items, {n} answer chunks between them")
    print("  " + ", ".join(a["absent_ids"]))
    if not n:
        return

    counts = {k: sum(1 for _, _, f in a["absent_chunks"] if k in f) for k in "ABC"}
    print(f"\n  shape of those {n} answer chunks                  count    corpus")
    print(f"    A  ends announcing what never follows        {counts['A']:5}"
          f"    {a['base']['A']:5.1%}")
    print(f"    B  opens pointing at what is not here        {counts['B']:5}"
          f"    {a['base']['B']:5.1%}")
    print(f"    C  boundary severed inside a code listing    {counts['C']:5}"
          f"    {a['base']['C']:5.1%}  of cuts")
    print(f"    any of the three                             {a['absent_flagged']:5}"
          f"    {a['base']['either']:5.1%}")

    fn = len(a["found_chunks"])
    rate = f" = {a['found_flagged'] / fn:.0%}" if fn else ""
    print(f"\n  control — the {a['found_items']} items retrieval DOES find: "
          f"{a['found_flagged']} of {fn} answer chunks flagged{rate}")

    flagged = [(g, c, f) for g, c, f in a["absent_chunks"] if f]
    if flagged:
        print("\n  flagged, and each one wants reading before it is believed:")
        for gid, cid, f in flagged:
            print(f"    {gid}  {cid}  shape {'+'.join(f)}")
    else:
        print("\n  Not one of them. Chunk repair cannot be the lever that reaches these"
              "\n  items; the mismatch is vocabulary, not a broken boundary (D70).")


def _ship_k() -> int:
    from rag import ask as ask_mod
    return ask_mod.DEFAULT_K


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

    if "--refusals" in argv:
        # D62: its own section, its own retrieval depth, its own run. Done first
        # so a missing Ollama fails before 50 retrievals have been paid for.
        report_refusals(refusal_rows(items, chunks))

    # Default is hybrid+rerank (`D67`/`D68`). Flags re-measure earlier rows.
    # None = index.retrieve's shipped default; a flag is the only override.
    hybrid = False if "--dense-only" in argv else None
    rerank = False if "--no-rerank" in argv else None
    modes = []
    if hybrid is False:
        modes.append("dense-only")
    if rerank is False:
        modes.append("no-rerank")
    if modes:
        print(f"mode: {', '.join(modes)}\n")
    rows = score_items(items, chunks, hybrid=hybrid, rerank=rerank)
    report(rows)
    if "--absents" in argv:
        # D70: printed after the curve, because it only makes sense once you know
        # how many items are absent. Costs no extra retrieval -- it reads `rows`.
        report_absents(absent_shapes(rows, items, chunks))
    if "--baseline" in argv:
        path = pathlib.Path(argv[argv.index("--baseline") + 1])
        compare(rows, json.loads(path.read_text())["rows"])
    if "--save" in argv:
        out = pathlib.Path(argv[argv.index("--save") + 1])
        out.write_text(json.dumps({"rows": rows}, indent=1) + "\n")
        print(f"\nsaved {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
