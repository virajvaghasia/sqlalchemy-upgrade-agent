"""Phase 6 Step 3b — escalation to a stronger model. No network, no key."""
import io
import types
import urllib.error

from rag import ask, escalate


def hit(cid="c1"):
    return types.SimpleNamespace(payload={
        "chunk_id": cid, "text": "body", "heading_path": ["Migration"],
        "sqlalchemy_version": "2.0.51", "source_path": "migration_20.rst"})


def reply(text, p=100, o=20):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": p, "candidatesTokenCount": o}}


def test_the_prompt_is_the_shipped_one_byte_for_byte():
    """If the strong model got a different prompt, the comparison would be about
    the prompt, not the model."""
    body = escalate.request_body("q?", [hit()])
    assert body["systemInstruction"]["parts"][0]["text"] == ask.SYSTEM
    assert body["contents"][0]["parts"][0]["text"] == ask.build_prompt("q?", [hit()])
    assert body["generationConfig"]["temperature"] == ask.TEMPERATURE


def test_tokens_are_the_api_counts_not_an_estimate():
    row = escalate.parse(reply("an answer [1]", p=1234, o=56))
    assert (row["prompt_tokens"], row["output_tokens"]) == (1234, 56)


def test_a_quota_error_stops_the_run_and_keeps_the_rows_so_far():
    calls = []

    def post(path, body, key):
        calls.append(1)
        if len(calls) == 2:
            raise urllib.error.HTTPError("u", 429, "quota", {}, io.BytesIO(b"PerDay"))
        return reply(ask.REFUSAL_OPENING + " this.")

    items = [{"id": f"g{n}", "question": "q"} for n in range(3)]
    rows = escalate.generate_rows(items, key="k", post=post, retrieve=lambda q: [hit()],
                                  log=lambda *a: None, sleep=lambda s: None)
    assert [r["id"] for r in rows] == ["g0"] and rows[0]["refused"]


def test_a_short_run_reports_itself_incomplete_and_is_never_scaled(capsys):
    rows = [{"id": "g1", "refused": False, "verdict": "SUPPORTED",
             "prompt_tokens": 10, "output_tokens": 2}]
    escalate.report(escalate.summarise(rows, expected=20))
    out = capsys.readouterr().out
    assert "INCOMPLETE — 1 of 20" in out and "answered    1 of 1" in out
    assert "PASS" not in out and "FAIL" not in out, "no verdict on 1 of 20"


def test_resume_does_not_ask_a_saved_question_again():
    asked = []
    post = lambda path, body, key: asked.append(1) or reply("an answer [1]")
    done = [{"id": "g0", "refused": False}]
    rows = escalate.generate_rows([{"id": "g0", "question": "q"}, {"id": "g1", "question": "q"}],
                                  key="k", post=post, retrieve=lambda q: [hit()],
                                  log=lambda *a: None, sleep=lambda s: None, done=done)
    assert len(asked) == 1 and [r["id"] for r in rows] == ["g0", "g1"]
