"""Phase 4 — the faithfulness judge's plumbing.

Every test here runs with no key and no network: `generate()` takes its
transport as an argument for exactly that reason. A test suite that needed a
credential would be skipped in CI and would therefore pin nothing.
"""

import urllib.error

import pytest

from rag import faithful


def fake_post(reply: str):
    """A transport that returns one canned answer in the API's shape."""
    def post(path, body, key, timeout=120):
        return {"candidates": [{"content": {"parts": [{"text": reply}]}}]}
    return post


# --- the key ----------------------------------------------------------------

def test_the_environment_wins_over_the_env_file(monkeypatch, tmp_path):
    """An exported key is the one the shell meant to use."""
    monkeypatch.setenv(faithful.KEY_VAR, "from-env")
    monkeypatch.setattr(faithful, "ENV_FILE", tmp_path / ".env")
    (tmp_path / ".env").write_text(f"{faithful.KEY_VAR}=from-file\n")
    assert faithful.api_key() == "from-env"


def test_the_env_file_is_read_when_nothing_is_exported(monkeypatch, tmp_path):
    """Nothing in this repo loads .env for host scripts -- Compose reads it for
    containers and seed.py uses a plain os.getenv. Without this fallback the
    tool reports 'no key' to someone looking straight at the line in the file."""
    monkeypatch.delenv(faithful.KEY_VAR, raising=False)
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql://x\n"
                   f"{faithful.KEY_VAR}=from-file\n")
    monkeypatch.setattr(faithful, "ENV_FILE", env)
    assert faithful.api_key() == "from-file"


def test_a_quoted_key_is_unquoted(monkeypatch, tmp_path):
    """KEY="abc" is the common paste shape, and sending the quotes produces a
    400 that reads exactly like a bad key."""
    monkeypatch.delenv(faithful.KEY_VAR, raising=False)
    env = tmp_path / ".env"
    env.write_text(f'{faithful.KEY_VAR}="abc123"\n')
    monkeypatch.setattr(faithful, "ENV_FILE", env)
    assert faithful.api_key() == "abc123"


def test_a_missing_env_file_is_not_an_error(monkeypatch, tmp_path):
    monkeypatch.delenv(faithful.KEY_VAR, raising=False)
    monkeypatch.setattr(faithful, "ENV_FILE", tmp_path / "absent")
    assert faithful.api_key() is None


def test_a_commented_out_key_is_not_read(monkeypatch, tmp_path):
    monkeypatch.delenv(faithful.KEY_VAR, raising=False)
    env = tmp_path / ".env"
    env.write_text(f"# {faithful.KEY_VAR}=old-revoked-key\n")
    monkeypatch.setattr(faithful, "ENV_FILE", env)
    assert faithful.api_key() is None


# --- the verdict ------------------------------------------------------------

def test_the_three_verdicts_parse():
    for word in faithful.VERDICTS:
        verdict, reason = faithful.parse_verdict(f"{word}\nPassage [2] says so.")
        assert verdict == word and reason == "Passage [2] says so."


def test_a_verdict_the_judge_did_not_follow_the_format_for_is_UNPARSED():
    """Coercing it to UNSUPPORTED would move the number in the flattering
    direction -- the failure ask.refused() had before D76 made it a prefix
    test. A judge that stopped following the format is a fact about the run."""
    verdict, reason = faithful.parse_verdict("Well, it depends on what you mean.")
    assert verdict == "UNPARSED"
    assert reason == "Well, it depends on what you mean."


def test_markdown_decoration_around_the_verdict_still_parses():
    """Models emit **SUPPORTED** and `SUPPORTED:` freely. Refusing those would
    report UNPARSED for a judge that answered correctly."""
    assert faithful.parse_verdict("**SUPPORTED**\nbecause")[0] == "SUPPORTED"
    assert faithful.parse_verdict("SUPPORTED: because")[0] == "SUPPORTED"


def test_an_empty_reply_is_UNPARSED_not_a_crash():
    assert faithful.parse_verdict("")[0] == "UNPARSED"


# --- the call ---------------------------------------------------------------

def test_judge_claim_numbers_the_passages():
    """The judge is asked which passage decided it, so the passages have to
    carry the same [n] labels the answer's citations use."""
    seen = {}

    def post(path, body, key, timeout=120):
        seen["prompt"] = body["contents"][0]["parts"][0]["text"]
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED\nx"}]}}]}

    faithful.judge_claim("a claim", ["first page", "second page"],
                         key="k", post=post)
    assert "[1] first page" in seen["prompt"]
    assert "[2] second page" in seen["prompt"]


def test_the_judge_runs_at_temperature_zero():
    """Same reason ask.py pins it: a judge that answers differently on re-read
    cannot be compared with itself."""
    seen = {}

    def post(path, body, key, timeout=120):
        seen["cfg"] = body["generationConfig"]
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED"}]}}]}

    faithful.generate("x", key="k", post=post)
    assert seen["cfg"]["temperature"] == 0.0


def test_every_row_carries_the_model_that_produced_it():
    """Not that the model never changes -- that a row never loses track of
    which model read it. This is the property that actually matters."""
    row = faithful.judge_claim("c", ["p"], key="k", model="pinned-x",
                               post=fake_post("UNSUPPORTED\nno passage"))
    assert row["judge_model"] == "pinned-x"
    assert row["verdict"] == "UNSUPPORTED"


def test_the_pinned_model_is_the_one_called():
    seen = {}

    def post(path, body, key, timeout=120):
        seen["path"] = path
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED"}]}}]}

    faithful.generate("x", key="k", model="gemini-9.9-flash-001", post=post)
    assert seen["path"] == "models/gemini-9.9-flash-001:generateContent"


# --- --check ----------------------------------------------------------------

def test_check_makes_exactly_one_call():
    """Finding out the key is wrong must cost one call, not a hundred."""
    calls = []

    def post(path, body, key, timeout=120):
        calls.append(path)
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED"}]}}]}

    ok, _ = faithful.check("k", post=post)
    assert ok and len(calls) == 1


def test_check_reports_an_http_error_instead_of_raising():
    """A 400 from a mistyped key and a 404 from a stale model id are the two
    likely outcomes, and both should print a diagnosis rather than a
    traceback."""
    def post(path, body, key, timeout=120):
        raise urllib.error.HTTPError(
            "url", 404, "Not Found", {}, __import__("io").BytesIO(b"no such model")
        )

    ok, message = faithful.check("k", post=post)
    assert not ok and "404" in message and "no such model" in message


def test_check_reports_an_unreachable_host_instead_of_raising():
    def post(path, body, key, timeout=120):
        raise urllib.error.URLError("offline")

    ok, message = faithful.check("k", post=post)
    assert not ok and "cannot reach" in message
