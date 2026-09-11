"""Phase 5, Step 0 — can the local model emit a valid tool call at all?

**Nothing in Phase 5 is built until this prints a number.** `qwen2.5-coder:7b`
has been measured in this repo doing exactly one thing: answering once, in
prose, with five passages already in the prompt. It has never been asked to
choose a tool. `PHASE-5.md` opens on the arithmetic that makes that the
phase-deciding question -- an agent is three or more generations where `0.43`
was measured on one.

**Ollama reports `capabilities: ['completion', 'tools', 'insert']` for this
model.** That is the model card's claim, not a measurement, and this file
exists because the two are different things. A declared capability that fails
on our questions is exactly the kind of thing this repo has caught before: the
healthcheck that "passed" because `/dev/tcp` is a bash builtin and the
container ran `sh`.

WHAT IS COUNTED, and why only these:

  valid       a tool call came back, the name is one of the two we offered,
              and the required argument is present and non-empty. **A call
              that does not parse is not a retry problem, it is a dead end**
              -- this is the number that can end the phase.

  right       the right tool for the question. Measured on a SYNTHETIC set
              whose label is unambiguous by construction (below), never on the
              golden set -- inventing labels for 100 real questions and then
              grading against them is how a benchmark measures its author.

WHAT IS NOT COUNTED HERE, deliberately:

  resolves    whether `check_api("Query.from_self")` names something real.
              That needs the tool to exist and to run against the pinned
              `sqlalchemy==2.0.51`, which is Step 1. Counting a fake version
              of it here would be a number about this file rather than about
              the model.

The two tools are deliberately far apart. If the model cannot separate "look
it up in the docs" from "check whether this symbol still exists", it will not
separate anything subtler, and a harder pair would only tell us the same thing
later and more expensively.
"""

import json
import pathlib
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
GOLDEN = REPO / "deliverables" / "golden.json"

MODEL = "qwen2.5-coder:7b"
HOST = "http://127.0.0.1:11434"

# Temperature 0 for the same reason every other run in this repo uses it, and
# with the same caveat attached: on this machine it does NOT make output
# repeatable across days (D54, D84). Any before/after built on this probe is
# re-run in one sitting or run on the lab.
TEMPERATURE = 0.0

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": (
                "Search the SQLAlchemy documentation for an explanation, a "
                "migration recipe, or example code. Use for how-to and why "
                "questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to look for, in plain words.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_api",
            "description": (
                "Check whether a symbol still exists in SQLAlchemy 2.0 and "
                "what its signature is. Use to confirm whether something was "
                "removed, renamed, or is still available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": (
                            "A dotted symbol, e.g. 'Query.from_self' or "
                            "'Session.get'."
                        ),
                    },
                },
                "required": ["symbol"],
            },
        },
    },
]

REQUIRED_ARG = {"search_docs": "query", "check_api": "symbol"}

SYSTEM = (
    "You help a developer upgrade code from SQLAlchemy 1.4 to 2.0. "
    "You have two tools. Call exactly one of them for the question you are "
    "given. Do not answer from memory."
)

# The synthetic probe set. **Labelled by construction, and that is the point.**
# Each `check_api` question asks whether a named symbol still exists; each
# `search_docs` question asks how or why. A reader can check the label from the
# question alone, which is what makes it usable without a human verification
# pass (`D06` governs the GOLDEN set; this is an instrument, not a ruler).
#
# They are written in developer phrasing on purpose. `D63` measured that
# phrasing, not provenance, decides retrieval -- and if it decides retrieval it
# may well decide tool choice too.
PROBE = [
    ("check_api", "Does Query.from_self still exist in SQLAlchemy 2.0?"),
    ("check_api", "Was Session.query removed in 2.0 or is it still there?"),
    ("check_api", "Is engine.execute still available on Engine in 2.0?"),
    ("check_api", "Does Session.get exist in SQLAlchemy 2.0?"),
    ("check_api", "Has Table.tometadata been renamed in 2.0?"),
    ("check_api", "Is Row.keys() still a method in 2.0?"),
    ("check_api", "Does declarative_base still exist or did it move?"),
    ("check_api", "Was MetaData.bind removed in SQLAlchemy 2.0?"),
    ("check_api", "Is Query.get still available in 2.0?"),
    ("check_api", "Does select() still accept a list of columns in 2.0?"),
    ("search_docs", "How do I rewrite a query that used from_self in 2.0?"),
    ("search_docs", "Why does my Comment never get INSERTed after I set the parent?"),
    ("search_docs", "How do I migrate connectionless execution to 2.0?"),
    ("search_docs", "What is the recommended way to load relationships eagerly in 2.0?"),
    ("search_docs", "How do I turn on the 2.0 deprecation warnings before upgrading?"),
    ("search_docs", "What should I use instead of the Query API in 2.0?"),
    ("search_docs", "How do I write a select with a join in the 2.0 style?"),
    ("search_docs", "Why am I getting MissingGreenlet with async SQLAlchemy?"),
    ("search_docs", "How do I convert my declarative models to the new typing style?"),
    ("search_docs", "What changed about autobegin and when a transaction starts?"),
]


def post(body: dict, timeout: int = 120) -> dict:
    request = urllib.request.Request(
        f"{HOST}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def ask(question: str, model: str = MODEL, transport=post) -> dict:
    """One question, tools offered, whatever comes back.

    Returns the raw shape rather than a verdict so `classify` can be tested
    against handcrafted replies with no server running -- the same reason
    `faithful.generate` takes its transport as an argument.
    """
    return transport({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": question}],
        "tools": TOOLS,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    })


def _validate(name, args, channel: str) -> dict:
    """Same checks whichever channel the call arrived on."""
    if isinstance(args, str):                 # some servers stringify it
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {"outcome": "unparseable_args", "tool": name, "arg": None}
    if name not in REQUIRED_ARG:
        return {"outcome": "unknown_tool", "tool": name, "arg": None}
    value = (args or {}).get(REQUIRED_ARG[name])
    if not isinstance(value, str) or not value.strip():
        return {"outcome": "missing_arg", "tool": name, "arg": None}
    return {"outcome": channel, "tool": name, "arg": value.strip()}


def ask_messages(messages: list[dict], model: str = MODEL,
                 transport=post) -> dict:
    """A whole conversation, tools offered — what the agent loop needs.

    `ask()` is the single-question probe Step 0 used; this is the same request
    with the caller's message list, so the two cannot drift on tool schemas,
    temperature or the offered tools.
    """
    return transport({
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    })


def classify(reply: dict) -> dict:
    """What came back, and **on which channel** -- the distinction this
    function was rewritten for on the day it was written.

    The first version read only `message.tool_calls` and scored the first run
    at **0 valid out of 20**. Every reply was in fact a correct call, with the
    right tool and a well-formed argument, sitting in `message.content` as
    JSON text. Ollama 0.34.0 reports `capabilities: ['tools']` for this model
    and does not lift its calls into `tool_calls`.

    **So "the model cannot call tools" would have been a claim about this
    parser.** Same family as the healthcheck that passed because `/dev/tcp` is
    a bash builtin, and as D76/D79 -- an instrument breaking in the direction
    of the thing under test, only this time the direction was unflattering.

    The two channels stay SEPARATE outcomes rather than being merged into one
    `valid`, because they mean different things for Step 1: `tool_calls` is
    the protocol MCP speaks, and `content_json` is text an agent must parse
    itself, with no guarantee the model will not wrap it in prose next time.

    `prose` is its own outcome and NOT a kind of invalid. A model that answers
    in words when it was asked for a tool has understood the question and
    ignored the protocol; a model that emits `{"name": "search"}` has not. The
    fixes are different -- one is a prompt, the other may be a dead end -- so
    the counts must be different too.
    """
    calls = (reply.get("message") or {}).get("tool_calls") or []
    if not calls:
        content = ((reply.get("message") or {}).get("content") or "").strip()
        if not content:
            return {"outcome": "empty", "tool": None, "arg": None}
        # A JSON object naming one of our tools is a call on the wrong channel.
        # Anything else -- prose, a fenced block, an apology -- is not.
        #
        # **A LEADING object counts even when prose follows it**, and that was
        # measured rather than anticipated. Step 0 probed single turns and got
        # 120 replies that were pure JSON. Inside the agent loop the same model
        # emits the call AND then starts answering in the same field:
        #
        #     {"name": "search_docs", "arguments": {...}}\n\n[1] SQLAlchemy 2.0...
        #
        # `json.loads` on the whole string raises, so the first version scored
        # that as `prose` -- the loop read it as an answer and **never ran the
        # tool the model had just asked for.** Fourth instrument in this repo to
        # break only once the thing under test started behaving differently
        # (D76, D79, D87). `raw_decode` reads the leading value and reports
        # where it stopped.
        try:
            blob, _ = json.JSONDecoder().raw_decode(content)
        except json.JSONDecodeError:
            return {"outcome": "prose", "tool": None, "arg": None}
        if not isinstance(blob, dict) or "name" not in blob:
            return {"outcome": "prose", "tool": None, "arg": None}
        return _validate(blob.get("name"), blob.get("arguments"), "content_json")
    call = (calls[0].get("function") or {})
    name = call.get("name")
    args = call.get("arguments")
    return _validate(name, args, "tool_calls")


def golden_questions(path: pathlib.Path = GOLDEN) -> list[str]:
    return [i["question"] for i in json.loads(path.read_text())["items"]]


USABLE = ("tool_calls", "content_json")


def run(pairs: list[tuple[str | None, str]], model: str = MODEL,
        ask_one=None, log=print) -> dict:
    """Probe every question and count outcomes. `want` may be None (unlabelled).

    Returns the counts the report prints, so a test can drive this with a fake
    transport and pin the arithmetic rather than the wording.
    """
    ask_one = ask_one or (lambda q: ask(q, model=model))
    rows = []
    for want, question in pairs:
        try:
            got = classify(ask_one(question))
        except (urllib.error.URLError, TimeoutError) as exc:
            # D75, third module to learn it: one unreachable call costs one
            # question, never the run.
            got = {"outcome": f"failed:{type(exc).__name__}",
                   "tool": None, "arg": None}
        rows.append({"want": want, "question": question, **got})
    usable = [r for r in rows if r["outcome"] in USABLE]
    labelled = [r for r in usable if r["want"]]
    return {
        "n": len(rows),
        "rows": rows,
        "usable": len(usable),
        "native": sum(1 for r in rows if r["outcome"] == "tool_calls"),
        "content": sum(1 for r in rows if r["outcome"] == "content_json"),
        "right": sum(1 for r in labelled if r["want"] == r["tool"]),
        "labelled": len(labelled),
    }


def report(got: dict, model: str, label: str) -> None:
    print(f"\nTOOL CALLS — {label}, {model}, temperature {TEMPERATURE}")
    print(f"  usable call      {got['usable']}/{got['n']}"
          f" = {got['usable'] / got['n']:.0%}" if got["n"] else "  no questions")
    if got["labelled"]:
        print(f"  right tool       {got['right']}/{got['labelled']}"
              f" = {got['right'] / got['labelled']:.0%}  (labelled by construction)")
    print(f"  ...on `tool_calls` (the MCP channel)   {got['native']}")
    print(f"  ...on `message.content` as JSON text   {got['content']}")
    bad = [r for r in got["rows"] if r["outcome"] not in USABLE]
    for r in bad:
        print(f"    {r['outcome']:<18} {r['question'][:64]}")
    if got["content"] and not got["native"]:
        print("  NOTE: every call arrived as content text. An agent built on "
              "this model parses\n        JSON itself; it cannot assume the "
              "MCP tool-call channel (D87).")


def main() -> None:
    import sys
    argv = sys.argv[1:]
    model = MODEL
    if "--model" in argv:
        model = argv[argv.index("--model") + 1]
    if "--golden" in argv:
        pairs = [(None, q) for q in golden_questions()]
        label = "the 100 golden questions, real developer phrasing"
    else:
        pairs = PROBE
        label = f"{len(PROBE)} synthetic questions, labelled by construction"
    report(run(pairs, model=model), model, label)


if __name__ == "__main__":
    main()
