"""
Phase 1, Step 5 — run questions with known answers and record where it fails.

    uv run python -m rag.probe                  # run everything, write the report
    uv run python -m rag.probe --only skew      # one category
    uv run python -m rag.probe --list           # the question set, no model calls

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
    return sum(1 for c in _CORPUS_CHUNKS if symbol.lower() in c["text"].lower())


def signals(question: str, symbol: str | None, hits, answer: str) -> dict:
    """Mechanical only. Nothing here is an opinion about correctness."""
    texts = [h.payload["text"] for h in hits]
    versions = {h.payload["sqlalchemy_version"] for h in hits}
    citations = {n for n in range(1, len(hits) + 1) if f"[{n}]" in answer}
    missing = bool(symbol) and not any(symbol.lower() in t.lower() for t in texts)
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


def run(only: str | None = None) -> list[dict]:
    rows = []
    questions = [q for q in QUESTIONS if only is None or q[1] == only]
    for n, (question, category, symbol) in enumerate(questions, 1):
        print(f"[{n}/{len(questions)}] {category:9} {question[:62]}", file=sys.stderr)
        hits = index.retrieve(question, limit=ask.DEFAULT_K)
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
    add("**Generated by `rag/probe.py`. Every answer below is UNVERIFIED.**")
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
    rows = run(only)
    write_report(rows)

    s = summarise(rows)
    print(f"\nwrote {REPORT_PATH.relative_to(corpus.REPO_ROOT)}")
    print(json.dumps(s, indent=2))
    print("\nEvery answer is marked UNVERIFIED. Read them and set the verdicts.")


if __name__ == "__main__":
    main()
