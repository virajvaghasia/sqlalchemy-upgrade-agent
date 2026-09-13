"""Phase 6 Step 4 — the public demo's logic. No network, no model, no Gradio."""
import types
import urllib.error

from rag import ask, demo


def hit(cid="c1"):
    return types.SimpleNamespace(score=1.0, payload={
        "chunk_id": cid, "text": "body text", "heading_path": ["Migration"],
        "sqlalchemy_version": "2.0.51", "source_path": "changelog/migration_20.rst"})


def reply(text):
    return {"choices": [{"message": {"content": text}}]}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_the_demo_sends_the_shipped_prompt_not_a_rewrite():
    """The page claims to run the shipped prompt; this is what makes that true."""
    seen = {}
    demo.answer("how do I migrate?", key="k", session="s", limiter=demo.RateLimiter(),
                retrieve=lambda q: [hit()], post=lambda m, k: seen.setdefault("m", m) and reply("x [1]"))
    assert seen["m"][0] == {"role": "system", "content": ask.SYSTEM}
    assert seen["m"][1]["content"] == ask.build_prompt("how do I migrate?", [hit()])


def test_a_missing_key_is_an_error_on_the_page_not_a_crash():
    out = demo.answer("q", key=None, session="s", limiter=demo.RateLimiter(),
                      retrieve=lambda q: [hit()], post=lambda m, k: reply("x"))
    assert "NVIDIA_API_KEY" in out["error"]


def test_rate_limit_per_session_and_per_hour():
    clock = Clock()
    lim = demo.RateLimiter(per_hour=2, gap=20, clock=clock)
    assert lim.check("a") is None
    assert "wait" in lim.check("a")                 # same session too soon
    assert lim.check("b") is None                   # another visitor is fine
    clock.t = 30
    assert "hourly" in lim.check("a")               # global cap of 2 reached
    clock.t = 3700
    assert lim.check("a") is None                   # the hour rolled over


def test_a_rate_limited_visitor_still_sees_the_sources():
    """Retrieval costs nothing; only generation spends credits."""
    lim = demo.RateLimiter(per_hour=0)
    out = demo.answer("q", key="k", session="s", limiter=lim,
                      retrieve=lambda q: [hit()], post=lambda m, k: reply("x"))
    assert "hourly" in out["error"] and out["sources"][0]["path"] == "changelog/migration_20.rst"


def test_a_remote_failure_keeps_the_sources_and_does_not_raise():
    def boom(m, k):
        raise urllib.error.URLError("down")
    out = demo.answer("q", key="k", session="s", limiter=demo.RateLimiter(),
                      retrieve=lambda q: [hit()], post=boom)
    assert out["error"] and out["sources"]


def test_overlong_and_empty_questions_are_refused_before_any_work():
    calls = []
    for q in ("", "x" * (demo.MAX_QUESTION_CHARS + 1)):
        out = demo.answer(q, key="k", session="s", limiter=demo.RateLimiter(),
                          retrieve=lambda q: calls.append(q) or [hit()], post=lambda m, k: reply("x"))
        assert out["error"]
    assert calls == []


def test_the_hosted_page_quotes_its_own_models_numbers_and_names_whose_the_042_is():
    """D95/D104: a number quoted next to a model that did not produce it is the
    error this project exists to avoid. The hosted notice gives nemotron's own
    measured numbers and still says the 0.42 belongs to qwen2.5-coder:7b."""
    page = demo.render({"answer": "a [1]", "sources": [], "error": None})
    assert demo.MODEL in page and "qwen2.5-coder:7b" in page and "0.42" in page
    assert "measured once" in page


def test_the_hosted_notices_numbers_are_derived_from_the_saved_rows():
    """The measurement rule: 0.58 and 77% in the notice must be what Step 4d's
    rows compute, not literals typed once (D104)."""
    import json
    import pytest
    from rag import escalate, route, score
    if not score.CHUNKS_PATH.exists():
        pytest.skip("corpus/chunks.jsonl is generated and gitignored (D11)")
    golden = {i["id"]: i for i in score.load_golden()}
    rows = json.loads(escalate.ROWS_ALL.read_text())["rows"]
    outs = [r for r in escalate.outcome_rows(rows, golden, score.load_chunks()) if r["answerable"]]
    e2e = sum(route.delivered(r) for r in outs) / len(outs)
    answered = [r for r in rows if not r.get("empty") and not ask.refused(r["answer"])]
    # Step 4g: the primary faithfulness figure is the judge given the block the model saw.
    share = sum(r.get("verdict_nvidia_h") == "SUPPORTED" for r in answered) / len(answered)
    assert f"{e2e:.2f} end to end" in demo.NOT_THE_MEASURED_MODEL
    assert f"{share:.0%} of its answers" in demo.NOT_THE_MEASURED_MODEL


def test_the_local_backend_needs_no_key_and_names_the_measured_model():
    """Run locally, the demo uses qwen2.5-coder:7b -- the generator the 0.42 was
    measured on -- and the page says that instead of the hosted disclaimer."""
    out = demo.answer("q", key=None, session="s", limiter=demo.RateLimiter(), backend="ollama",
                      retrieve=lambda q: [hit()], post=lambda m, k: reply("an answer [1]"))
    assert out["error"] is None and out["answer"] == "an answer [1]"
    page = demo.render(out, "ollama")
    assert "the generator the project measured" in page and "a different model" not in page


def test_ollama_down_is_a_page_error_not_a_dead_server():
    """ask.generate calls sys.exit when Ollama is unreachable; SystemExit is not an
    Exception, so a plain except would let it kill the web server."""
    def down(m, k):
        raise SystemExit("cannot reach Ollama")
    out = demo.answer("q", key=None, session="s", limiter=demo.RateLimiter(), backend="ollama",
                      retrieve=lambda q: [hit()], post=down)
    assert "Ollama" in out["error"] and out["sources"]


def test_status_separates_answered_declined_and_error():
    assert demo.status({"answer": "a [1]", "refused": False, "error": None}) == "answered"
    assert demo.status({"answer": ask.REFUSAL_OPENING + " this.", "refused": True, "error": None}) == "declined"
    assert demo.status({"error": "no key"}) == "error"


def test_source_cards_escape_markup_from_the_docs():
    """SQLAlchemy's pages contain literal <...>; unescaped, they become markup."""
    page = demo.render_sources({"sources": [{"n": 1, "version": "2.0.51", "path": "a.rst",
                                             "heading": "H <b>", "text": "<script>x</script> <User id=1>"}]})
    assert "<script>" not in page and "&lt;script&gt;" in page and "&lt;User id=1&gt;" in page


def test_the_answer_panel_keeps_the_generator_notice():
    """The split page must not drop the sentence D102 requires."""
    assert "a different model" in demo.render_answer({"answer": "a", "refused": False, "error": None})
    assert "the generator the project measured" in demo.render_answer(
        {"answer": "a", "refused": False, "error": None}, "ollama")


def test_sphinx_roles_become_readable_names():
    assert demo.readable("use :meth:`_orm.Query.get` or :class:`~sqlalchemy.engine.Row`") == \
        "use `Query.get` or `Row`"
    assert demo.readable(":ref:`the guide <migration_20>`") == "`the guide`"


def test_citations_link_to_cards_but_never_inside_code_or_out_of_range():
    answer = "Use it [2].\n```python\nrow[1]\nx = [1]\n```\nSee `a[1]` and [9]."
    out = demo.link_citations(answer, n_sources=5)
    assert "[[2]](#src-2)" in out
    assert "row[1]" in out and "x = [1]" in out and "`a[1]`" in out   # code untouched
    assert "[9]" in out and "#src-9" not in out                        # no card 9


def test_cards_are_anchored_and_mark_what_the_answer_cited():
    result = {"answer": "It is [2].", "sources": [
        {"n": n, "version": "2.0.51", "path": "p.rst", "heading": "H", "text": ":meth:`_orm.Query.get`"}
        for n in (1, 2)]}
    page = demo.render_sources(result)
    assert 'id="src-1"' in page and 'id="src-2"' in page
    assert page.count(">cited<") == 1 and page.index(">cited<") > page.index('id="src-2"')
    assert "Query.get" in page and ":meth:" not in page


def test_a_role_and_a_citation_in_one_sentence_both_render():
    """The bug seen in the browser: the role's backticks were taken for inline
    code, so ':meth:' stayed on the page. The earlier tests never combined them."""
    out = demo.link_citations("The :meth:`_orm.Query.get` method moves to :meth:`_orm.Session.get` [1].", 5)
    assert out == "The `Query.get` method moves to `Session.get` [[1]](#src-1)."
    assert ":meth:" not in out


def test_payload_carries_linked_answer_marked_sources_and_the_notice():
    """The custom page reads only this; it must never have to re-derive a rule."""
    result = {"answer": "Use :meth:`_orm.Session.get` [2].", "refused": False, "error": None,
              "sources": [{"n": n, "version": "2.0.51", "path": "p.rst", "heading": "H",
                           "text": ":class:`~sqlalchemy.engine.Row`"} for n in (1, 2)]}
    p = demo.payload(result, "ollama", 12.34)
    assert p["status"] == "answered" and p["answer_md"] == "Use `Session.get` [[2]](#src-2)."
    assert [s["cited"] for s in p["sources"]] == [False, True] and p["sources"][0]["text"] == "Row"
    assert "the generator the project measured" in p["notice"] and p["seconds"] == 12.3
    assert "a different model" in demo.payload(result, "nvidia", 1)["notice"]
