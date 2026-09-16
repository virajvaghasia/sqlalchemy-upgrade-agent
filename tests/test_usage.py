"""
Pin the token ledger. No network here.

The ledger exists because NVIDIA's free tier shows no balance and sends no
rate-limit headers (measured 2026-09-16), so the `usage` block of each reply is
the only evidence there is. These tests pin the two things that would make it
useless: dropping failures, and dying on a bad write.
"""

import json

from rag import usage


def test_a_successful_call_is_recorded_with_its_three_counts(tmp_path):
    led = tmp_path / "u.jsonl"
    usage.record("m/x", {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                 "test", path=led)
    row = json.loads(led.read_text().strip())
    assert (row["model"], row["caller"], row["status"]) == ("m/x", "test", 200)
    assert (row["prompt_tokens"], row["completion_tokens"], row["total_tokens"]) == (10, 4, 14)
    assert row["ts"].endswith("+00:00"), "UTC, so two machines' rows can be read together"


def test_failures_are_recorded_too(tmp_path):
    """A 429 in this file is the ONLY place 'the rate limit was reached' appears:
    there are no rate-limit headers. A success-only ledger shows silence instead."""
    led = tmp_path / "u.jsonl"
    usage.record("m/x", None, "test", status=429, path=led)
    usage.record("m/x", None, "test", status=404, path=led)
    out = usage.report(usage.load(led))
    assert "failed 2" in out
    assert "429x1" in out and "404x1" in out
    assert "rate limit was reached" in out
    assert "entitlement, not an outage" in out


def test_a_failed_call_contributes_no_tokens(tmp_path):
    led = tmp_path / "u.jsonl"
    usage.record("m/x", {"total_tokens": 99}, "test", status=500, path=led)
    usage.record("m/x", {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                 "test", path=led)
    out = usage.report(usage.load(led))
    assert "total 3" in out, "a 500's tokens must not be counted as spend"


def test_totals_group_by_model_and_by_day(tmp_path):
    led = tmp_path / "u.jsonl"
    for model in ("a/1", "a/1", "b/2"):
        usage.record(model, {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
                     "test", path=led)
    out = usage.report(usage.load(led))
    assert "calls 3   ok 3   failed 0" in out
    assert "a/1" in out and "b/2" in out
    assert "total 30" in out


def test_an_unwritable_ledger_never_breaks_the_run(tmp_path):
    """Modal containers are read-only in places. Losing a ledger line is a
    smaller failure than losing the answer the user asked for."""
    bad = tmp_path / "nope" / "u.jsonl"
    bad.parent.write_text("i am a file, not a directory")
    usage.record("m/x", {"total_tokens": 1}, "test", path=bad)  # must not raise


def test_an_empty_ledger_says_so_rather_than_printing_zeros():
    out = usage.report([])
    assert "empty" in out and "no hosted calls recorded" in out


def test_missing_usage_block_is_zero_not_a_crash(tmp_path):
    led = tmp_path / "u.jsonl"
    usage.record("m/x", None, "test", path=led)
    assert json.loads(led.read_text().strip())["total_tokens"] == 0


def test_the_demo_records_every_hosted_call(monkeypatch, tmp_path):
    """Wiring check: the ledger is only useful if the call sites use it."""
    import io, json as _json, urllib.error
    from rag import demo

    led = tmp_path / "u.jsonl"
    monkeypatch.setattr(usage, "LEDGER", led)
    body = _json.dumps({"choices": [{"message": {"content": "hi"}}],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}})
    monkeypatch.setattr(demo.urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(body.encode()))
    demo.nvidia_post([{"role": "user", "content": "q"}], "key")
    rows = usage.load(led)
    assert len(rows) == 1 and rows[0]["total_tokens"] == 10
    assert rows[0]["model"] == demo.MODEL and rows[0]["caller"] == "demo.nvidia_post"


def test_the_demo_records_a_refused_call(monkeypatch, tmp_path):
    import urllib.error
    from rag import demo

    led = tmp_path / "u.jsonl"
    monkeypatch.setattr(usage, "LEDGER", led)

    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    monkeypatch.setattr(demo.urllib.request, "urlopen", boom)
    try:
        demo.nvidia_post([{"role": "user", "content": "q"}], "key")
    except urllib.error.HTTPError:
        pass
    rows = usage.load(led)
    assert rows and rows[0]["status"] == 404, "the 404 that took the demo down must be on record"
