"""
Re-run D43 — is the refusal clause necessary, and does the strict wording over-fire?

    uv run python -m rag.compare_prompts              # all three prompts, both questions
    uv run python -m rag.compare_prompts --prompt C   # just one variant
    uv run python -m rag.compare_prompts --all        # all 19 probe questions, counts only

`study/09-DECISIONS.md` **D43** recorded a three-by-two table on 2026-08-15 and
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

One the corpus can answer, one it provably cannot (the API-reference hole, D07).
A single question cannot show the failure modes pull in opposite directions:
A fails only on the answerable one, C only on the unanswerable one.

WHAT THIS DOES NOT MEASURE

**A rate.** n=1 per cell. It identifies mechanisms, not frequencies, and the
2026-08-16 re-run proved a single observation here can fail to reproduce. It
also writes no verdicts: D06 and D46 reserve those for a person, so this prints
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

# A is quoted verbatim from D43. B is imported rather than retyped, so this
# script cannot drift from what actually ships.
REFUSAL_CLAUSES = {
    "A": "If the sources do not contain the answer, say exactly: "
         "\"The sources do not answer this.\" ",
    "B": None,  # sentinel: use ask.SYSTEM unchanged
    "C": "",
}

LABELS = {
    "A": "strict canned refusal",
    "B": "refusal as last resort (SHIPPED)",
    "C": "no refusal clause",
}

# (kind, question). The unanswerable one is probe.py's `absent` category.
QUESTIONS = [
    ("ANSWERABLE  ", "why can't I call engine.execute() any more?"),
    ("UNANSWERABLE", "what is the exact signature and full argument list of Session.execute?"),
]


def system_prompt(variant: str) -> str:
    """B is the shipped string itself; A and C rebuild it around a different clause."""
    clause = REFUSAL_CLAUSES[variant]
    return ask.SYSTEM if clause is None else _HEAD + clause + _TAIL


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
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())["message"]["content"].strip()
    except urllib.error.URLError as exc:
        sys.exit(
            f"cannot reach Ollama at {ask.OLLAMA_URL}: {exc}\n"
            f"  start it, and check `ollama list` has {ask.MODEL}"
        )


def refused(answer: str) -> bool:
    """
    The canned sentence is the refusal signal, matched on its stable prefix.

    Deliberately mechanical and deliberately not a verdict: a refusal is the
    CORRECT output for the unanswerable question and a failure for the other,
    so this reports which cell it landed in and lets a reader judge (D46).
    """
    return answer.lower().startswith("the sources do not answer this")


def sweep_all(variants: list[str]) -> None:
    """
    Every probe question against each wording, counting refusals.

    D43 chose prompt B on two questions. Round 7 then found B refusing 8 of 19
    with the answer demonstrably in the prompt (D51), which the original
    experiment could not have seen. This is the same test at the size that
    would have caught it: refusals per variant, over the whole set.

    Counts only — no answers printed, because 57 answers is not readable and
    the question here is a rate, not a reading.
    """
    tally = {v: {"refused": 0, "answered": 0} for v in variants}
    per_q: list[tuple[str, str, dict[str, str]]] = []
    for question, category, _sym in probe.QUESTIONS:
        hits = index.retrieve(question, limit=ask.DEFAULT_K)
        prompt = ask.build_prompt(question, hits)
        row = {}
        for v in variants:
            answer = generate(system_prompt(v), prompt)
            r = refused(answer)
            tally[v]["refused" if r else "answered"] += 1
            row[v] = "refused" if r else "answered"
        per_q.append((question, category, row))
        print(f"  {category:9} {' '.join(f'{v}={row[v][:3]}' for v in variants)}  {question[:46]}")

    print()
    print(f"{'prompt':<8} {'refused':>8} {'answered':>9}   of {len(probe.QUESTIONS)}")
    for v in variants:
        t = tally[v]
        print(f"{v:<8} {t['refused']:>8} {t['answered']:>9}   {LABELS[v]}")
    print()
    print("A refusal is CORRECT for the 3 `absent` questions and a failure elsewhere,")
    print("so the floor is 3 — a variant refusing 3 is not under-refusing, it is right.")


def main() -> None:
    argv = sys.argv[1:]
    only = argv[argv.index("--prompt") + 1].upper() if "--prompt" in argv else None
    if only and only not in REFUSAL_CLAUSES:
        sys.exit(f"unknown prompt {only!r}; choose from {', '.join(REFUSAL_CLAUSES)}")
    variants = [only] if only else list(REFUSAL_CLAUSES)

    if "--all" in argv:
        sweep_all(variants)
        return

    grid: dict[tuple[str, str], bool] = {}

    for kind, question in QUESTIONS:
        hits = index.retrieve(question, limit=ask.DEFAULT_K)
        prompt = ask.build_prompt(question, hits)
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
        print("so a cell disagreeing with D43's table is a finding to record, not an error.")


if __name__ == "__main__":
    main()
