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
#
# The lookbehind is subscript syntax, not pedantry. `keys[0]`, `row[1]` and
# `argv[1]` are bracket-integers too, and the first version of this regex read
# them as citations. Measured over the 300 saved D/H/I answers it fires three
# times -- `row[keys[0]]`, `keys[1]`, and a prose mention of `row[0]` -- and
# every one of them was scored as the model citing a source numbered 0 that
# does not exist. A bare `[0]` in prose still is exactly that, which is why the
# rule is "not preceded by an identifier char, `]` or `)`" rather than "ignore
# code blocks": the g121 case is in prose, and a `# [2]` comment inside a fence
# is a real citation that uncited_code_blocks() must keep seeing.
#
# Same shape as D76. H writes far more code than D, so the false positive only
# became visible once the variant under test started complying -- the second
# time in this phase that a better answer broke the instrument reading it.
CITATION = re.compile(r"(?<![\w\]\)])\[(\d+)\]")

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


# A dotted API call in the answer's code: `op.create_view(`, `session.get(`,
# `Query.from_self(`. Deliberately NOT bare identifiers -- `subq`, `stmt`, `ua`
# are the model's own local variables and grounding them is meaningless.
API_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\(")


def api_calls(answer: str) -> list[str]:
    """Every dotted call inside the answer's code blocks, deduplicated.

    Scoped to code blocks: prose naming `Query.from_self` is usually discussing
    the thing the question asked about, while code CALLING it is a claim that
    this is how you do it.
    """
    return sorted({m.group(1) for block in code_blocks(answer)
                   for m in API_CALL.finditer(block)})


def ungrounded_calls(answer: str, source_texts: list[str], question: str = "") -> list[str]:
    """Dotted calls the answer makes that appear in NONE of its sources.

    This is the deterministic half of faithfulness, and the only Phase 4 metric
    that reaches the defect the prompt work could not (D74: fabrications sat at
    2 under every wording tried).

    **It measures GROUNDEDNESS, not existence, and the difference matters.**
    `op.create_table` is a real Alembic function; if it is not in any retrieved
    source then an answer calling it is still unsupported by the pages the
    system was given, which is exactly what a RAG faithfulness metric should
    say. Whether a symbol exists at all is a different question, answered
    against the real library by tools/audit_golden_fullbar.py. Neither
    subsumes the other: g065 invented `op.create_view` (fails both) beside
    `op.create_table` (exists, still ungrounded here).

    The question is subtracted because a developer pasting their own broken code
    puts identifiers in the prompt that the docs will never contain -- flagging
    the model for echoing them back would measure the questioner, not the answer.

    Matching is probe.py's `_contains`, imported rather than reimplemented: a
    naive `symbol in text` counted `relation` inside every `relationship`, 798
    chunks against 0, and silenced the signal it existed for.
    """
    from rag.probe import _contains

    haystack = "\n".join(source_texts) + "\n" + question
    out = []
    for call in api_calls(answer):
        # Ground on the attribute chain and on its last segment: docs often
        # write `Session.get` where the answer writes `session.get`, and
        # rejecting that would report a style difference as a fabrication.
        tail = call.rsplit(".", 1)[-1]
        if not _contains(haystack, call) and not _contains(haystack, tail):
            out.append(call)
    return out


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
        # Answers calling an API that appears in none of their own sources.
        "ungrounded": sum(1 for r in answered if r.get("ungrounded")),
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
    if any("ungrounded" in r for r in rows):
        print(f"  calls an API in none of its sources {agg['ungrounded']:>4}  {pct('ungrounded')}")
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

    bad = [r for r in rows if not r["refused"]
           and (r["out_of_range"] or r["uncited_code_blocks"] or r.get("ungrounded"))]
    if bad:
        print("\n  the two that need a person, named:")
        for r in bad:
            why = []
            if r["out_of_range"]:
                why.append(f"cites {r['out_of_range']} of {r['n_sources']} sources")
            if r["uncited_code_blocks"]:
                why.append(f"{r['uncited_code_blocks']} uncited code block(s)")
            if r.get("ungrounded"):
                why.append("ungrounded: " + ", ".join(r["ungrounded"][:4]))
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
        source_texts = [h.payload["text"] for h in hits]
        out = gen(prompt)
        # ask.generate returns (answer, timings); injected fakes may return
        # just the text. Accept both rather than making every test build a tuple.
        answer = out[0] if isinstance(out, tuple) else out
        rows.append(dict(citation_report(answer, len(hits)), id=it["id"],
                         provenance=it.get("provenance"),
                         ungrounded=ungrounded_calls(answer, source_texts, it["question"])))
    return rows


# --- the open cell ----------------------------------------------------------
#
# An item that got an ANSWER while its verified answer chunk was NOT in the
# prompt. Every automated metric in this repo scores it as neither a win nor a
# loss and then walks past it: --refusals counts it nowhere, recall@5 already
# said the page was missed, and citation integrity only asks whether the
# brackets point somewhere real.
#
# It is the one cell where the two possible readings are opposite:
#
#   the answer is CORRECT   -> the golden set's answer chunk is not the only
#                              page that answers this, and the item is a win
#                              no scorer can see
#   the answer is WRONG     -> the model answered from nothing, and the same
#                              scorers count it as harmless
#
# D06 says a human decides which, and no script may. This renders the sheet;
# it does not rule on it. The precedent is the golden signature, closed on a
# risk-weighted read of ten (§H CLOSED, 2026-08-21).
#
# Why it matters for the prompt decision specifically: prompt H answers 62
# items to D's 48, and the open cell grows 7 -> 13 with it. Whether that is H
# earning fourteen more answers or H talking past the evidence is exactly this
# sheet, and it cannot be settled by counting.


def open_cell(rows: list[dict]) -> list[dict]:
    """Answered, answerable, and the verified page never reached the prompt."""
    return [
        r for r in rows
        if not r.get("failed")
        and r.get("answerable")
        and not r.get("answer_in_prompt")
        and not ask.refused(r["answer"])
    ]


def open_cell_sheet(saved: dict, items: list[dict], out: pathlib.Path) -> int:
    """Render the open-cell answers for a human to rule on, one variant per
    section. Reads the SAVED answers rather than regenerating: D54 says a
    re-run drifts, and a sheet that disagrees with the run it is meant to
    explain is worse than no sheet.
    """
    by_id = {i["id"]: i for i in items}
    lines = [
        "# The open cell — answers with no verified page in the prompt",
        "",
        "Generated by `rag.judge --open-cell`. **Claude renders this sheet and does",
        "not rule on it** (`D06`). For each answer below, the question is only:",
        "",
        "> Read against real SQLAlchemy 2.0.51 — **is this answer correct?**",
        "",
        "`CORRECT` means the golden set's answer chunk is not the only page that",
        "answers the question, and the system did better than the scorer can see.",
        "`WRONG` means the model answered from nothing and every current metric",
        "scored it as harmless.",
        "",
    ]
    # Which items to read first, when there is more than one variant. The
    # shared ones are a property of the system; the ones a variant ADDS are the
    # ones that decide whether shipping it is safe. H answers fourteen more
    # items than D, and six of them land here -- that six is the ship decision.
    cells = {v: {r["id"] for r in open_cell(rows)} for v, rows in saved.items()}
    if len(cells) > 1:
        control = next(iter(cells))
        lines += [
            "## Read these first",
            "",
            f"Shared with the control (`{control}`) and therefore not a reason to "
            "prefer one prompt over another:",
            "",
        ]
        shared = set.intersection(*cells.values())
        lines += [f"- {', '.join('`%s`' % i for i in sorted(shared)) or '(none)'}", ""]
        for v, ids in cells.items():
            if v == control:
                continue
            added = sorted(ids - cells[control])
            lines += [
                f"**`{v}` adds {len(added)}** — these are answers the control "
                f"refused, so they exist only because `{v}` was more willing: "
                f"{', '.join('`%s`' % i for i in added) or '(none)'}",
                "",
            ]
        lines += ["---", ""]

    n = 0
    for variant, rows in saved.items():
        cell = open_cell(rows)
        n += len(cell)
        lines += [f"## Variant `{variant}` — {len(cell)} items", ""]
        for r in cell:
            it = by_id.get(r["id"], {})
            lines += [
                f"### `{r['id']}`  ({r.get('provenance', '?')})",
                "",
                f"**Question.** {it.get('question', '(not in golden.json)')}",
                "",
                f"**Golden says the answer is in:** "
                f"{', '.join('`%s`' % c for c in it.get('answer_chunks', [])) or '(none listed)'}"
                f" — none of which reached the prompt.",
                "",
                f"**Cited:** {r.get('cited') or 'nothing'}"
                f" | **code blocks:** {r.get('code_blocks', 0)}"
                f" | **ungrounded calls:** {r.get('ungrounded') or 'none'}",
                "",
                "**Answer.**",
                "",
                "```",
                r["answer"].strip(),
                "```",
                "",
                "**Verdict:** `CORRECT` / `WRONG` / `PARTIAL` — _______",
                "",
                "---",
                "",
            ]
    out.write_text("\n".join(lines))
    return n


def main() -> None:
    argv = sys.argv[1:]
    items = json.loads(GOLDEN_PATH.read_text())["items"]
    items = [i for i in items if i.get("verified_by") == "human"]
    if "--limit" in argv:
        items = items[: int(argv[argv.index("--limit") + 1])]

    if "--open-cell" in argv:
        # Reads a saved sweep (rag.compare_prompts --golden --save) rather than
        # generating: the sheet must describe the run it is filed against.
        src = pathlib.Path(argv[argv.index("--open-cell") + 1])
        out = pathlib.Path(argv[argv.index("--out") + 1]) if "--out" in argv else \
            pathlib.Path("deliverables/OPEN-CELL-REVIEW.md")
        saved = json.loads(src.read_text())
        if "rows" in saved:                      # a judge --save file, one variant
            saved = {"(saved run)": saved["rows"]}
        n = open_cell_sheet(saved, items, out)
        print(f"{n} open-cell answers across {len(saved)} variant(s) -> {out}")
        print("D06: a human rules on these. This script does not.")
        return

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
