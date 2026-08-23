"""
Phase 4 — grade the ANSWER, not the search.

    uv run python -m rag.judge --citations              # deterministic; no model, no key
    uv run python -m rag.judge --citations --limit 20
    uv run python -m rag.judge --citations --save f.json # keep the rows; a run costs ~100 calls

Phase 3 closed retrieval at recall@5 = 0.64. End to end the system answers
0.43 (D72), so twenty-one points are lost AFTER the right page is already in
the prompt. Every number in PHASE-3.md is computed above that gap. This module
is where the gap gets measured.

The first full run said something sharper than "generation is lossy" (D73):
of the 48 items that got an answer at all, **31 cite nothing**, and **26 of
the 28 answers containing code** put executable code on screen with no source
attached. Mean coverage is 0.07 -- five pages retrieved, and the answer points
at roughly a third of one. Phase 1's ask.py opens with "SOURCES ARE NOT
DECORATION"; measured, they mostly are.

TWO HALVES, AND ONLY ONE OF THEM NEEDS A MODEL

  * **Citation integrity** -- deterministic. Does `[4]` point at a source that
    exists? Does the code block carry any citation at all? Counting brackets is
    not a judgement, so it needs no model, no API key, and no free tier. It runs
    in CI-adjacent time and it is exact.
  * **Faithfulness** -- needs a judge model, because "is this claim supported by
    that passage" is a reading task. Behind its own flag for the same reason
    `--refusals` is (D62): it costs generations, and a number that expensive
    should not be produced as a side effect of asking for a cheap one.

Build the deterministic half first and completely. It is the half that can be
run today, by anyone, with no key -- and it already catches the defect that
motivated the phase.

THE DEFECT THIS WAS BUILT FROM

`g065`. The system answered an unanswerable question with an Alembic script
calling `op.create_view` and `op.drop_view`. `hasattr(Operations,
"create_view")` is False on alembic 1.19.1; `op.create_table`, in the same
script, is real. Two invented calls beside two working ones -- **and no
citation on the code block**.

That last clause is the part a machine can see. Nothing here can tell whether
`op.create_view` exists (that is verify_2_0's job, on a different library, and
`tools/audit_golden_fullbar.py` already runs real 2.0.51). What it can say is
that the model emitted executable-looking code and pointed at no source for it,
which is the shape of a fabrication whether or not this particular one was.

WHY OUT-OF-RANGE CITATIONS ARE A SEPARATE COUNT FROM UNCITED

`rag/probe.py` `signals()` builds its citation set as `{n for n in range(1,
len(hits) + 1) if f"[{n}]" in answer}` -- it only ever looks for numbers that
exist. An answer citing `[7]` when five sources were supplied contributes
nothing to that set, so a five-source answer citing only `[7]` reads there as
`uncited`. Two different defects, and they want different fixes: `uncited` is a
model that did not cite, `out_of_range` is a model that cited a source it was
never given. The second is strictly worse and much rarer, which is exactly why
it needs its own count rather than being absorbed.

This module does NOT duplicate probe.py's detectors. It imports `ask.refused`
like probe.py does, for the same reason: probe.py once held a second copy of a
symbol test and it silenced the very signal it existed for.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

from rag import ask, corpus

GOLDEN_PATH = corpus.REPO_ROOT / "deliverables" / "golden.json"

# A citation marker as the prompt asks for it: [1], [12]. Deliberately not
# matching [a] or [1,2] -- the SYSTEM prompt specifies a bare integer, and
# widening this to "whatever looks citation-ish" would quietly forgive a model
# that stopped following the format.
CITATION = re.compile(r"\[(\d+)\]")

# A fenced code block. The model is asked for migration code, so this fires a
# lot; that is fine, because the count that matters is how many of them carry
# no citation at all.
CODE_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)

# Prose long enough that saying nothing about sources is a real omission.
# probe.py uses the same threshold for `uncited` and the two must agree.
MIN_WORDS_FOR_UNCITED = 15


def citations(answer: str) -> list[int]:
    """Every [n] in the answer, in order, duplicates collapsed."""
    return sorted({int(m.group(1)) for m in CITATION.finditer(answer)})


def code_blocks(answer: str) -> list[str]:
    return [m.group(1) for m in CODE_FENCE.finditer(answer)]


def uncited_code_blocks(answer: str) -> int:
    """Fenced blocks with no [n] inside them and none on the line before.

    Scoped to the block and its introducing line rather than the whole answer:
    an answer that cites [2] three paragraphs earlier and then emits an
    uncited script is the g065 shape, and crediting the distant citation would
    hide it.
    """
    n = 0
    for m in CODE_FENCE.finditer(answer):
        block = m.group(0)
        # The introducing line is the last line with anything on it -- markdown
        # puts a blank line before a fence, so "the previous line" is usually
        # empty. Taking it literally credited nothing and counted every properly
        # cited block as uncited.
        before = [l for l in answer[:m.start()].split("\n") if l.strip()]
        head = before[-1] if before else ""
        if not CITATION.search(block) and not CITATION.search(head):
            n += 1
    return n


def citation_report(answer: str, n_sources: int) -> dict:
    """Everything checkable about an answer's citations without reading it.

    `n_sources` is how many chunks were actually put in the prompt, so it is the
    range a citation is allowed to point into. Passing the retrieval DEPTH here
    instead of the shipped k would silently legalise citations to sources the
    model never saw.
    """
    cited = citations(answer)
    in_range = [n for n in cited if 1 <= n <= n_sources]
    out_of_range = [n for n in cited if n < 1 or n > n_sources]
    substantial = len(answer.split()) > MIN_WORDS_FOR_UNCITED
    return {
        "refused": ask.refused(answer),
        "cited": cited,
        "in_range": in_range,
        # A source that does not exist. probe.py structurally cannot see these.
        "out_of_range": out_of_range,
        "n_sources": n_sources,
        # Same definition as probe.py's, deliberately.
        "uncited": not in_range and substantial,
        "single_source": len(in_range) == 1 and n_sources > 1,
        "code_blocks": len(code_blocks(answer)),
        "uncited_code_blocks": uncited_code_blocks(answer),
        # Coverage: of the pages we paid to retrieve and put in the prompt, how
        # many did the answer actually use? Low coverage is not a defect on its
        # own -- one good page can answer a question -- but it is the number
        # that says whether k=5 is earning its tokens.
        "coverage": round(len(in_range) / n_sources, 3) if n_sources else 0.0,
    }


def aggregate(rows: list[dict]) -> dict:
    """Counts over answered rows. Refusals are excluded from every citation
    figure: an answer that declines has nothing to cite, and counting it as
    `uncited` would make the system look worse the more honest it got --
    the same trap D62 refused for recall."""
    answered = [r for r in rows if not r["refused"]]
    n = len(answered)
    return {
        "n": len(rows),
        "n_refused": len(rows) - n,
        "n_answered": n,
        "out_of_range": sum(1 for r in answered if r["out_of_range"]),
        "uncited": sum(1 for r in answered if r["uncited"]),
        "single_source": sum(1 for r in answered if r["single_source"]),
        "with_code": sum(1 for r in answered if r["code_blocks"]),
        "uncited_code": sum(1 for r in answered if r["uncited_code_blocks"]),
        "mean_coverage": round(sum(r["coverage"] for r in answered) / n, 3) if n else 0.0,
    }


def report(rows: list[dict], agg: dict) -> None:
    print(f"\nCITATION INTEGRITY  —  deterministic, no judge model (Phase 4)")
    print(f"  items asked                    {agg['n']:>4}")
    print(f"    refused, nothing to cite     {agg['n_refused']:>4}")
    print(f"    answered                     {agg['n_answered']:>4}   <- every rate below is over these")
    if not agg["n_answered"]:
        return
    pct = lambda k: f"{agg[k] / agg['n_answered']:6.1%}"
    print(f"\n  cites a source that does not exist  {agg['out_of_range']:>4}  {pct('out_of_range')}")
    print(f"  no citation at all                  {agg['uncited']:>4}  {pct('uncited')}")
    print(f"  cites only one of the sources       {agg['single_source']:>4}  {pct('single_source')}")
    print(f"  answers containing code             {agg['with_code']:>4}  {pct('with_code')}")
    if agg["with_code"]:
        # Rate over answers WITH code, not over all answers: "3 of 4 code
        # blocks are uncited" and "3 of 91 answers" are different claims, and
        # the second one hides the defect.
        print(f"    of those, code with no citation   {agg['uncited_code']:>4}"
              f"  {agg['uncited_code'] / agg['with_code']:6.1%}")
    k = rows[0]["n_sources"] if rows else 0
    print(f"\n  mean source coverage                {agg['mean_coverage']:.2f}"
          f"   (fraction of the {k} prompt sources an answer cites)")

    # D73: split by provenance, because the first run left a mechanism open.
    # Phase 1's probe reported `uncited` on 3 of its 11 answered questions;
    # this reports 31 of 48. The bands do not overlap, so they are not the same
    # rate measured twice -- and the obvious suspect is phrasing, which D63
    # already proved decides retrieval. This is the split that tests it.
    provs = sorted({r.get("provenance") for r in rows if r.get("provenance")})
    if len(provs) > 1:
        print("\n  by provenance (answered items only)")
        print(f"    {'':<16}{'answered':>9}{'uncited':>9}{'rate':>7}")
        for prov in provs:
            sub = [r for r in rows if r.get("provenance") == prov and not r["refused"]]
            if not sub:
                continue
            u = sum(1 for r in sub if r["uncited"])
            print(f"    {prov:<16}{len(sub):>9}{u:>9}{u / len(sub):>7.0%}")

    bad = [r for r in rows if not r["refused"] and (r["out_of_range"] or r["uncited_code_blocks"])]
    if bad:
        print("\n  the two that need a person, named:")
        for r in bad:
            why = []
            if r["out_of_range"]:
                why.append(f"cites {r['out_of_range']} of {r['n_sources']} sources")
            if r["uncited_code_blocks"]:
                why.append(f"{r['uncited_code_blocks']} uncited code block(s)")
            print(f"    {r['id']}  {'; '.join(why)}")


def judge_rows(items: list[dict], k: int | None = None, generate=None) -> list[dict]:
    """Ask each item and grade the answer's citations.

    Retrieves at the k that SHIPS, not at score.py's DEPTH -- for the same
    reason `--refusals` does (D62). Citation behaviour is a property of the
    configured system; grading it over twenty sources would describe a system
    nobody runs.
    """
    from rag import index

    k = k or ask.DEFAULT_K
    gen = generate or ask.generate
    rows = []
    for it in items:
        hits = index.retrieve(it["question"], limit=k)
        prompt = ask.build_prompt(it["question"], hits)
        out = gen(prompt)
        # ask.generate returns (answer, timings); injected fakes may return
        # just the text. Accept both rather than making every test build a tuple.
        answer = out[0] if isinstance(out, tuple) else out
        rows.append(dict(citation_report(answer, len(hits)), id=it["id"],
                         provenance=it.get("provenance")))
    return rows


def main() -> None:
    argv = sys.argv[1:]
    items = json.loads(GOLDEN_PATH.read_text())["items"]
    items = [i for i in items if i.get("verified_by") == "human"]
    if "--limit" in argv:
        items = items[: int(argv[argv.index("--limit") + 1])]

    if "--citations" not in argv:
        sys.exit(__doc__.strip().splitlines()[0] + "\n\n  pass --citations")

    rows = judge_rows(items)
    report(rows, aggregate(rows))
    if "--save" in argv:
        # Each run costs ~100 generations. Saving the rows means the next
        # question about them -- a provenance split, a per-item read -- does not
        # cost another hour. score.py --save exists for the same reason.
        out = pathlib.Path(argv[argv.index("--save") + 1])
        out.write_text(json.dumps({"rows": rows}, indent=1) + "\n")
        print(f"\nsaved {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
