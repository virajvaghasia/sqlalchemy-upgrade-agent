"""Phase 5 Step 1 — the three tools.

**Every test here runs with no subprocess, no wheel download and no Qdrant.**
`_run` and `search_docs` take their runner/retriever as arguments for the same
reason `faithful.generate` takes its transport: a suite that needed the network
would be skipped in CI and would therefore pin nothing.

The one thing that genuinely needs the pinned interpreter -- the `g065`
reproduction -- is a documented command, not a test.
"""

import json
import subprocess
import types

from rag import tools


def runner(stdout="", returncode=0, stderr=""):
    def run(cmd):
        run.cmd = cmd
        return types.SimpleNamespace(stdout=stdout, returncode=returncode,
                                     stderr=stderr)
    return run


# --- the pin -----------------------------------------------------------------

def test_the_pin_is_the_one_verify_2_0_declares():
    """One source of truth. `verify_2_0.py` owns `PIN` because its recorded
    error strings depend on it; this module reads that file rather than
    keeping a second copy, which is the drift `D85` found elsewhere."""
    declared = tools._VERIFY.read_text()
    assert f'PIN = "{tools.PIN}"' in declared


def test_the_pin_is_read_not_imported():
    """`verify_2_0` calls `sys.exit()` at module level when it finds itself on
    1.4 -- which is always, in this project (`D04`). Importing it from here
    would kill the process, and `SystemExit` does not inherit from `Exception`
    so a guard around the import would not catch it."""
    assert "import" not in tools._pin.__doc__.split("**Read, not imported")[0][-40:]
    assert tools.PIN.startswith("2.")


# --- check_api ---------------------------------------------------------------

def test_a_missing_symbol_is_an_answer_not_an_error():
    """`check_api("Query.from_self")` answering "no" IS the tool working.
    Collapsing that into an error would make an agent treat a removed API the
    same way it treats a broken lookup, which is the distinction the tool
    exists to draw."""
    got = tools.check_api("sqlalchemy.orm.Query.from_self",
                          runner=runner(json.dumps({"exists": False,
                                                    "error": None})))
    assert got["exists"] is False and got["error"] is None


def test_a_present_symbol_comes_back_with_its_signature():
    got = tools.check_api("sqlalchemy.orm.Session.get", runner=runner(
        json.dumps({"exists": True, "error": None,
                    "signature": "get(self, entity, ident)"})))
    assert got["exists"] and got["signature"].startswith("get(")


def test_an_unknown_package_is_refused_before_any_subprocess():
    """Each package is a wheel resolved on every call, so the list is short on
    purpose. A typo must fail here rather than spend two minutes proving it."""
    called = []
    got = tools.check_api("x", package="requests",
                          runner=lambda cmd: called.append(cmd))
    assert got["exists"] is False and "unknown package" in got["error"]
    assert called == [], "no subprocess for an unknown package"


def test_a_timeout_costs_one_call_not_the_run():
    """D75, and this is the fourth module to inherit it. The first two learned
    it the expensive way."""
    def boom(cmd):
        raise subprocess.TimeoutExpired(cmd, tools.TIMEOUT)

    got = tools.check_api("anything", runner=boom)
    assert got["exists"] is False and "timed out" in got["error"]


def test_a_probe_that_prints_nothing_is_reported_rather_than_crashing():
    got = tools.check_api("x", runner=runner(stdout="   "))
    assert got["exists"] is False and "no JSON" in got["error"]


def test_a_failed_subprocess_surfaces_its_last_stderr_line():
    got = tools.check_api("x", runner=runner(
        returncode=1, stderr="Resolution failed\nNo solution found"))
    assert got["exists"] is False and got["error"] == "No solution found"


def test_the_pinned_version_is_in_the_command():
    """The whole reason for the subprocess: this process is on 1.4.52 and the
    question is about 2.0."""
    run = runner(json.dumps({"exists": True, "error": None}))
    tools.check_api("sqlalchemy.orm.Session.get", runner=run)
    assert f"sqlalchemy=={tools.PIN}" in run.cmd
    assert "--no-project" in run.cmd


def test_alembic_is_reachable_because_g065_needs_it():
    """`g065`'s fabrication was `op.create_view`, not a SQLAlchemy symbol. A
    tool that could only see SQLAlchemy could not have caught it."""
    run = runner(json.dumps({"exists": False, "error": None}))
    tools.check_api("alembic.operations.Operations.create_view",
                    package="alembic", runner=run)
    assert "alembic" in run.cmd


def test_the_g065_expectations_are_the_measured_ones():
    """`D77` measured `create_table` real and `create_view` absent on the same
    script. If this table is ever edited to agree with a future alembic, the
    edit is deliberate and visible."""
    assert dict((s, e) for s, _, e in tools.G065) == {
        "alembic.operations.Operations.create_table": True,
        "alembic.operations.Operations.create_view": False,
    }


# --- get_function_source -----------------------------------------------------

def test_source_is_a_separate_tool_not_a_flag():
    """The answers differ in size by three orders of magnitude. An agent that
    wanted yes/no should not be handed 400 lines to reason about."""
    run = runner(json.dumps({"exists": True, "error": None, "source": "def f(): ..."}))
    got = tools.get_function_source("sqlalchemy.orm.Session.get", runner=run)
    assert got["source"] == "def f(): ..."
    assert json.loads(run.cmd[-1])["source"] is True

    run2 = runner(json.dumps({"exists": True, "error": None}))
    tools.check_api("sqlalchemy.orm.Session.get", runner=run2)
    assert json.loads(run2.cmd[-1])["source"] is False


# --- search_docs -------------------------------------------------------------

def test_search_docs_uses_the_graded_retrieval_path():
    """NOT a private retriever. A second one would drift from the path Phase 2
    measured, and every recall figure here would quietly stop describing what
    the agent sees -- the defect `D85` found when one metric had two
    implementations."""
    seen = {}

    def retrieve(query, limit=5):
        seen["query"], seen["limit"] = query, limit
        return [types.SimpleNamespace(payload={"chunk_id": "c01567",
                                               "source": "migration_20.rst",
                                               "text": "body"})]

    got = tools.search_docs("from_self", k=3, retrieve=retrieve)
    assert seen == {"query": "from_self", "limit": 3}
    assert got == [{"chunk_id": "c01567", "source": "migration_20.rst",
                    "text": "body"}]
