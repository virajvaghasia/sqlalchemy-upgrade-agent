"""
Phase 1, Step 5 — run questions with known answers and record where it fails.

    uv run python -m rag.probe                  # run everything, write the report
    uv run python -m rag.probe --only skew      # one category
    uv run python -m rag.probe --list           # the question set, no model calls
    uv run python -m rag.probe --k 6            # a different top-k, to test the cut

Writes `deliverables/FAILURES.md`. That file is the Phase 1 deliverable and the
argument for everything in Phase 3.

THIS SCRIPT DOES NOT GRADE ANSWERS, AND THAT IS THE POINT

`study/09-DECISIONS.md` **D06**: the golden dataset is hand-verified, never
auto-generated. If this script decided which answers were correct, Phase 2 would
be scoring retrieval against a key written by the same family of model that
produced the answers — measuring self-consistency rather than correctness.

So every answer is written out marked **UNVERIFIED**, for a human to judge. What
the script does instead is compute **mechanical signals** — things that are true
or false without opinion:

    refused          the model declined to answer
    uncited          the answer makes claims with no [n] citation
    duplicate_slots  the same text occupied more than one top-k slot (D38)
    version_mixed    top-k contains both 1.4 and 2.0 passages
    symbol_missing   no retrieved chunk contains the exact symbol asked about
    single_source    every citation points at one source — the answer may not
                     survive that source being wrong

None of those is automatically a failure. `version_mixed` is usually fine and
occasionally the whole problem; `refused` is correct when the corpus genuinely
cannot answer. They are **where to look**, not verdicts.

WHERE THE QUESTIONS COME FROM

`deliverables/BREAKAGES.md` — 23 breakages measured against real 2.0.51 and
verified by hand. Two properties make it the right source:

  - **The answers are already known and already checked**, which is what
    `PHASE-1.md` Step 5 asks for: "run questions you know the answers to".
  - **It is deliberately NOT in the corpus** (D09), so asking about it is a fair
    test rather than a lookup of the answer key.

The `symbol` field on each question is the mechanical half — the exact string
that has to appear in a retrieved chunk for the answer to be *retrievable at
all*. It is not an expected answer, and no expected answers are stored here.
"""

from __future__ import annotations

import json
import sys
import time

from rag import ask, corpus, index

REPORT_PATH = corpus.REPO_ROOT / "deliverables" / "FAILURES.md"
VERDICTS_PATH = corpus.REPO_ROOT / "deliverables" / "verdicts.json"


def _verdicts() -> dict:
    """Confirmed verdicts, so a regeneration preserves them (see tools/apply_verdicts.py)."""
    if not VERDICTS_PATH.exists():
        return {}
    import json as _json
    return {k: v for k, v in _json.loads(VERDICTS_PATH.read_text().replace("\r", ""))
            .items() if not k.startswith("_")}


VERDICTS = _verdicts()

# category -> why it is in the set
CATEGORIES = {
    "symbol": "exact symbol names — where dense retrieval is supposed to be weakest",
    "skew": "the answer differs between 1.4 and 2.0, so a wrong-version page is a wrong answer",
    "spanning": "the answer needs more than one chunk",
    "absent": "the corpus genuinely cannot answer — the honest output is a refusal",
    "silent": "a breakage that raises nothing, so the docs barely discuss it",
}

# question, category, and the exact string that must appear in a retrieved chunk
# for the answer to be retrievable. NO expected answers — see the docstring.
QUESTIONS = [
    # --- exact symbol names (BREAKAGES #12, #13, #5, #6, #18, #10) -----------
    ("what replaces Query.from_self() in SQLAlchemy 2.0?", "symbol", "from_self"),
    ("Query.join with aliased=True stopped working, what do I use?", "symbol", "aliased"),
    ("engine.table_names() is gone — what replaces it?", "symbol", "table_names"),
    ("engine.has_table() no longer exists, what is the replacement?", "symbol", "has_table"),
    ("row.keys() raises in 2.0, how do I get the column names?", "symbol", "keys()"),
    ("orm.relation() is not available any more, what is it called now?", "symbol", "relation"),

    # --- version skew (the future=True case, measured in Step 1) ------------
    ("should I pass future=True to create_engine?", "skew", "future"),
    ("is Session.autocommit still supported?", "skew", "autocommit"),
    ("can I still use session.begin() with subtransactions?", "skew", "subtransaction"),
    ("does MetaData still accept a bind argument?", "skew", "bind"),

    # --- answers that span chunks ------------------------------------------
    ("how do I migrate select([col1, col2]) to the 2.0 form?", "spanning", "select("),
    ("what is the full set of steps to migrate a 1.4 app to 2.0?", "spanning", "migration"),
    ("how do I get scalar values instead of Row objects from session.execute?",
     "spanning", "scalars"),
    ("why do I need .unique() when using joinedload on a collection?", "spanning", "unique()"),

    # --- the corpus cannot answer these (D07 — the API reference hole) ------
    ("what is the exact signature and full argument list of Session.execute?", "absent",
     None),
    ("list every keyword argument accepted by relationship()", "absent", None),
    ("what does the SQLAlchemy 2.1 release change?", "absent", None),

    # --- the silent one (BREAKAGES #23) -------------------------------------
    ("if I write comment.issue = issue instead of issue.comments.append(comment), "
     "does the comment get saved?", "silent", "cascade_backrefs"),
    ("why would an object assigned to a many-to-one relationship never be inserted?",
     "silent", "backref"),
]


def _contains(text: str, symbol: str) -> bool:
    """
    Whole-symbol match, not substring.

    Naive `symbol in text` counted `relation` inside every `relationship`: 798
    chunks against the 0 that actually document `orm.relation()`. That made a
    ceiling case look like a retrieval failure and, worse, silenced the very
    signal meant to tell them apart — `symbol_missing` can never fire for a
    symbol that is a prefix of a common word. `bind` had the same shape.

    So a symbol ending in an identifier character must not be followed by one.
    Symbols ending in punctuation — `keys()`, `select(` — are already
    self-delimiting and match literally.
    """
    import re as _re

    pattern = _re.escape(symbol)
    if symbol[-1].isalnum() or symbol[-1] == "_":
        pattern += r"(?![A-Za-z0-9_])"
    return _re.search(pattern, text, _re.I) is not None


_CORPUS_CHUNKS: list[dict] | None = None


def corpus_chunk_count(symbol: str) -> int:
    """How many chunks in the whole corpus contain this string.

    This is the number that turns a vague failure into an actionable one, and it
    is the most important thing this script computes. `symbol_missing` on its
    own says only "the answer was not in the top-k". Combined with this:

        in corpus, not retrieved  ->  RETRIEVAL failed. Phase 3 can fix it.
        not in corpus at all      ->  the CEILING. No phase can fix it,
                                      because there is nothing to find (R1.4).

    Those need opposite responses, and telling them apart by eye across twenty
    questions is exactly the sort of thing that gets guessed at instead.
    """
    global _CORPUS_CHUNKS
    if _CORPUS_CHUNKS is None:
        from rag import embed

        _CORPUS_CHUNKS = [
            json.loads(line) for line in embed.CHUNKS_PATH.read_text().splitlines()
        ]
    return sum(1 for c in _CORPUS_CHUNKS if _contains(c["text"], symbol))


def signals(question: str, symbol: str | None, hits, answer: str) -> dict:
    """Mechanical only. Nothing here is an opinion about correctness."""
    texts = [h.payload["text"] for h in hits]
    versions = {h.payload["sqlalchemy_version"] for h in hits}
    citations = {n for n in range(1, len(hits) + 1) if f"[{n}]" in answer}
    missing = bool(symbol) and not any(_contains(t, symbol) for t in texts)
    in_corpus = corpus_chunk_count(symbol) if symbol else None

    return {
        "refused": answer.strip().startswith("The sources do not answer"),
        "uncited": not citations and len(answer.split()) > 15,
        "duplicate_slots": len(texts) - len(set(texts)),
        "version_mixed": len(versions) > 1,
        "symbol_missing": missing,
        "symbol_chunks_in_corpus": in_corpus,
        # The two that matter, and they are mutually exclusive:
        "retrieval_failure": bool(missing and in_corpus),
        "ceiling": bool(symbol and in_corpus == 0),
        "single_source": len(citations) == 1 and len(hits) > 1,
        "cited": sorted(citations),
        "versions": sorted(versions),
        "top_score": round(hits[0].score, 3) if hits else None,
    }


def run(only: str | None = None, k: int = ask.DEFAULT_K) -> list[dict]:
    rows = []
    questions = [q for q in QUESTIONS if only is None or q[1] == only]
    for n, (question, category, symbol) in enumerate(questions, 1):
        print(f"[{n}/{len(questions)}] {category:9} {question[:62]}", file=sys.stderr)
        hits = index.retrieve(question, limit=k)
        started = time.perf_counter()
        answer, timings = ask.generate(ask.build_prompt(question, hits))
        rows.append({
            "question": question,
            "category": category,
            "symbol": symbol,
            "answer": answer,
            "seconds": round(time.perf_counter() - started, 1),
            "tokens_per_second": timings["tokens_per_second"],
            "signals": signals(question, symbol, hits, answer),
            "hits": [
                {
                    "n": i,
                    "score": round(h.score, 3),
                    "version": h.payload["sqlalchemy_version"],
                    "source": h.payload["source_path"],
                    "heading": " > ".join(h.payload["heading_path"]) or "(none)",
                    "text": h.payload["text"],
                }
                for i, h in enumerate(hits, 1)
            ],
        })
    return rows


def summarise(rows: list[dict]) -> dict:
    keys = ("refused", "uncited", "version_mixed", "symbol_missing", "single_source",
            "retrieval_failure", "ceiling")
    out = {k: sum(1 for r in rows if r["signals"][k]) for k in keys}
    out["any_duplicate_slot"] = sum(1 for r in rows if r["signals"]["duplicate_slots"])
    out["total_duplicate_slots"] = sum(r["signals"]["duplicate_slots"] for r in rows)
    out["questions"] = len(rows)
    return out


def write_report(rows: list[dict]) -> None:
    s = summarise(rows)
    lines: list[str] = []
    add = lines.append

    add("# Phase 1 failures — where the deliberately dumb RAG breaks")
    add("")
    add("**Generated by `rag/probe.py`.** Answers are the model's; verdicts are a "
        "human's, recorded in `verdicts.json` and rendered here.")
    add("")
    add("This file is the Phase 1 deliverable and the argument for everything in Phase 3. It is")
    add("generated, but it is *not finished* — the script records mechanical signals and never")
    add("decides whether an answer is correct. That judgement is a human's, per")
    add("[`../study/09-DECISIONS.md`](../study/09-DECISIONS.md) **D06**: a golden set graded by the")
    add("same family of model that produced the answers measures self-consistency, not truth.")
    add("")
    add("**To use this file:** read each answer against its sources and mark the verdict line")
    add("`CORRECT`, `WRONG`, or `PARTIAL`, adding one sentence saying why. The signals tell you")
    add("where to look; they are not verdicts.")
    add("")
    add("## How to decide correct, and how to decide complete")
    add("")
    add("These are two different questions and only the first is obvious. **Do not judge by")
    add("reading** — 14 of these questions have a fix in `BREAKAGES.md` that was *run* against")
    add("real 2.0.51, so the answer can be executed rather than assessed.")
    add("")
    add("**The test, for any answer that proposes code or names a replacement:**")
    add("")
    add("1. **Write the code the answer describes, literally** — only what it says, not what you")
    add("   know it meant.")
    add("2. **Run it** on the pinned version:")
    add("   `uv run --no-project --with 'sqlalchemy==2.0.51' python -c \"...\"`")
    add("3. **Compare against the verified fix** — not just \"did it error\", but *what SQL did it")
    add("   emit* and *did it do the same thing*.")
    add("")
    add("| outcome | verdict | why |")
    add("|---|---|---|")
    add("| names the wrong construct, or the code will not run | `WRONG` | it fails immediately |")
    add("| runs, and behaves like the verified fix | `CORRECT` | a developer following it lands right |")
    add("| **runs, but behaves differently** | **`PARTIAL`** | **the dangerous one — see below** |")
    add("")
    add("**`PARTIAL` is a measured outcome, not a hedge.** It is what you record when the answer")
    add("is true, correctly sourced, and still leaves a developer with a silent bug — working")
    add("code that does the wrong thing, with no error to notice.")
    add("")
    add("*Worked example, question 1.* The answer names `aliased` as the replacement for")
    add("`Query.from_self()`, which is right, and cites the exact migration section, which is")
    add("also right. **What it leaves out is that `aliased()` takes a second argument, and the")
    add("second argument is the whole point.**")
    add("")
    add("```python")
    add("# what the answer says")
    add("inner = aliased(Issue)              # ONE argument -> aliases the TABLE")
    add("")
    add("# the verified fix")
    add("subq  = select(Issue).subquery()    # build an inner SELECT")
    add("inner = aliased(Issue, subq)        # TWO arguments -> aliases the SUBQUERY")
    add("```")
    add("")
    add("`aliased(Issue)` says *\"call the issues table something else\"*. `aliased(Issue, subq)`")
    add("says *\"treat the rows coming out of this subquery as Issue objects\"*. Only the second is")
    add("what `from_self()` did, and the answer carries it only inside the borrowed phrase *\"in")
    add("terms of any arbitrary selectable\"*.")
    add("")
    add("**It is not cosmetic — the results differ**, measured on 2.0.51. Take the first three")
    add("issues, then keep only those titled `a` or `e`:")
    add("")
    add("```")
    add("aliased(Issue, subq)  ->  ['a']         # limit 3 (a,b,c), THEN filter")
    add("aliased(Issue)        ->  ['a', 'e']    # filter, then limit 3")
    add("```")
    add("")
    add("`e` was never in the first three. Without the subquery the outer filter moves inside,")
    add("so the query stops meaning what it meant. **Nothing raises. The row count just differs**")
    add("— which is why this is `PARTIAL` rather than `WRONG`, and why `PARTIAL` is the verdict")
    add("worth being precise about.")
    add("")
    add("**Two kinds of answer this test does not reach**, and they are judged differently:")
    add("")
    add("- **`absent` questions** — there is no code to run. The answer is `CORRECT` when the")
    add("  model **declined**, and `WRONG` when it produced something confident instead.")
    add("- **Answers proposing no code** (\"what are the steps to migrate\") — judge whether every")
    add("  claim is supported by a cited source, and whether a reader following it would be")
    add("  misled. `single_source` is worth weighing here.")
    add("")
    add("**`tools/review_sheet.py` renders all of this per entry** — the answer, the sources, and")
    add("the verified fix side by side — so most verdicts become a comparison rather than a")
    add("recall test.")
    add("")
    add("## What the signals mean")
    add("")
    add("| signal | means | is it a failure? |")
    add("|---|---|---|")
    add("| `refused` | the model declined to answer | **correct** for `absent` questions, a failure elsewhere |")
    add("| `uncited` | a substantial answer with no `[n]` citation | usually a failure — the claim is unverifiable |")
    add("| `duplicate_slots` | the same text held more than one top-k slot (D38) | wasted context, not automatically wrong |")
    add("| `version_mixed` | top-k holds both 1.4 and 2.0 passages | usually fine, occasionally the whole problem |")
    add("| `symbol_missing` | no retrieved chunk contains the exact symbol asked about | see the two below — the reason decides the fix |")
    add("| **`retrieval_failure`** | the symbol IS in the corpus and search did not find it | **yes — and Phase 3 can fix it** |")
    add("| **`ceiling`** | the symbol is in **no** chunk at all | **yes — and no phase can fix it.** Only the corpus decision can (R1.4) |")
    add("| `single_source` | every citation points at one source | the answer does not survive that source being wrong |")
    add("")
    add("## Summary")
    add("")
    add(f"- **{s['questions']} questions** across {len(CATEGORIES)} categories")
    add(f"- `refused`: **{s['refused']}**")
    add(f"- `uncited`: **{s['uncited']}**")
    add(f"- `symbol_missing`: **{s['symbol_missing']}**")
    add(f"- `version_mixed`: **{s['version_mixed']}**")
    add(f"- `single_source`: **{s['single_source']}**")
    add(f"- questions with at least one duplicate slot: **{s['any_duplicate_slot']}** "
        f"({s['total_duplicate_slots']} slots wasted in total)")
    add("")
    add("**The split that decides what Phase 3 is worth:**")
    add("")
    add(f"- `retrieval_failure` — the answer was in the corpus and search missed it: **{s['retrieval_failure']}**")
    add(f"- `ceiling` — the answer is in no chunk at all: **{s['ceiling']}**")
    add("")
    add("The first number is the one hybrid search and reranking are aimed at. The second is a")
    add("corpus decision wearing a retrieval costume, and no amount of Phase 3 work touches it.")
    add("")
    add("## Categories")
    add("")
    for name, why in CATEGORIES.items():
        add(f"- **`{name}`** — {why}")
    add("")
    add("---")
    add("")

    for n, row in enumerate(rows, 1):
        sig = row["signals"]
        flags = [k for k in ("refused", "uncited", "retrieval_failure", "ceiling",
                             "single_source") if sig[k]] + \
                (["duplicate_slots"] if sig["duplicate_slots"] else [])
        add(f"## {n}. {row['question']}")
        add("")
        corpus_note = (
            f" · symbol `{row['symbol']}` appears in **{sig['symbol_chunks_in_corpus']}** "
            f"corpus chunks" if row["symbol"] else "")
        add(f"`{row['category']}` · top score **{sig['top_score']}** · "
            f"versions retrieved {', '.join(sig['versions'])} · "
            f"cited {sig['cited'] or 'nothing'} · {row['seconds']}s{corpus_note}")
        add("")
        add(f"**Signals:** {', '.join(f'`{f}`' for f in flags) if flags else '_none_'}")
        add("")
        # Verdicts are human judgement and the one thing here a script cannot
        # reproduce, so they are read back from deliverables/verdicts.json rather
        # than reset. Regenerating this file used to destroy them silently.
        v = VERDICTS.get(str(n))
        if v:
            add(f"**Verdict:** `{v[0]}` — {v[1]}")
        else:
            add("**Verdict:** `UNVERIFIED` — <!-- CORRECT / WRONG / PARTIAL, and one sentence why -->")
        add("")
        add("### Answer")
        add("")
        add("```")
        add(row["answer"])
        add("```")
        add("")
        add("### What was retrieved")
        add("")
        for hit in row["hits"]:
            add(f"**[{hit['n']}]** `{hit['score']}` · SQLAlchemy **{hit['version']}** · "
                f"`{hit['source']}`  ")
            add(f"{hit['heading']}")
            add("")
            add("```rst")
            body = hit["text"]
            add(body if len(body) <= 700 else body[:700] + "\n… (truncated for this report)")
            add("```")
            add("")
        add("---")
        add("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines))


def main() -> None:
    argv = sys.argv[1:]
    if "--list" in argv:
        for question, category, symbol in QUESTIONS:
            print(f"{category:9} {symbol or '-':18} {question}")
        print(f"\n{len(QUESTIONS)} questions, {len(CATEGORIES)} categories")
        return

    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    k = int(argv[argv.index("--k") + 1]) if "--k" in argv else ask.DEFAULT_K
    rows = run(only, k=k)

    # A non-default k is an experiment, not a new deliverable. Overwriting
    # FAILURES.md with it would replace 19 human verdicts with answers nobody
    # judged, so it prints and stops.
    if k != ask.DEFAULT_K:
        s = summarise(rows)
        print(f"\nk={k} (default {ask.DEFAULT_K}) — report NOT written")
        print(json.dumps(s, indent=2))
        return

    write_report(rows)
    s = summarise(rows)
    print(f"\nwrote {REPORT_PATH.relative_to(corpus.REPO_ROOT)}")
    print(json.dumps(s, indent=2))
    print("\nVerdicts render from deliverables/verdicts.json (tools.apply_verdicts).")


if __name__ == "__main__":
    main()
