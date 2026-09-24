"""
Re-run the refusal-clause experiment: is the refusal clause necessary, and does the strict wording over-fire?

    uv run python -m rag.compare_prompts              # all three prompts, both questions
    uv run python -m rag.compare_prompts --prompt C   # just one variant
    uv run python -m rag.compare_prompts --all        # all 19 probe questions, counts only
    uv run python -m rag.compare_prompts --all --k 10 # the same at a different top-k
    uv run python -m rag.compare_prompts --all --repeat 5  # n=5 per cell, not n=1

    # Phase 4 (2026-08-22): the 100-item golden set, scored on BOTH defects
    uv run python -m rag.compare_prompts --golden --save runs.json

The refusal-clause decision recorded a three-by-two table on 2026-08-15 and
shipped prompt B off it. It existed only as a table: the experiment was run by
hand, and nothing in the repo could reproduce it. A re-run on 2026-08-16 then
disagreed with one cell, which is exactly the situation an unreproducible
measurement makes impossible to investigate. Hence this file.

WHAT IS VARIED, AND WHAT IS HELD STILL

**One sentence** of the system prompt. The sources, the question, the model and
the temperature are identical across the three runs — otherwise the comparison
measures whatever else moved.

    A   "If the sources do not contain the answer, say exactly: ..."
        Refusing is the default exit. "Do not contain the answer" is a high bar.
    B   "Prefer answering from what the sources do say ... only if genuinely
        silent."  Answering is the default; refusing is the escape hatch. SHIPPED.
    C   the sentence is absent. The model has no permission to refuse, so it
        must always produce something.

THE TWO QUESTIONS, AND WHY EXACTLY TWO

One the corpus can answer, one it provably cannot (the API reference is not in the docs source the corpus is built from).
A single question cannot show the failure modes pull in opposite directions:
A fails only on the answerable one, C only on the unanswerable one.

WHAT THIS DOES NOT MEASURE

**A rate.** n=1 per cell. It identifies mechanisms, not frequencies, and the
2026-08-16 re-run proved a single observation here can fail to reproduce. It
also writes no verdicts: verdicts are reserved for a person, so this prints
the answers and stops. Reading them is the job it does not do.

Generation is nondeterministic, so two runs of this script may disagree. That
is a property of the thing being measured, not a bug in the measurement — which
is why the output labels itself with the date and says so.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from rag import ask, index, probe

# Shared by all three variants, so the only difference is the refusal sentence.
_HEAD = (
    "You answer questions about migrating Python code from SQLAlchemy 1.4 to 2.0. "
    "You are given numbered sources from the SQLAlchemy documentation. "
    "Base your answer on those sources and cite the source number in brackets, like [2]. "
)
_TAIL = (
    "Each source is labelled with the SQLAlchemy version it documents — if versions "
    "disagree, say so rather than picking one silently."
)

# A is quoted verbatim from the original refusal-clause experiment. B is imported rather than retyped, so this
# script cannot drift from what actually ships.
REFUSAL_CLAUSES = {
    "A": "If the sources do not contain the answer, say exactly: "
         "\"The sources do not answer this.\" ",
    # B was shipped until 2026-08-17; kept literal so the comparison survives
    # D becoming the default. The sentinel moved to D.
    "B": "Prefer answering from what the sources do say, even if they address the question "
         "indirectly. Only if the sources are genuinely silent on the topic, reply: "
         "\"The sources do not answer this.\" ",
    "C": "",
    # D is not a tuning of B. A and B both ask the model to judge SUFFICIENCY —
    # "do these sources contain the answer?" — a binary gate it applies strictly
    # the moment a question names a specific symbol (both refused the same
    # 8, including 4 where the answer was present). D removes that judgement:
    # partial answers become the expected output, and refusal is narrowed to
    # "no source is about the subject at all" plus an obligation to name what
    # was looked for. Naming it forces a check rather than a pattern match.
    "D": None,  # sentinel: use ask.SYSTEM — D is what ships as of 2026-08-17
}

# --- Phase 4 variants (2026-08-22) -------------------------------------------
#
# A-D vary exactly one sentence and nothing else; a test pins that invariant.
# These vary the CITATION instruction and add a relevance premise, so they
# cannot live in REFUSAL_CLAUSES without breaking what that dict means. They are
# built here as whole system prompts instead, from D's text, so the diff against
# what ships is readable in one place.
#
# They exist to attack two MEASURED defects, not to tune wording:
#
#   Over-refusal:  19 of the 58 items whose answer reached the prompt were refused anyway
#        -- 33% of retrieval's ceiling, thrown away by generation.
#   No citations:  31 of the 48 answered items cite NOTHING, and 26 of the 28 answers
#        containing code show executable code with no source attached.
#
# The risk in E is real and is the reason it is measured rather than shipped:
# "do not say it if you cannot cite it" is a refusal pressure, and an earlier wording change
# already fixed one cell by breaking another.

# D's citation sentence, quoted so the diff is visible.
_CITE_D = ("Base your answer on those sources and cite the source number in "
           "brackets, like [2]. ")

# E: citation becomes an obligation with a named consequence, and code is
# called out because that is where the defect concentrates (26 of 28).
_CITE_E = (
    "Base your answer on those sources. Every factual sentence must end with the "
    "bracketed number of the source it came from, like [2]. Every code block must "
    "have the source number it is based on on the line immediately before it. "
    "An answer with no bracketed number in it is not acceptable. "
)

# F: the over-refusal premise. D already narrows refusal to subject; the 19
# failures are the model still demanding a source that states the answer
# verbatim. This tells it what the sources ARE -- search results for this
# question -- and what counts as enough.
_RELEVANCE_F = (
    "These sources were selected by a search engine as the closest matches for "
    "this question, so assume they are on topic. A source that shows the relevant "
    "API, pattern, or error is enough to answer from, even if no sentence in it "
    "states the answer directly. "
)


def _phase4(cite: str, relevance: str) -> str:
    """Rebuild D's system prompt with a different citation clause and/or premise.

    D's own refusal sentences are quoted from ask.SYSTEM rather than retyped, so
    if the shipped prompt changes these variants change with it instead of
    silently comparing against a prompt nobody runs.
    """
    body = ask.SYSTEM.replace(_CITE_D, cite)
    if body == ask.SYSTEM and cite != _CITE_D:  # pragma: no cover - guard
        raise AssertionError(
            "ask.SYSTEM no longer contains D's citation sentence; _CITE_D is stale")
    return body.replace("Answer with whatever", relevance + "Answer with whatever")


# H and I change WHERE the instruction sits, not how loudly it is worded.
#
# The smoke run on 2026-08-22 is why they exist: E states "an answer with no
# bracketed number in it is not acceptable" in the system message, and on g002
# the model produced an answer byte-comparable to D's, with zero citations. A
# 7B model is not refusing to comply so much as not attending -- the system
# message is thousands of tokens away from where the answer starts, behind five
# full documentation chunks.
#
# So these put the requirement in the USER message, on the last line before
# "ANSWER:", which is the text nearest the generation point. Same mechanism
# change that made D beat B: a different lever, not a louder one.
_REMINDER_H = (
    "Before answering: cite the source number in brackets, like [2], after each "
    "statement you take from a source, and put the source number on the line "
    "before any code block."
)

PHASE4_VARIANTS = {
    "E": lambda: _phase4(_CITE_E, ""),
    "F": lambda: _phase4(_CITE_D, _RELEVANCE_F),
    "G": lambda: _phase4(_CITE_E, _RELEVANCE_F),
    "H": lambda: ask.SYSTEM,          # D's system prompt; the change is in the user turn
    "I": lambda: _phase4(_CITE_D, _RELEVANCE_F),   # F's system prompt + H's reminder
}

# What each variant appends to the user message, just before "ANSWER:".
USER_SUFFIX = {"H": _REMINDER_H, "I": _REMINDER_H}


def user_prompt(variant: str, prompt: str) -> str:
    """Insert a variant's reminder immediately before the ANSWER: cue.

    build_prompt ends with "\n\nANSWER:"; anything appended after that would
    land after the cue and read as the start of the answer.

    Since prompt H shipped (2026-09-20) the sentence SHIPS, so every arm in this module builds from
    `build_prompt(..., reminder="")` — the prompt from before H shipped — and `H` puts it
    back here. Without that the control silently becomes the new prompt and the
    whole comparison measures nothing (one ruler, not two).
    """
    suffix = USER_SUFFIX.get(variant)
    if not suffix:
        return prompt
    assert prompt.endswith("ANSWER:"), "build_prompt no longer ends with the ANSWER cue"
    return prompt[: -len("ANSWER:")] + suffix + "\n\nANSWER:"

LABELS = {
    "A": "strict canned refusal",
    "B": "refusal as last resort (was shipped to 2026-08-17)",
    "C": "no refusal clause",
    "D": "answer partially, refuse only on subject (SHIPPED)",
    "E": "D + citation is mandatory, code blocks named (attacks the missing citations)",
    "F": "D + sources are search results, relevance assumed (attacks the over-refusals)",
    "G": "E + F together",
    "H": "D + the citation rule moved into the USER turn, next to ANSWER:",
    "I": "F's relevance premise + H's user-turn reminder",
}

# (kind, question). The unanswerable one is probe.py's `absent` category.
QUESTIONS = [
    ("ANSWERABLE  ", "why can't I call engine.execute() any more?"),
    ("UNANSWERABLE", "what is the exact signature and full argument list of Session.execute?"),
]


def system_prompt(variant: str) -> str:
    """The shipped variant IS ask.SYSTEM; the others rebuild it around a different clause."""
    if variant in PHASE4_VARIANTS:
        return PHASE4_VARIANTS[variant]()
    clause = REFUSAL_CLAUSES[variant]
    return ask.SYSTEM if clause is None else _HEAD + clause + _TAIL


ALL_VARIANTS = list(REFUSAL_CLAUSES) + list(PHASE4_VARIANTS)


def generate(system: str, prompt: str) -> str:
    """One Ollama call with an overridden system message. Mirrors ask.generate()."""
    body = json.dumps({
        "model": ask.MODEL,
        "stream": False,
        "options": {"temperature": ask.TEMPERATURE},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    request = urllib.request.Request(
        f"{ask.OLLAMA_URL}/api/chat", data=body,
        headers={"Content-Type": "application/json"},
    )
    # Two attempts, the second with a longer ceiling.
    #
    # A single slow generation used to abort the whole sweep: urllib raises
    # socket.timeout, which is a TimeoutError/OSError and NOT a URLError, so it
    # sailed past the handler below and killed a 100-item run at item 150 of
    # 300 (2026-08-22). The cost of one retry is seconds; the cost of not
    # retrying was ~50 minutes of generations.
    last = None
    for attempt, limit in enumerate((300, 900)):
        try:
            with urllib.request.urlopen(request, timeout=limit) as response:
                return json.loads(response.read())["message"]["content"].strip()
        except urllib.error.URLError as exc:
            sys.exit(
                f"cannot reach Ollama at {ask.OLLAMA_URL}: {exc}\n"
                f"  start it, and check `ollama list` has {ask.MODEL}"
            )
        except (TimeoutError, OSError) as exc:
            last = exc
            print(f"    generation timed out at {limit}s"
                  f"{'; retrying once' if attempt == 0 else ''}", flush=True)
    raise TimeoutError(f"generation failed twice: {last}")


def refused(answer: str) -> bool:
    """
    The canned sentence is the refusal signal — `ask.refused`, not a copy of it.

    Deliberately mechanical and deliberately not a verdict: a refusal is the
    CORRECT output for the unanswerable question and a failure for the other,
    so this reports which cell it landed in and lets a reader judge.

    **This used to be a second implementation** — `answer.lower().startswith(...)`
    — which differed from `ask.refused` in two ways: it lowercased, and it did
    not strip, so a single leading space made it miss a refusal that ask.py
    caught. Two detectors for one concept is how probe.py once silenced the very
    signal it existed for.

    Unified 2026-08-22, on evidence rather than principle: across the 100 real
    answers saved by the first golden sweep, the two implementations disagreed
    on **zero**, no answer had leading whitespace, and no refusal came back in
    non-canonical case. The divergence was latent, so removing it changes no
    recorded number — which is the only safe moment to remove it.
    """
    return ask.refused(answer)


def sweep_all(variants: list[str], k: int = ask.DEFAULT_K, repeat: int = 1) -> None:
    """
    Every probe question against each wording, counting refusals.

    The original experiment chose prompt B on two questions. Round 7 then found B refusing 8 of 19
    with the answer demonstrably in the prompt, which the original
    experiment could not have seen. This is the same test at the size that
    would have caught it: refusals per variant, over the whole set.

    Counts only — no answers printed, because 57 answers is not readable and
    the question here is a rate, not a reading.
    """
    # counts[variant][question_index] = how many of `repeat` runs refused.
    # n=1 per cell is what prompt B shipped on, and why A and B later turned out identical; --repeat is
    # the fix, and aggregating here means one sitting settles it rather than
    # five round-trips through this file.
    counts = {v: [0] * len(probe.QUESTIONS) for v in variants}
    for r in range(repeat):
        for qi, (question, _cat, _sym) in enumerate(probe.QUESTIONS):
            hits = index.retrieve(question, limit=k)
            prompt = ask.build_prompt(question, hits, reminder="")
            for v in variants:
                if refused(generate(system_prompt(v), prompt)):
                    counts[v][qi] += 1
        print(f"  run {r + 1}/{repeat} done", flush=True)

    print()
    if repeat > 1:
        print(f"per-question refusals out of {repeat} runs "
              f"({' '.join(variants)} — * = not unanimous)")
        for qi, (question, category, _s) in enumerate(probe.QUESTIONS):
            cells = " ".join(f"{v}={counts[v][qi]}" for v in variants)
            unstable = any(0 < counts[v][qi] < repeat for v in variants)
            print(f"  {qi+1:2d} {category:9} {cells} {'*' if unstable else ' '} {question[:42]}")
        print()

    tally = {v: {"refused": sum(counts[v]) / repeat,
                 "answered": len(probe.QUESTIONS) - sum(counts[v]) / repeat} for v in variants}
    per_q = []
    print()
    print(f"{'prompt':<8} {'refused':>8} {'answered':>9}   of {len(probe.QUESTIONS)}")
    for v in variants:
        t = tally[v]
        print(f"{v:<8} {t['refused']:>8.1f} {t['answered']:>9.1f}   {LABELS[v]}")
    print()
    print("A refusal is CORRECT for the 3 `absent` questions and a failure elsewhere,")
    print("so the floor is 3 — a variant refusing 3 is not under-refusing, it is right.")


def golden_sweep(variants: list[str], k: int = ask.DEFAULT_K,
                 limit: int | None = None, save: str | None = None) -> None:
    """Every golden item against each wording, scored on BOTH Phase 4 defects.

    Three things about the design, each of which is a decision:

    **Retrieval runs once, not once per variant.** The prompt cannot change what
    search returns, so re-retrieving would burn minutes to reproduce identical
    hits -- and worse, would let a reranker or index change mid-sweep and be
    read as a prompt effect.

    **One generation per (item, variant), two metrics off it.** Refusal and
    citation are both properties of the same answer. Generating twice would
    double a ~35-minute pass and, because generation is not perfectly
    reproducible across calls, would let the two metrics describe different
    answers.

    **Every variant runs in this sitting, including D.** Refusal behaviour was shown to drift on
    2026-08-21, when two items flipped between days with the prompt, temperature
    and index all unchanged. Comparing a new wording against yesterday's numbers
    would put that drift inside the measurement. D is re-run here as the control
    even though its numbers are already published (end to end 0.43, 65% uncited).

    It writes no verdicts. It prints cells and names ids; which wording ships is
    a decision, and the last time that was assumed rather than asked it was the
    wrong call (2026-08-17, prompt D).
    """
    from rag import judge, score

    items = [i for i in score.load_golden() if i.get("verified_by") == "human"]
    if limit:
        items = items[:limit]
    chunks = score.load_chunks()

    print(f"golden sweep — {len(items)} items x {len(variants)} variants, k={k}")
    print(f"variants: {', '.join(variants)}\n", flush=True)

    prepared = []
    for it in items:
        hits = index.retrieve(it["question"], limit=k)
        prepared.append({
            "item": it,
            "prompt": ask.build_prompt(it["question"], hits, reminder=""),
            "n_sources": len(hits),
            # Same definition score.py --refusals uses, so the columns below are
            # comparable with the table rather than merely similar to it.
            "answer_in_prompt": (
                score.rank_of_first_hit([h.payload["chunk_id"] for h in hits], it, chunks)
                is not None if it.get("answerable") else False),
        })
    print(f"retrieved {len(prepared)} items once; generating\n", flush=True)

    import pathlib as _pathlib

    def checkpoint(partial: dict) -> None:
        """Write what exists so far. A sweep is ~300 generations and hours long;
        losing all of it to one bad call has now happened twice in this repo."""
        if save:
            _pathlib.Path(save).write_text(json.dumps(partial, indent=1) + "\n")

    results: dict[str, list[dict]] = {}
    for v in variants:
        system = system_prompt(v)
        rows = []
        for n, p in enumerate(prepared, 1):
            try:
                answer = generate(system, user_prompt(v, p["prompt"]))
            except TimeoutError as exc:
                # Record and continue. One unanswerable-in-time item is a data
                # point; aborting turns it into a lost night.
                print(f"    {v}/{p['item']['id']}: FAILED — {exc}", flush=True)
                rows.append({"id": p["item"]["id"], "failed": True,
                             "answerable": bool(p["item"].get("answerable")),
                             "answer_in_prompt": p["answer_in_prompt"]})
                continue
            row = judge.citation_report(answer, p["n_sources"])
            row.update(
                id=p["item"]["id"],
                provenance=p["item"].get("provenance"),
                answerable=bool(p["item"].get("answerable")),
                answer_in_prompt=p["answer_in_prompt"],
                # ask.refused, via citation_report -- NOT this module's legacy
                # `refused()`, which lowercases and does not strip. The two
                # disagree on a leading space, and the baseline used ask's.
                answer=answer,
            )
            rows.append(row)
            if n % 25 == 0:
                print(f"  {v}: {n}/{len(prepared)}", flush=True)
                checkpoint({**results, v: rows})
        results[v] = rows
        checkpoint(results)
        print(f"  {v}: done ({sum(1 for r in rows if r.get('failed'))} failed)", flush=True)

    _report_golden(results, variants)
    if save:
        import pathlib
        pathlib.Path(save).write_text(json.dumps(results, indent=1) + "\n")
        print(f"\nsaved {sum(map(len, results.values()))} rows to {save}")


def cells(rows: list[dict]) -> dict:
    """One variant's row of the golden-sweep table.

    Module level rather than a closure inside the report so the rules can be
    tested directly -- the same move `chunk.audit()`'s detectors needed, and
    for the same reason: an inline rule is a rule nothing can pin.

    **The citation columns count EVERY answered row, not only the answerable
    ones.** They used to count `ans`, which silently excluded answers
    to `answerable: false` items -- so this table and `judge --report` printed
    a column with the same name and different denominators, D reading
    `18/45 = 40%` here and `20/47 = 43%` there. The excluded rows are the
    fabrications, which are the answers least worth trusting, and a user has no
    idea which of their questions was unanswerable. `fabr` still counts them
    separately; that is the column that means "should not have answered".
    """
    # A row that never got a generation is not a refusal and not an answer.
    # Counting it either way would let a flaky night look like a prompt effect.
    # Imported here, not at module level, matching `golden_sweep` below: the
    # citation rules live in `judge` and this module is the one that calls
    # them, never the reverse.
    from rag import judge

    # The DENOMINATOR keeps every answerable item, failed rows included.
    # Dropping them per-arm is how a paired comparison gets two rulers: D has
    # no failures and H has one, so this reported H as 47/90 against a
    # published 47/91 -- `judge._sweep_generation` had already been fixed for
    # exactly this and the two modules disagreed.
    n_answerable = sum(1 for r in rows if r["answerable"])
    rows = [r for r in rows if not r.get("failed")]

    # Refusal is RE-SCORED from the answer text, not read from the stored
    # field, for the reason the citation detector taught: stored fields go
    # stale the moment a detector is fixed. `ask.refused` gained the
    # leading-`[n]` strip after H's cited refusals broke it -- H's saved rows predate it, so reading
    # `r["refused"]` off the 2026-08-23 sweep reports 68 answers where the
    # published figure is 62, silently restoring the bug that fix removed. On a fresh
    # run the two agree; the difference only appears when re-reading, which is
    # exactly when nobody is watching.
    def declined(r):
        return ask.refused(r["answer"]) if r.get("answer") else r.get("refused")

    # The citation fields are re-scored from the answer for the same reason,
    # and this is the same bug rather than an analogy: under H a subscript
    # `row[keys[0]]` had been read as citing sources 0, 1 and 2, which made an
    # UNCITED code block look cited. Rows written before that fix still carry
    # the old values, so reading them replays the bug -- `g016` is the item.
    def scored(r):
        if r.get("answer") is None:
            return r
        return judge.citation_report(r["answer"], r.get("n_sources", 0))

    una = [r for r in rows if not r["answerable"]]
    ans = [r for r in rows if r["answerable"]]
    in_prompt = [r for r in ans if r["answer_in_prompt"]]
    answered = [r for r in rows if not declined(r)]
    return {
        "fabricated": sum(1 for r in una if not declined(r)),
        "n_una": len(una),
        "n_ans": n_answerable,
        "n_judged": len(ans),
        "ceiling": len(in_prompt),
            # The over-refusal defect: the page was there and it declined anyway.
        "over_with": sum(1 for r in in_prompt if declined(r)),
        "end_to_end": sum(1 for r in in_prompt if not declined(r)),
        "answered": len(answered),
        "uncited": sum(1 for r in answered if scored(r)["uncited"]),
        "with_code": sum(1 for r in answered if scored(r)["code_blocks"]),
        "uncited_code": sum(1 for r in answered if scored(r)["uncited_code_blocks"]),
        "out_of_range": sum(1 for r in answered if scored(r)["out_of_range"]),
    }


def _report_golden(results: dict[str, list[dict]], variants: list[str]) -> None:
    t = {v: cells(results[v]) for v in variants}
    n_ans = t[variants[0]]["n_ans"]

    print("\n" + "=" * 78)
    print("GOLDEN SWEEP — both Phase 4 defects, one sitting")
    print("=" * 78)
    print(f"\n{'':<6}{'end/end':>9}{'ceiling':>9}{'over':>7}{'uncited':>9}"
          f"{'code':>7}{'unc.code':>10}{'fabr':>6}")
    for v in variants:
        c = t[v]
        e2e = f"{c['end_to_end']}/{n_ans}"
        unc = f"{c['uncited']}/{c['answered']}" if c["answered"] else "-"
        uc = f"{c['uncited_code']}/{c['with_code']}" if c["with_code"] else "-"
        print(f"{v:<6}{e2e:>9}{c['ceiling']:>9}{c['over_with']:>7}{unc:>9}"
              f"{c['with_code']:>7}{uc:>10}{c['fabricated']:>6}")

    print("\n  end/end   answer in the prompt AND not refused — what a user gets")
    print("  ceiling   answer in the prompt at all — identical across variants by design")
    print("  over      refused WITH the page in hand (the defect)")
    print("  uncited   answered items citing nothing (the defect)")
    print("  unc.code  answers whose code carries no source, of those containing code")
    print("  fabr      answered an unanswerable item — the worst cell in the table")

    base = variants[0]
    print(f"\nPAIRED against {base}, item by item: which items flipped, not the averages")
    for v in variants[1:]:
        by_id = {r["id"]: r for r in results[base] if not r.get("failed")}
        # Pairing needs BOTH sides. An item that failed in either run is dropped
        # from the comparison rather than silently counted as a flip.
        cmp_rows = [r for r in results[v] if not r.get("failed") and r["id"] in by_id]
        fixed = [r["id"] for r in cmp_rows
                 if r["answerable"] and r["answer_in_prompt"]
                 and not r["refused"] and by_id[r["id"]]["refused"]]
        broke = [r["id"] for r in cmp_rows
                 if r["answerable"] and r["answer_in_prompt"]
                 and r["refused"] and not by_id[r["id"]]["refused"]]
        newfab = [r["id"] for r in cmp_rows
                  if not r["answerable"] and not r["refused"] and by_id[r["id"]]["refused"]]
        p = score_mcnemar(len(fixed), len(broke))
        print(f"\n  {v}: answers now that {base} refused  {len(fixed):>3}  {', '.join(fixed) or '—'}")
        print(f"     refuses now that {base} answered  {len(broke):>3}  {', '.join(broke) or '—'}")
        print(f"     exact McNemar p = {p:.3f}")
        if newfab:
            print(f"     NEW FABRICATIONS {len(newfab)}: {', '.join(newfab)}  <- disqualifying")


def score_mcnemar(fixed: int, broken: int) -> float:
    from rag import score
    return score.mcnemar_exact(fixed, broken)


def main() -> None:
    argv = sys.argv[1:]
    only = argv[argv.index("--prompt") + 1].upper() if "--prompt" in argv else None
    if only and only not in ALL_VARIANTS:
        sys.exit(f"unknown prompt {only!r}; choose from {', '.join(ALL_VARIANTS)}")
    variants = [only] if only else list(REFUSAL_CLAUSES)

    if "--golden" in argv:
        # D first and always: it is the control, and because refusals drift day to day it must be
        # re-run in the same sitting as anything compared against it.
        vs = ([only] if only else
              [v for v in argv[argv.index("--golden") + 1:]
               if v.upper() in ALL_VARIANTS] or ["D", "E", "F", "H", "I"])
        if "D" not in vs:
            vs = ["D"] + vs
        kk = int(argv[argv.index("--k") + 1]) if "--k" in argv else ask.DEFAULT_K
        lim = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
        sv = argv[argv.index("--save") + 1] if "--save" in argv else None
        golden_sweep(vs, k=kk, limit=lim, save=sv)
        return

    if "--all" in argv:
        kk = int(argv[argv.index("--k") + 1]) if "--k" in argv else ask.DEFAULT_K
        print(f"top-k = {kk}\n")
        rp = int(argv[argv.index("--repeat") + 1]) if "--repeat" in argv else 1
        print(f"repeat = {rp}")
        sweep_all(variants, k=kk, repeat=rp)
        return

    # The two-question refusal-clause run. `k` was undefined here from eeedbc4 until
    # 2026-09-14, so this path crashed on its first retrieve.
    k = int(argv[argv.index("--k") + 1]) if "--k" in argv else ask.DEFAULT_K
    grid: dict[tuple[str, str], bool] = {}

    for kind, question in QUESTIONS:
        hits = index.retrieve(question, limit=k)
        prompt = ask.build_prompt(question, hits, reminder="")
        print("=" * 78)
        print(f"{kind.strip()}: {question}")
        print(f"  top-5 scores: {[round(h.score, 3) for h in hits]}")
        print("=" * 78)
        for v in variants:
            answer = generate(system_prompt(v), prompt)
            grid[(v, kind)] = refused(answer)
            print(f"\n--- prompt {v}  {LABELS[v]} ---")
            print(answer)
        print()

    if len(variants) > 1:
        print("=" * 78)
        print("SUMMARY — 'refused' is correct for UNANSWERABLE, a failure for ANSWERABLE")
        print("=" * 78)
        print(f"{'prompt':<8} {'answerable':<14} {'unanswerable':<14}")
        for v in variants:
            cells = []
            for kind, _ in QUESTIONS:
                r = grid[(v, kind)]
                want_refusal = kind.strip() == "UNANSWERABLE"
                cells.append(("refused" if r else "answered") + ("  ok" if r == want_refusal else "  X"))
            print(f"{v:<8} {cells[0]:<14} {cells[1]:<14}")
        print("\nn=1 per cell — a mechanism, never a rate. Generation is nondeterministic,")
        print("so a cell disagreeing with the table is a finding to record, not an error.")


if __name__ == "__main__":
    main()
