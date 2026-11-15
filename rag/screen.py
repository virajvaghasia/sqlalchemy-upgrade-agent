"""Which hosted model should the demo page answer with? A screen, not a ruling.

    uv run python -m rag.screen --probe      # one tiny call per candidate: who answers at all
    uv run python -m rag.screen --run        # the 100 test questions through every candidate
    uv run python -m rag.screen --run --only <model>,<model>   # re-ask what failed, those models only
    uv run python -m rag.screen --report     # the table, from the saved rows, no network

WHY IT EXISTS

The page answers with a model on NVIDIA's free endpoints, and that catalog moves:
two models the page relied on have already left it, and on 2026-11-15 its second
fallback returned 404. Newer free models are listed. "Newer" is not "better on
this task", and the only way this project says which model is better is to ask
all of them the same questions.

WHAT IS HELD FIXED

Every model gets the same 100 questions, the same system message, the same prompt
(`ask.build_prompt`, so the one the page ships) and THE SAME FIVE PAGES. The pages
are not searched for again: they are read from the saved run of the current model
(`deliverables/nemotron-all-phase6.json`), which stored the five page ids it was
given for every question. So a difference between two models here cannot be a
difference in what search returned.

The current model is asked again too, in the same sitting. Its published 0.58 was
taken before the citation sentence was added to the prompt, and answers drift
between days, so a candidate is compared with the control run beside it and never
with the old number.

THE RULE, WRITTEN BEFORE THE FIRST CALL

  * A run with more than MAX_MISSING questions unanswered by the endpoint (empty
    reply, timeout, HTTP error) is not quoted and that model is not used.
  * The DEFAULT model changes only if a candidate is AHEAD of the control: at
    least 6 questions the control failed and it delivers, at most 1 the other way,
    exact McNemar p < 0.05, and no more unanswerable questions answered than the
    control answered. Anything less and the default stays where it is.
  * A FALLBACK must not be BEHIND the control (more broken than fixed with
    p < 0.05) and must answer at most 2 of the 9 unanswerable questions. Fallbacks
    are ordered by questions delivered.

WHAT THIS DOES NOT MEASURE

Whether the answers are supported by the pages (that needs the judge model, about
70 more calls per candidate) or whether they are correct. A new default would need
the judge run before any figure for it goes on the page. "Delivered" means the
right page was among the five and the model did not decline.
"""

from __future__ import annotations

import json
import statistics
import sys
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor

from rag import ask, escalate, faithful, judge, score

CONTROL = "nvidia/nemotron-3-ultra-550b-a55b"
# Every other model below answered a one-word probe on 2026-11-15 in under 15 seconds.
# Left out, and why: nemotron-4-340b, nemotron-3-super-120b and kimi-k2.6 returned 404 on
# this key; deepseek-v4.1-flash, gemma-4-31b and step-5-preview timed out at 90 seconds;
# gpt-oss-20b is the judge, and a judge must not grade its own answers.
#
# CHANGED AFTER THE RUN STARTED, both before any result was read off the table:
#   - mistral-large-4-1t-a52b was in the first list and is out. It answers a one-word
#     probe in a second and never answered a real question: zero rows after ten
#     minutes, and a single question sent alone timed out at 100 seconds.
#   - nemotron-3.5-lightning is in. It is one of the page's existing fallbacks and
#     was left out of the first list by oversight.
CANDIDATES = [
    CONTROL,
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "minimaxai/minimax-m3.1-flash",
    "z-ai/glm-5.3-flash",
    "poolside/laguna-xs-2.1",
]
# A model that fails this many questions in a row is not asked the rest: each failure
# costs several minutes of retries, and a hung endpoint would hold the run for a day.
GIVE_UP_AFTER = 3
PAGES = judge.DELIVERABLES / "nemotron-all-phase6.json"  # the five page ids per question
ROWS = judge.DELIVERABLES / "model-screen.json"
MAX_MISSING = escalate.MAX_MISSING
FALLBACK_FABRICATIONS = escalate.FABRICATION_BAR


class Page:
    """A saved chunk in the shape `ask.build_prompt` reads a search hit in."""

    def __init__(self, chunk: dict):
        self.payload = {**chunk, "chunk_id": chunk["id"]}


def saved_pages(path=PAGES) -> dict[str, list[str]]:
    return {r["id"]: r["hits"] for r in json.loads(path.read_text())["rows"]}


def request_body(model: str, question: str, hits) -> dict:
    """`escalate.request_body` with the model swapped and nothing else."""
    return {**escalate.request_body(question, hits), "model": model}


def ask_model(model: str, items: list[dict], pages: dict, chunks: dict, *, post, key, done=(), save=None, log=print):
    """One model through every question. A question the endpoint fails on is left
    out of the rows, so a re-run asks it again; it is never scored as a decline."""
    rows = list(done)
    have = {r["id"] for r in rows}
    failed_in_a_row = 0
    for it in items:
        if it["id"] in have:
            continue
        if failed_in_a_row >= GIVE_UP_AFTER:
            log(f"  {model} gave up: {GIVE_UP_AFTER} questions in a row got no answer from the endpoint")
            break
        hits = [Page(chunks[c]) for c in pages[it["id"]]]
        started = time.monotonic()
        try:
            data = post("chat/completions", request_body(model, it["question"], hits), key)
            parsed = escalate.parse(data)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError) as exc:
            log(f"  {model} {it['id']} SKIPPED ({type(exc).__name__})")
            failed_in_a_row += 1
            continue
        failed_in_a_row = 0
        row = {
            "id": it["id"],
            "model": model,
            "hits": pages[it["id"]],
            "seconds": round(time.monotonic() - started, 1),
            **parsed,
        }
        row["empty"] = escalate.empty(row)
        row["refused"] = (not row["empty"]) and ask.refused(row["answer"])
        rows.append(row)
        if save:
            save(model, rows)
    return rows


def summarise(rows: list[dict], control: list[dict], golden: dict, chunks: dict, expected: int) -> dict:
    out = escalate.outcome_rows(rows, golden, chunks)
    base = escalate.outcome_rows(control, golden, chunks)
    answerable = [r for r in out if r["answerable"]]
    answered = [r for r in out if not r["refused"]]
    p = escalate.paired(out, base)
    fabricated = sorted(r["id"] for r in out if not r["answerable"] and not r["refused"])
    return {
        "missing": expected - len(out),
        "answerable": len(answerable),
        "delivered": sum(escalate.route.delivered(r) for r in answerable),
        "declined_with_page": sum(r["answer_in_prompt"] and r["refused"] for r in answerable),
        "fabricated": fabricated,
        "unanswerable_asked": sum(not r["answerable"] for r in out),
        "uncited": sum(not judge.citations(r["answer"]) for r in answered),
        "answered": len(answered),
        "median_seconds": statistics.median(r["seconds"] for r in rows) if rows else None,
        "paired": p,
        "verdict": escalate.verdict(p),
    }


def decide(summaries: dict[str, dict]) -> dict:
    """The rule in the module docstring, applied. Returns the default and the fallbacks."""
    control = summaries[CONTROL]
    usable = {m: s for m, s in summaries.items() if s["missing"] <= MAX_MISSING}
    default = CONTROL
    if CONTROL in usable:
        ahead = [
            m
            for m, s in usable.items()
            if m != CONTROL and s["verdict"] == "AHEAD" and len(s["fabricated"]) <= len(control["fabricated"])
        ]
        if ahead:
            default = max(ahead, key=lambda m: usable[m]["delivered"])
    fallbacks = [
        m
        for m, s in usable.items()
        if m != default and s["verdict"] != "BEHIND" and len(s["fabricated"]) <= FALLBACK_FABRICATIONS
    ]
    # A control that lost its place as default is still the measured model: it only
    # has to be usable to stay in the list, which the loop above already checked
    # against the same two conditions (its own verdict is LEVEL by construction).
    fallbacks.sort(key=lambda m: -usable[m]["delivered"])
    unused = [m for m in summaries if m != default and m not in fallbacks]
    return {"default": default, "fallbacks": fallbacks, "unused": unused}


def report(saved: dict, golden: dict, chunks: dict, out=print) -> dict:
    expected = len(escalate.all_ids(golden))
    control = saved.get(CONTROL, [])
    summaries = {m: summarise(rows, control, golden, chunks, expected) for m, rows in saved.items()}
    out(f"MODEL SCREEN: {expected} questions, the same five pages and the same prompt for every model")
    out("")
    out(f"  {'model':<36} {'delivered':>10} {'declined':>9} {'made up':>8} {'uncited':>9} {'median':>7} {'missing':>8}")
    out(f"  {'':<36} {'':>10} {'w/ page':>9} {'of 9':>8} {'':>9} {'':>7} {'':>8}")
    for m, s in summaries.items():
        rate = f"{s['delivered']}/{s['answerable']}"
        med = f"{s['median_seconds']:.1f}s" if s["median_seconds"] is not None else "-"
        out(
            f"  {m:<36} {rate:>10} {s['declined_with_page']:>9} {len(s['fabricated']):>8} "
            f"{str(s['uncited']) + '/' + str(s['answered']):>9} {med:>7} {s['missing']:>8}"
        )
    out("")
    out(f"  against {CONTROL}, same sitting, question by question:")
    for m, s in summaries.items():
        if m == CONTROL:
            continue
        p = s["paired"]
        out(
            f"  {m:<36} fixed {len(p['fixed']):>2}  broken {len(p['broken']):>2}  "
            f"p = {p['p']:.4f}  over {p['n']}  -> {s['verdict']}"
        )
    if CONTROL in summaries:
        d = decide(summaries)
        out("")
        out(f"  default    {d['default']}")
        out(f"  fallbacks  {', '.join(d['fallbacks']) or '(none)'}")
        out(f"  not used   {', '.join(d['unused']) or '(none)'}")
    return summaries


def probe(key: str, out=print) -> None:
    def one(model):
        body = {
            "model": model,
            "temperature": 0,
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        }
        started = time.monotonic()
        try:
            data = escalate.nvidia_chat("", body, key, timeout=90)
            text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "(empty)"
            state = f"200 {text.strip()[:20]!r}"
        except urllib.error.HTTPError as exc:
            state = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError) as exc:
            state = type(exc).__name__
        return model, state, time.monotonic() - started

    with ThreadPoolExecutor(len(CANDIDATES)) as pool:
        for model, state, seconds in pool.map(one, CANDIDATES):
            out(f"  {model:<36} {state:<28} {seconds:5.1f}s")


def main() -> None:
    argv = sys.argv[1:]
    golden = {i["id"]: i for i in score.load_golden()}
    saved = json.loads(ROWS.read_text()) if ROWS.exists() else {}
    if "--report" in argv:
        report(saved, golden, score.load_chunks())
        return
    key = faithful.env_key(faithful.NVIDIA_KEY_VAR)
    if not key:
        sys.exit(f"no {faithful.NVIDIA_KEY_VAR} in the environment or .env; nothing called")
    if "--probe" in argv:
        probe(key)
        return
    if "--run" not in argv:
        sys.exit(__doc__)
    chunks, pages = score.load_chunks(), saved_pages()
    items = [golden[i] for i in escalate.all_ids(golden)]
    lock = threading.Lock()

    def save(model, rows):
        with lock:
            saved[model] = rows
            ROWS.write_text(json.dumps(saved, indent=1) + "\n")

    post = faithful.retrying(escalate.nvidia_chat)
    log = lambda *a: print(*a, flush=True)

    def one(model):
        rows = ask_model(model, items, pages, chunks, post=post, key=key, done=saved.get(model, []), save=save, log=log)
        log(f"{model}: {len(rows)} of {len(items)} asked")

    # One thread per model, questions in order inside it: the models answer at
    # different speeds and none of them waits on another.
    # `--only a,b` asks just those models: a re-run for the questions an endpoint
    # failed on should not also restart a model that was stopped on purpose.
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else CANDIDATES
    unknown = [m for m in only if m not in CANDIDATES]
    if unknown:
        sys.exit(f"not in CANDIDATES: {', '.join(unknown)}")
    with ThreadPoolExecutor(len(only)) as pool:
        list(pool.map(one, only))
    report(saved, golden, score.load_chunks())


if __name__ == "__main__":
    main()
