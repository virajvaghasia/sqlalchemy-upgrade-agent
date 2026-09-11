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

SYSTEM = (
    "You help a developer upgrade code from SQLAlchemy 1.4 to 2.0.\n"
    "You may call tools. Call ONE tool at a time and wait for its result.\n"
    "When you have enough to answer, answer in prose and cite sources as "
    "[1], [2].\n"
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
        log=lambda *a: None) -> dict:
    """One question, up to `max_steps` tool calls, one answer or one decline.

    Returns the transcript as well as the answer, because a trace nobody can
    read is how an agent's failures become unattributable -- the thing tools
    were built and measured first to avoid (`D88`).
    """
    generate = generate or (lambda messages: toolcall.ask_messages(messages))
    call_tool = call_tool or _default_tools

    messages = [{"role": "system", "content": SYSTEM},
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
