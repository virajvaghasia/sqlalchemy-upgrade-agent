"""Phase 5, Step 1 — the three tools, built before the agent that calls them.

**Tools first, loop second**, for a reason that is not sequencing taste: these
are independently testable and independently useful, and an agent built on
tools nobody has measured produces failures you cannot attribute. The model returning tool calls as plain text
already made that mistake cheap to imagine -- a parser bug nearly ended the phase.

  search_docs        the corpus, through the SAME retrieval path the rest of
                     the system uses (`index.retrieve`). Not a second
                     retriever: a second one would drift from the graded one
                     and Phase 2's numbers would stop describing what the
                     agent sees.

  get_function_source
                     the actual source of a callable, read out of the pinned
                     `sqlalchemy==2.0.51` rather than out of the docs. Docs
                     describe; source is.

  check_api          does this symbol still exist in 2.0, and what is its
                     signature? **This is the differentiator and it is not
                     hypothetical.** the groundedness check proved `g065` fabricated by
                     measuring `hasattr(Operations, "create_view") is False`
                     on alembic while `create_table` in the same script was
                     real. As a tool the model can call BEFORE it writes, that
                     is the check that would have caught the fabrication at
                     generation time instead of in a post-mortem.

THE VERSION PROBLEM, and why there is a subprocess here.

This project's own environment is pinned to **SQLAlchemy 1.4.52** -- deliberately,
because `experiments/` is an instrument pointed at 1.4. So the process
asking "does this exist in 2.0?" cannot import 2.0 to find out. `verify_2_0.py`
solved this first and this module reuses its answer rather than inventing a
second one:

    uv run --no-project --with 'sqlalchemy==2.0.51' python -c ...

**One pin, one place.** `PIN` is imported from `verify_2_0` so a version bump
cannot leave two files disagreeing about which 2.0 is "real 2.0" -- exactly the
drift already found once between two copies of one metric.
"""

import json
import pathlib
import re
import subprocess

_VERIFY = (pathlib.Path(__file__).resolve().parent.parent / "experiments"
           / "sqlalchemy_1_4_vs_2_0" / "verify_2_0.py")


def _pin() -> str:
    """The 2.0 version this repo calls real, read out of the file that owns it.

    **Read, not imported, and that is not squeamishness.** `verify_2_0` runs a
    module-level `sys.exit()` when it finds itself on 1.4 -- which is always,
    here, because this project is pinned to 1.4.52 by design. Importing
    it from a 1.4 process kills the process, and `SystemExit` does not inherit
    from `Exception`, so a `try/except Exception` around the import would not
    even catch it. That trap is already written up in the project; this is the
    second module to meet it.

    One source of truth either way: `PIN` stays declared in `verify_2_0.py`,
    which is the file whose measured error strings depend on it. A test pins
    the two together so a version bump cannot leave them disagreeing -- the
    drift already found once when one metric had two implementations.
    """
    found = re.search(r'^PIN = "([^"]+)"', _VERIFY.read_text(), re.M)
    if not found:                              # a rename must fail loudly
        raise RuntimeError(f"no PIN declared in {_VERIFY}")
    return found.group(1)


PIN = _pin()

# Packages a symbol may name. Extra packages are NOT free -- each is a wheel
# resolved on every call -- so this list is short on purpose and grows only
# when a measured question needs it. `alembic` is here because `g065`'s
# fabrication was `op.create_view`, and that is the case this tool exists for.
PACKAGES = {
    "sqlalchemy": f"sqlalchemy=={PIN}",
    "alembic": "alembic",
}

TIMEOUT = 120

# Runs in the pinned interpreter, not this one. Kept as a string rather than a
# file so there is nothing to keep in sync; it reads one JSON argument and
# writes one JSON object, which is the whole contract.
_PROBE = r'''
import importlib, inspect, json, sys

req = json.loads(sys.argv[1])
symbol, want_source = req["symbol"], req["source"]

parts = symbol.split(".")
obj, resolved, err = None, [], None
# Walk the longest importable prefix, then getattr the rest. "Query.from_self"
# and "sqlalchemy.orm.Query.from_self" must behave the same, so a bare leading
# name is retried under the package root.
for start in range(len(parts), 0, -1):
    try:
        obj = importlib.import_module(".".join(parts[:start]))
        resolved = parts[start:]
        break
    except ImportError:
        continue
if obj is None:
    try:
        obj = importlib.import_module(req["package"])
        resolved = parts
    except ImportError as exc:
        print(json.dumps({"exists": False, "error": f"no module: {exc}"}))
        raise SystemExit

for name in resolved:
    obj = getattr(obj, name, None)
    if obj is None:
        # A miss is a RESULT, not an error. `check_api("Query.from_self")`
        # answering "no" is the tool working.
        print(json.dumps({"exists": False, "error": None}))
        raise SystemExit

out = {"exists": True, "error": None, "kind": type(obj).__name__}
try:
    out["signature"] = symbol.split(".")[-1] + str(inspect.signature(obj))
except (TypeError, ValueError):
    out["signature"] = None
doc = inspect.getdoc(obj) or ""
out["doc"] = doc.strip().splitlines()[0] if doc else None
if want_source:
    try:
        out["source"] = inspect.getsource(obj)
    except (TypeError, OSError) as exc:
        out["source"] = None
        out["error"] = f"source unavailable: {exc}"
print(json.dumps(out))
'''


def _run(symbol: str, package: str, source: bool, runner=None) -> dict:
    """One call into the pinned interpreter.

    `runner` is injectable so every test in this file's suite runs with no
    network, no wheel download and no subprocess -- the same reason
    `faithful.generate` takes its transport.
    """
    if package not in PACKAGES:
        return {"exists": False,
                "error": f"unknown package {package!r}; known: "
                         f"{', '.join(sorted(PACKAGES))}"}
    argument = json.dumps({"symbol": symbol, "source": source,
                           "package": package})
    command = ["uv", "run", "--no-project", "--with", PACKAGES[package],
               "python", "-c", _PROBE, argument]
    runner = runner or (lambda cmd: subprocess.run(
        cmd, capture_output=True, text=True, timeout=TIMEOUT))
    try:
        done = runner(command)
    except subprocess.TimeoutExpired:
        # The fourth module to need this rule: one unreachable
        # call costs one question, never the run.
        return {"exists": False, "error": f"timed out after {TIMEOUT}s"}
    if done.returncode != 0:
        return {"exists": False,
                "error": (done.stderr or "").strip().splitlines()[-1:] and
                         (done.stderr or "").strip().splitlines()[-1] or
                         "probe failed"}
    try:
        return json.loads(done.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"exists": False, "error": "probe produced no JSON"}


def check_api(symbol: str, package: str = "sqlalchemy", runner=None) -> dict:
    """Does `symbol` exist in the pinned version, and what is its signature?

    **`exists: False` is an answer, not a failure.** That distinction is the
    whole tool: `Query.from_self` returning "no" is the correct, useful reply,
    and collapsing it into an error would make the agent treat a removed API
    the same way it treats a broken lookup.
    """
    return _run(symbol, package, source=False, runner=runner)


def get_function_source(symbol: str, package: str = "sqlalchemy",
                        runner=None) -> dict:
    """The real source of a callable in the pinned version.

    Separate from `check_api` rather than a flag on it, because the answers
    differ in size by three orders of magnitude and an agent that wanted a
    yes/no should not be handed 400 lines to reason about.
    """
    return _run(symbol, package, source=True, runner=runner)


def search_docs(query: str, k: int = 5, retrieve=None) -> list[dict]:
    """The corpus, through the graded retrieval path.

    Calls `index.retrieve`, which is hybrid + dedupe + seat-5 rerank
    **Not a private retriever.** A second one would drift from
    the one Phase 2 measured, and every recall figure in this repo would
    quietly stop describing what the agent actually sees -- the same defect
    found once when one metric had two implementations.
    """
    if retrieve is None:                      # imported late: needs Qdrant up
        from rag import index
        retrieve = index.retrieve
    return [{"chunk_id": hit.payload.get("chunk_id", "?"),
             "source": hit.payload.get("source"),
             "text": hit.payload["text"]}
            for hit in retrieve(query, limit=k)]


# The two calls that make `g065` a measurement rather than an anecdote. Prompt
# D answered an unanswerable question with an Alembic script in which
# `op.create_table` is real and `op.create_view` does not exist -- two invented
# calls sitting next to two working ones. A count of fabrications
# cannot see that; this can, and an agent can call it before it writes.
G065 = [("alembic.operations.Operations.create_table", "alembic", True),
        ("alembic.operations.Operations.create_view", "alembic", False)]


def main() -> None:
    import sys
    argv = sys.argv[1:]
    package = argv[argv.index("--package") + 1] if "--package" in argv \
        else "sqlalchemy"

    if "--g065" in argv:
        print(f"g065 — the fabricated Alembic script, checked against real "
              f"alembic")
        ok = True
        for symbol, pkg, expected in G065:
            got = check_api(symbol, package=pkg)
            mark = "OK " if got["exists"] == expected else "!! "
            ok &= got["exists"] == expected
            print(f"  {mark}{symbol:<48} exists={str(got['exists']):<5} "
                  f"(expected {expected})")
        print("  Two invented calls beside two working ones — and the tool "
              "separates them.")
        raise SystemExit(0 if ok else 1)

    if "--source" in argv:
        got = get_function_source(argv[argv.index("--source") + 1],
                                  package=package)
        print(got.get("source") or f"no source: {got.get('error')}")
        return

    if "--check" in argv:
        symbol = argv[argv.index("--check") + 1]
        got = check_api(symbol, package=package)
        print(f"{symbol}  (in {package} {PIN if package == 'sqlalchemy' else ''})")
        print(f"  exists     {got['exists']}")
        print(f"  signature  {got.get('signature')}")
        if got.get("doc"):
            print(f"  doc        {got['doc']}")
        if got.get("error"):
            print(f"  error      {got['error']}")
        return

    print("usage: python -m rag.tools --check SYMBOL [--package alembic]\n"
          "                           --source SYMBOL\n"
          "                           --g065")


if __name__ == "__main__":
    main()
