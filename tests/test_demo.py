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


def test_the_page_always_says_the_measured_score_is_not_this_model():
    """D95/D99: a number quoted next to a model that did not produce it is the
    error this project exists to avoid."""
    page = demo.render({"answer": "a [1]", "sources": [], "error": None})
    assert "qwen2.5-coder:7b" in page and "does not describe these answers" in page


def test_the_local_backend_needs_no_key_and_names_the_measured_model():
    """Run locally, the demo uses qwen2.5-coder:7b -- the generator the 0.42 was
    measured on -- and the page says that instead of the hosted disclaimer."""
    out = demo.answer("q", key=None, session="s", limiter=demo.RateLimiter(), backend="ollama",
                      retrieve=lambda q: [hit()], post=lambda m, k: reply("an answer [1]"))
    assert out["error"] is None and out["answer"] == "an answer [1]"
    page = demo.render(out, "ollama")
    assert "the generator the project measured" in page and "does not describe" not in page


def test_ollama_down_is_a_page_error_not_a_dead_server():
    """ask.generate calls sys.exit when Ollama is unreachable; SystemExit is not an
    Exception, so a plain except would let it kill the web server."""
    def down(m, k):
        raise SystemExit("cannot reach Ollama")
    out = demo.answer("q", key=None, session="s", limiter=demo.RateLimiter(), backend="ollama",
                      retrieve=lambda q: [hit()], post=down)
    assert "Ollama" in out["error"] and out["sources"]
