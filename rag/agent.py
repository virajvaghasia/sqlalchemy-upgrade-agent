"""Phase 5, Step 2 — the loop, and the failure path that justifies it.

**An agent with no failure path is decoration**, so the recovery behaviours are
built here in the same file as the loop rather than bolted on after a demo.

WHY THIS IS CHANNEL-AGNOSTIC, which is a design decision and not an accident.

`D87` measured that `qwen2.5-coder:7b` returns tool calls as JSON in
`message.content` and never on `message.tool_calls` -- on the Mac, on Ollama
0.34.0. Round 17 is open precisely because that may be a **server version**
fact rather than a model fact, and the lab runs an older Ollama.

So this loop never looks at either field. It calls `toolcall.classify`, which
already treats `tool_calls` and `content_json` as two outcomes of one question,
and it acts on `outcome in toolcall.USABLE`. **Whichever way Round 17 comes
back, this file does not change.** Building it the other way would have meant
writing code whose correctness depended on an open measurement.

THE FOUR FAILURE PATHS, each with the defect it exists for:

  tool raised        retry once, then fall back. `D75`, and this repo has now
                     met it in four modules -- twice the expensive way, once
                     at generation 150 of 300 and once at item 63 of 64.

  tool returned
  nothing            reformulate once; do NOT repeat the same call. The 17
                     absents (`D70`) are the measured case where no
                     reformulation helps, so the loop must be able to stop.

  budget exhausted   say so. An agent that loops is a worse failure than one
                     that declines, because it fails slowly and invisibly.

  nothing found      decline, using the string `ask.refused()` detects.
                     **Phase 4's entire refusal instrumentation depends on
                     this.** If the agent invents its own way of saying no,
                     `--refusals`, `rag.judge` and `rag.faithful` all stop
                     seeing declines and start scoring them as answers.
"""

import json

from rag import ask, toolcall, tools

# How many tool calls one question may cost. Deliberately small: `PHASE-5.md`
# opens on the arithmetic that each generation is a place to lose, and a wide
# budget hides a bad plan behind a retry. Raise it only with a measurement.
MAX_STEPS = 4

# The agent's decline. NOT a new sentence -- `ask.REFUSAL_OPENING` is the one
# `ask.refused()` anchors on, and every Phase 4 instrument is a prefix test
# against it (`D76`).
DECLINE = ask.REFUSAL_OPENING + " this."

# --- the system prompt, and the variant under test (E1) ---------------------
#
# MEASURED 2026-09-11, lab Round 17.4: under `SYSTEM` the agent called **no
# tool on 96 of 100** golden questions and chained two on none. The standalone
# probe -- same model, same machine, same 100 questions -- got a usable call on
# **100 of 100** (`D87`).
#
# The only difference is these words. `SYSTEM` says "You may call tools" and
# then explains how to answer in prose; the probe says "Call exactly one of
# them" and "Do not answer from memory". That is the `D74` shape -- one
# permissive word against one imperative -- and the swing is 96 points.
#
# Both are kept and **the shipped one stays `SYSTEM`** until a measurement
# moves it. `D74` is the precedent: prompt `H` beat `D` on the Mac and was
# never shipped, because it did not reproduce on a second machine.

SYSTEM = (
    "You help a developer upgrade code from SQLAlchemy 1.4 to 2.0.\n"
    "You may call tools. Call ONE tool at a time and wait for its result.\n"
    "When you have enough to answer, answer in prose and cite sources as "
    "[1], [2].\n"
    f'If the tools cannot establish the answer, reply "{DECLINE}"'
)


# E1's candidate. Two changes and no others, so a difference is attributable:
# the permission becomes an obligation, and "do not answer from memory" is
# stated -- the probe's own words, which produced 100/100.
#
# **The citation clause is deliberately UNCHANGED.** E3 measured 31 of 53
# memory answers carrying `[n]` markers against ZERO retrieved sources, so this
# model will write citations with nothing behind them. If the candidate
# restores tool calls, its citations must be re-measured rather than assumed
# fixed -- that is the whole lesson of `D79` and of E3.
SYSTEM_MUSTCALL = (
    "You help a developer upgrade code from SQLAlchemy 1.4 to 2.0.\n"
    "You have two tools. You MUST call a tool before answering — do not "
    "answer from memory.\n"
    "Call ONE tool at a time and wait for its result. Once you have tool "
    "results, answer in prose and cite sources as [1], [2].\n"
    f'If the tools cannot establish the answer, reply "{DECLINE}"'
)


def _echo(name: str, argument: str) -> str:
    """The call, written back into the transcript in the shape the model emits.

    Uses the schema's own argument name rather than a placeholder: the model is
    about to read its own turn back, and a transcript that does not look like
    what it produced is a needless source of confusion.
    """
    return json.dumps({"name": name,
                       "arguments": {toolcall.REQUIRED_ARG.get(name, "arg"):
                                     argument}})


def _observation(name: str, result) -> str:
    """What the model is shown after a tool runs.

    A tool that found nothing says so **in words the model can act on**, rather
    than an empty list it may read as a formatting problem. `check_api`'s
    `exists: False` is the case that matters: it is an ANSWER (the API was
    removed) and must not read as a broken lookup (`D88`).
    """
    if name == "check_api":
        if result.get("error"):
            return f"check_api failed: {result['error']}"
        if not result.get("exists"):
            return ("check_api: NOT FOUND. This symbol does not exist in the "
                    "pinned version. That is a definite answer, not an error.")
        return (f"check_api: exists. signature: {result.get('signature')}. "
                f"{result.get('doc') or ''}").strip()
    if name == "search_docs":
        if not result:
            return "search_docs: no passages matched. Try different wording once."
        return "\n\n".join(
            f"[{n}] ({hit['chunk_id']}) {hit['text'][:600]}"
            for n, hit in enumerate(result, 1))
    return json.dumps(result)[:2000]


def run(question: str, generate=None, call_tool=None, max_steps: int = MAX_STEPS,
        log=lambda *a: None, system: str | None = None) -> dict:
    """One question, up to `max_steps` tool calls, one answer or one decline.

    Returns the transcript as well as the answer, because a trace nobody can
    read is how an agent's failures become unattributable -- the thing tools
    were built and measured first to avoid (`D88`).
    """
    generate = generate or (lambda messages: toolcall.ask_messages(messages))
    call_tool = call_tool or _default_tools

    messages = [{"role": "system", "content": system or SYSTEM},
                {"role": "user", "content": question}]
    trace, seen_calls = [], set()

    for step in range(1, max_steps + 1):
        reply = generate(messages)
        got = toolcall.classify(reply)

        if got["outcome"] not in toolcall.USABLE:
            # Prose at this point is the model answering, which is the normal
            # way out of the loop -- not a failure.
            content = ((reply.get("message") or {}).get("content") or "").strip()
            trace.append({"step": step, "kind": "answer"})
            return {"answer": content or DECLINE, "steps": step,
                    "trace": trace, "stopped": "answered"}

        name, argument = got["tool"], got["arg"]
        key = (name, argument)
        if key in seen_calls:
            # Repeating a call cannot produce new information and is the
            # cheapest way for a loop to burn its whole budget looking busy.
            trace.append({"step": step, "kind": "repeat", "tool": name,
                          "arg": argument})
            return {"answer": DECLINE, "steps": step, "trace": trace,
                    "stopped": "repeated_call"}
        seen_calls.add(key)

        result, error = call_tool(name, argument)
        if error:
            # D75: retry once, then fall back. The retry is the loop's next
            # iteration with the failure visible to the model, NOT a silent
            # re-call -- a model that cannot see the error cannot route around it.
            trace.append({"step": step, "kind": "tool_error", "tool": name,
                          "arg": argument, "error": error})
            log(f"  [{step}] {name}({argument!r}) FAILED: {error}")
            messages.append({"role": "assistant",
                             "content": _echo(name, argument)})
            messages.append({"role": "user",
                             "content": f"The tool failed: {error}. Try a "
                                        f"different tool or a different "
                                        f"argument, or decline."})
            continue

        observation = _observation(name, result)
        trace.append({"step": step, "kind": "tool", "tool": name,
                      "arg": argument, "observation": observation[:200]})
        log(f"  [{step}] {name}({argument!r})")
        messages.append({"role": "assistant", "content": _echo(name, argument)})
        messages.append({"role": "user", "content": observation})

    # Budget exhausted. **Declining here is the whole point**: an agent that
    # silently returns its best half-formed guess after four tool calls is
    # indistinguishable, downstream, from one that knew the answer.
    trace.append({"step": max_steps, "kind": "budget"})
    return {"answer": DECLINE, "steps": max_steps, "trace": trace,
            "stopped": "budget"}


def _default_tools(name: str, argument: str):
    """Dispatch, returning `(result, error)` so a failure is data, not an
    exception crossing a loop boundary."""
    try:
        if name == "check_api":
            got = tools.check_api(argument)
            return got, got.get("error")
        if name == "search_docs":
            return tools.search_docs(argument), None
        return None, f"unknown tool {name!r}"
    except Exception as exc:                  # noqa: BLE001 - see below
        # Broad on purpose, and narrow in effect: this converts ANY tool
        # failure into the loop's `error` path, which is the behaviour D75
        # says must exist. The alternative -- letting it propagate -- is
        # exactly the bug that killed a sweep at item 63 of 64.
        return None, f"{type(exc).__name__}: {exc}"


# --- Step 3: run the golden set through the agent ---------------------------
#
# **The question this answers is the one most likely to have an unwelcome
# answer:** does routing the same 100 questions through a tool-using agent make
# single-answer quality WORSE than the one-shot pipeline Phase 4 measured?
#
# It needs no new labels. The golden set, `rag.judge --report` and every Phase 4
# column already exist; the agent is simply a different way of producing the
# `answer` field. That is deliberate -- a task set (Step 3's second half) costs
# human verification (`D06`), and this half costs none.

SWEEP_NAME = "agent-sweep-phase5"


def machine() -> str:
    """Same stamp `faithful.machine()` produces: a machine CLASS, not a
    hostname. `D83`: generation figures do not reproduce across machines, so a
    row that does not name its machine is under-labelled."""
    from rag import faithful
    return faithful.machine()


def sweep(items: list[dict], chunks: dict | None = None, run_one=None,
          checkpoint=None, log=print, resume: dict | None = None) -> list[dict]:
    """Every golden item through the agent, saved in Phase 4's row shape.

    Rows carry `answer_in_prompt` computed with **`score.rank_of_first_hit`,
    the same function `--refusals` and the prompt sweep use**, so the columns
    are comparable with `D72`'s table rather than merely similar to it. For the
    agent that means: *did a verified answer chunk come back from any
    `search_docs` call this run made?* -- the agent's own equivalent of "the
    page reached the prompt", since the agent chooses its own retrieval.
    """
    from rag import score

    chunks = chunks if chunks is not None else score.load_chunks()
    done = {r["id"]: r for r in (resume or {}).get("rows", [])}
    rows = list(done.values())

    for n, item in enumerate(items, 1):
        if item["id"] in done:
            log(f"  [{n}/{len(items)}] {item['id']}  (done, skipped)")
            continue
        seen_chunks: list[str] = []

        def call_tool(name, argument, _seen=seen_chunks):
            result, error = _default_tools(name, argument)
            if name == "search_docs" and not error:
                _seen.extend(hit["chunk_id"] for hit in result)
            return result, error

        try:
            got = (run_one or run)(item["question"], call_tool=call_tool)
        except Exception as exc:              # noqa: BLE001
            # D75, and by now the rule rather than the exception: one bad item
            # costs one item. A `failed` row is neither an answer nor a
            # refusal, and both halves of the comparison drop it.
            log(f"  [{n}/{len(items)}] {item['id']}  FAILED {type(exc).__name__}")
            rows.append({"id": item["id"], "failed": True,
                         "answerable": bool(item.get("answerable")),
                         "answer_in_prompt": False,
                         "provenance": item.get("provenance")})
            if checkpoint:
                checkpoint(rows)
            continue

        in_prompt = bool(item.get("answerable")) and seen_chunks and \
            score.rank_of_first_hit(seen_chunks, item, chunks) is not None
        rows.append({
            "id": item["id"],
            "provenance": item.get("provenance"),
            "answerable": bool(item.get("answerable")),
            "answer_in_prompt": bool(in_prompt),
            "answer": got["answer"],
            # The agent's sources ARE what it retrieved, so the citation
            # denominator is the number of passages it actually saw. Zero when
            # it never searched -- which is itself a measurement (an answer
            # with no lookup behind it).
            "n_sources": len(seen_chunks),
            "steps": got["steps"],
            "stopped": got["stopped"],
            "tools": [t.get("tool") for t in got["trace"] if t["kind"] == "tool"],
            "trace": got["trace"],
        })
        log(f"  [{n}/{len(items)}] {item['id']}  steps={got['steps']} "
            f"stopped={got['stopped']} tools={rows[-1]['tools']}")
        if checkpoint and n % 5 == 0:
            checkpoint(rows)
    if checkpoint:
        checkpoint(rows)
    return rows


def summarise(rows: list[dict]) -> dict:
    """Agent-specific counts. The generation and citation columns come from
    `rag.judge`'s own functions, never from a second copy here -- `D85` is what
    happens when one metric grows two implementations."""
    from rag import judge

    live = [r for r in rows if not r.get("failed")]
    used = [r for r in live if r.get("tools")]
    return {
        **judge._sweep_generation(rows),
        "no_tool_call": len(live) - len(used),
        "one_tool_only": sum(1 for r in used if len(r["tools"]) == 1),
        "multi_tool": sum(1 for r in used if len(r["tools"]) > 1),
        "stopped": {k: sum(1 for r in live if r.get("stopped") == k)
                    for k in ("answered", "budget", "repeated_call")},
    }


E1_ARMS = {"A_shipped": SYSTEM, "B_mustcall": SYSTEM_MUSTCALL}


def e1(items: list[dict], chunks: dict | None = None, run_one=None,
       log=print) -> dict:
    """Both system prompts over the same items, **in one sitting** (`D54`).

    Arms are interleaved per item rather than run one after the other, so a
    machine that drifts over an hour drifts through both arms equally. `D54`
    forced this rule for refusals and `D89` makes it sharper: whether a tool is
    called at all disagrees 50% across machines, so it is not a quantity to
    measure twice at different times.
    """
    from rag import judge, score

    chunks = chunks if chunks is not None else score.load_chunks()
    out = {arm: [] for arm in E1_ARMS}
    for n, item in enumerate(items, 1):
        for arm, prompt in E1_ARMS.items():
            seen: list[str] = []

            def call_tool(name, argument, _s=seen):
                result, error = _default_tools(name, argument)
                if name == "search_docs" and not error:
                    _s.extend(hit["chunk_id"] for hit in result)
                return result, error

            got = (run_one or run)(item["question"], call_tool=call_tool,
                                   system=prompt)
            used = [t.get("tool") for t in got["trace"] if t["kind"] == "tool"]
            report = judge.citation_report(got["answer"], len(seen))
            out[arm].append({
                "id": item["id"], "tools": used, "n_sources": len(seen),
                "answerable": True,
                "answer_in_prompt": bool(
                    seen and score.rank_of_first_hit(seen, item, chunks)
                    is not None),
                "answer": got["answer"],
                "out_of_range": bool(report["out_of_range"]),
            })
            log(f"  {arm} [{n}/{len(items)}] {item['id']} tools={used}")
    return out


def e1_report(out: dict) -> None:
    print("\n" + "=" * 66)
    print(f"E1 — system prompt A/B, one sitting (D54), n={len(next(iter(out.values())))}"
          f"   [{machine()}]")
    print("=" * 66)
    print(f"{'':<12}{'no tool':>9}{'one':>6}{'two+':>6}{'in prompt':>11}"
          f"{'delivered':>11}{'bad cites':>11}")
    for arm, rows in out.items():
        print(f"{arm:<12}"
              f"{sum(1 for r in rows if not r['tools']):>9}"
              f"{sum(1 for r in rows if len(r['tools']) == 1):>6}"
              f"{sum(1 for r in rows if len(r['tools']) > 1):>6}"
              f"{sum(1 for r in rows if r['answer_in_prompt']):>11}"
              f"{sum(1 for r in rows if r['answer_in_prompt'] and not ask.refused(r['answer'])):>11}"
              f"{sum(1 for r in rows if r['out_of_range']):>11}")
    print("\nbad cites = [n] pointing at a source that was never retrieved (E3)")
    print("two+      = chained tools. ZERO under both prompts on both machines")
    print("            so far — the one number that has reproduced everywhere.")


def main() -> None:
    import json as _json
    import pathlib
    import sys

    from rag import judge, score

    argv = sys.argv[1:]
    out = judge.DELIVERABLES / f"{SWEEP_NAME}.{machine()}.json"

    if "--report" in argv:
        if not out.exists():
            sys.exit(f"no rows yet: {out.name}\n"
                     f"  run: uv run python -m rag.agent --golden")
        saved = _json.loads(out.read_text())
        got = summarise(saved["rows"])
        print(f"\nAGENT — the golden set through the tool-using loop"
              f"  [{saved.get('machine', '?')}]")
        print(f"  end to end     {got['delivered']}/{got['n_answerable']} = "
              f"{got['end_to_end']:.2f}   (D72's shipped pipeline: 39/91 = 0.43 "
              f"on Darwin-arm64)")
        print(f"  over-refused   {got['over_refused']}"
              f"      fabricated {got['fabricated']}"
              f"      failed {got['failed']}")
        print(f"  no tool call   {got['no_tool_call']}"
              f"      one tool {got['one_tool_only']}"
              f"      two or more {got['multi_tool']}")
        print(f"  stopped        {got['stopped']}")
        print("  Compare item by item, not by the averages (D61) — and only "
              "against a run\n  from THIS machine (D83).")
        return

    if "--e1" in argv:
        from rag import score as _score
        n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
        items = [i for i in _score.load_golden() if i.get("answerable")][:n]
        got = e1(items)
        e1_report(got)
        path = judge.DELIVERABLES / f"e1-phase5.{machine()}.json"
        path.write_text(_json.dumps({"machine": machine(), "arms": got},
                                    indent=1) + "\n")
        print(f"\nsaved to {path.name}")
        return

    if "--golden" not in argv:
        print("usage: uv run python -m rag.agent --golden [--limit N] [--resume]\n"
              "       uv run python -m rag.agent --e1 [--n 20]\n"
              "       uv run python -m rag.agent --report")
        return

    # score.load_golden enforces D06 in code: anything whose verified_by
    # is not "human" is dropped, loudly, with its id named.
    items = score.load_golden()
    if "--limit" in argv:
        items = items[: int(argv[argv.index("--limit") + 1])]

    resume = None
    if "--resume" in argv and out.exists():
        prior = _json.loads(out.read_text())
        if prior.get("machine") != machine():
            sys.exit(f"those rows are from {prior.get('machine')}, this host is "
                     f"{machine()}. Two machines in one file is the mistake "
                     f"D83 cost a recovery from.")
        resume = prior
        print(f"resuming: {len(prior['rows'])} rows already done")
    elif out.exists():
        prior = _json.loads(out.read_text()).get("machine")
        if prior and prior != machine():
            sys.exit(f"{out.name} holds rows from {prior}; this host is "
                     f"{machine()}. Overwriting destroys the other machine's "
                     f"evidence (D83).")

    def save(rows):
        out.write_text(_json.dumps({"machine": machine(),
                                    "n": len(rows), "rows": rows}, indent=1) + "\n")

    print(f"agent over {len(items)} golden items — checkpointing every 5 to "
          f"{out.name}")
    rows = sweep(items, checkpoint=save, resume=resume)
    save(rows)
    print(f"\nsaved {len(rows)} rows to {out.name}")
    main_report = summarise(rows)
    print(f"  end to end {main_report['delivered']}/{main_report['n_answerable']}"
          f" = {main_report['end_to_end']:.2f}")


if __name__ == "__main__":
    main()
