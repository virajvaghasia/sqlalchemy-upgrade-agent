"""
Phase 1, Step 4 — ask a question, get an answer and the chunks it came from.

    uv run python -m rag.ask "why can't I call engine.execute any more?"
    uv run python -m rag.ask "..." --k 8              # more sources
    uv run python -m rag.ask "..." --version 2.0.51   # filter by release
    uv run python -m rag.ask "..." --retrieval-only   # skip the model entirely
    uv run python -m rag.ask "..." --show-prompt      # print what the model was sent

Needs Qdrant loaded (`rag/index.py`) and Ollama running with the model below.

SOURCES ARE NOT DECORATION

`phases/PHASE-1.md` says this and it is the entire reason Step 4 prints them.
Without the chunks, there is no way to tell a correct answer from a lucky one —
you are back to trusting a fluent paragraph, which is the problem retrieval
exists to solve. It also makes Step 5 possible at all: a failure is only
diagnosable if you can see *what was retrieved* separately from *what was
said about it*.

So the output is always two parts, and the sources half is never suppressed.

WHAT THE PROMPT DOES, AND WHY EACH LINE IS THERE

Three instructions, each earning its place:

  - **"Use only the sources."** The model has SQLAlchemy in its weights and will
    happily answer from memory — which is exactly the blurred 1.4/2.0 recall
    this project exists to route around (study/10-RETRIEVAL.md §R1.1).
  - **"Cite the source number."** Turns a claim into a checkable one. An answer
    citing [3] can be verified against source 3 in seconds.
  - **"Say you don't know."** A model with no "I have nothing" mechanism invents
    a plausible continuation. Being told the option exists is what makes
    "the corpus cannot answer this" an available output rather than a
    hallucination — and Step 5 specifically looks for questions where this is
    the correct behaviour.

**Each source carries its SQLAlchemy version in the prompt.** That is deliberate
and it is not a Phase 3 fix smuggled in early: retrieval is still unfiltered
(D10), and the version is metadata that honestly belongs with a quoted passage.
What it buys is the chance to observe, in Step 5, whether the model *uses* it —
whether it notices that a 1.4 page is answering a 2.0 question. That is a real
finding either way.

WHAT IS DELIBERATELY NOT DONE

No streaming, no chat history, no retry, no reranking of the retrieved chunks,
no query rewriting. Phase 1 is the naive baseline (D04). Ugly output is fine;
the gate is that a question typed at a terminal returns an answer and its
sources.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

from rag import index

OLLAMA_URL = "http://127.0.0.1:11434"

# Pinned like everything else. `qwen2.5-coder:7b` is what Phase 0 measured on the
# lab PC at 62.23 tok/s, and it is already local on the Mac — using the same tag
# on both machines is what makes those numbers comparable.
MODEL = "qwen2.5-coder:7b"

# How many pages get pasted into the prompt. Search ranks all 3284; the chatbot
# only sees this many. `backref` landed at rank 6 of 3284 — one place below this
# cut — so 6 would have put that page in with no other change (§R4.3). Round 7
# then showed refusals stay 8 at k=5, 6 and 10, and k=10 bought over-fires, so
# D54 kept 5. The integer that fixes the miss is not the one that ships.
DEFAULT_K = 5

# Temperature 0. A retrieval system that answers the same question two different
# ways cannot be evaluated, and Phase 2 has to score these answers. Creativity is
# not a feature here.
TEMPERATURE = 0.0

# The refusal clause is phrased as a LAST RESORT, and the wording is measured
# rather than chosen. Three candidates were run against one answerable question
# and one the corpus provably cannot answer (the API-reference hole, D07).
#
# A is this instruction, not a slogan:
#   If the sources do not contain the answer, say exactly:
#   "The sources do not answer this."
# "Say exactly" hands the model a canned sentence it may emit INSTEAD of
# answering. "Do not contain the answer" is a high bar — pages that explain
# engine.execute without quoting a FAQ still look like a miss, so A refused
# a question whose answer was sitting in the prompt (verified by feeding it
# ONLY those chunks; it still refused).
#
#   prompt                          answerable      unanswerable
#   A canned refusal as the exit    REFUSED  ✗      refused  ✓
#   B refusal as last resort        answered ✓      refused  ✓     <- this one
#   C no refusal clause             answered ✓      ANSWERED ✗
#
# Both failure modes are real and they pull opposite ways. C invented a full
# method signature for Session.execute out of the model's own weights, which
# is precisely the hallucination the clause exists to prevent.
#
# So the clause is NECESSARY (C proves it) and the strict wording OVER-FIRES
# (A proves it). "Prefer answering from what the sources do say... only if
# genuinely silent" is what threads it.
#
# n=1 per cell. Two questions is a diagnosis, not a benchmark — Step 5 is where
# this gets run against a list.
# Prompt D, shipped 2026-08-17 (09-DECISIONS.md D54). It replaced wording B,
# which asked the model to judge SUFFICIENCY — "do these sources contain the
# answer?" — a binary gate it applied strictly whenever a question named a
# symbol. Measured over 19 questions, B and the stricter A refused the SAME 8,
# so D43 had chosen between two identical options (D52).
#
# D changes the mechanism rather than the wording: partial answers are the
# expected output, refusal narrows to SUBJECT rather than sufficiency, and a
# refusal must name what was looked for — which forces a check instead of a
# pattern match, and makes a wrong refusal visible instead of silent.
#
# Measured at DEFAULT_K = 5, all nine of D's refusals are correct (D54). Do not
# raise k to "help": at 10 it buys two over-fires and one fabrication.
SYSTEM = (
    "You answer questions about migrating Python code from SQLAlchemy 1.4 to 2.0. "
    "You are given numbered sources from the SQLAlchemy documentation. "
    "Base your answer on those sources and cite the source number in brackets, like [2]. "
    "Answer with whatever the sources do support, even partially: if they cover part "
    "of the question, give that part and state plainly which part they do not cover. "
    "Reply \"The sources do not answer this.\" only when none of the sources is about "
    "the subject of the question at all, and when you do, name the specific thing you "
    "looked for and did not find. "
    "Each source is labelled with the SQLAlchemy version it documents — if versions "
    "disagree, say so rather than picking one silently."
)


# The exact opening the SYSTEM clause above mandates. It lives HERE, beside the
# sentence that demands it, because a refusal detector that drifts from the
# prompt reports the wrong number in both directions at once: a reworded prompt
# makes every real refusal look like an answer, and nothing fails loudly.
#
# `rag/probe.py` and `rag/score.py --refusals` both call this. Two copies of the
# string was the alternative, and it is how the two would eventually disagree
# about the same run.
REFUSAL_OPENING = "The sources do not answer"


def refused(answer: str) -> bool:
    """Did the model decline, rather than answer badly?

    A prefix test, not a search: the clause tells the model to OPEN with this
    sentence. Matching it anywhere would count an answer that *mentions* the
    sources not covering some sub-part -- which is the behaviour prompt D was
    built to produce (answer the part that is covered, say which part is not)
    and is the opposite of a refusal.
    """
    return answer.strip().startswith(REFUSAL_OPENING)


def build_prompt(question: str, hits) -> str:
    blocks = []
    for n, hit in enumerate(hits, 1):
        p = hit.payload
        heading = " > ".join(p["heading_path"]) or "(no heading)"
        blocks.append(
            f"[{n}] SQLAlchemy {p['sqlalchemy_version']} — {p['source_path']}\n"
            f"     {heading}\n\n{p['text']}"
        )
    sources = "\n\n---\n\n".join(blocks)
    return f"SOURCES\n\n{sources}\n\n---\n\nQUESTION: {question}\n\nANSWER:"


def generate(prompt: str) -> tuple[str, dict]:
    """
    One non-streaming call to Ollama. Returns the answer and its timings.

    Ollama reports token counts and nanosecond durations, so tokens/second is
    read off the response rather than timed from outside — an outside timer
    would include model load on a cold call and report a number that is not
    generation speed.
    """
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }).encode()

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as exc:
        sys.exit(
            f"cannot reach Ollama at {OLLAMA_URL}: {exc}\n"
            f"  start it, and check `ollama list` has {MODEL}"
        )
    wall = time.perf_counter() - started

    eval_count = data.get("eval_count", 0)
    eval_ns = data.get("eval_duration", 0) or 1
    timings = {
        "wall_seconds": round(wall, 1),
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "answer_tokens": eval_count,
        "tokens_per_second": round(eval_count / (eval_ns / 1e9), 1),
    }
    return data["message"]["content"].strip(), timings


def ask(question: str, k: int = DEFAULT_K, version: str | None = None,
        retrieval_only: bool = False, show_prompt: bool = False) -> None:
    hits = index.retrieve(question, limit=k, version=version)
    if not hits:
        sys.exit("no hits — is the collection loaded? `uv run python -m rag.index`")

    prompt = build_prompt(question, hits)
    if show_prompt:
        print(f"{'=' * 78}\nPROMPT SENT TO {MODEL}\n{'=' * 78}\n{SYSTEM}\n\n{prompt}\n")

    if not retrieval_only:
        answer, timings = generate(prompt)
        print(f"\n{'=' * 78}\nQ: {question}\n{'=' * 78}\n")
        print(answer)
        print(
            f"\n[{MODEL}  {timings['answer_tokens']} tokens  "
            f"{timings['tokens_per_second']} tok/s  {timings['wall_seconds']}s wall  "
            f"prompt {timings['prompt_tokens']} tokens]"
        )

    # Always printed, never behind a flag. See the module docstring.
    print(f"\n{'-' * 78}\nSOURCES\n{'-' * 78}")
    for n, hit in enumerate(hits, 1):
        p = hit.payload
        heading = " > ".join(p["heading_path"]) or "(no heading)"
        print(f"\n[{n}] {hit.score:.3f}  SQLAlchemy {p['sqlalchemy_version']}  {p['source_path']}")
        print(f"    {heading}")
        print(f"    {p['text'][:180].strip().replace(chr(10), ' ')}...")


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("--"):
        sys.exit('usage: uv run python -m rag.ask "your question" [--k N] [--version 2.0.51] '
                 '[--retrieval-only] [--show-prompt]')

    def flag(name, cast, default=None):
        return cast(argv[argv.index(name) + 1]) if name in argv else default

    ask(
        argv[0],
        k=flag("--k", int, DEFAULT_K),
        version=flag("--version", str),
        retrieval_only="--retrieval-only" in argv,
        show_prompt="--show-prompt" in argv,
    )


if __name__ == "__main__":
    main()
