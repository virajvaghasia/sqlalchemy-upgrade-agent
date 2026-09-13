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
    return {"choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": p, "completion_tokens": o}}


def test_the_prompt_is_the_shipped_one_byte_for_byte():
    """If the strong model got a different prompt, the comparison would be about
    the prompt, not the model."""
    body = escalate.request_body("q?", [hit()])
    assert body["messages"][0] == {"role": "system", "content": ask.SYSTEM}
    assert body["messages"][1] == {"role": "user", "content": ask.build_prompt("q?", [hit()])}
    assert body["temperature"] == ask.TEMPERATURE


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


def test_nvidia_verdicts_are_the_scored_ones_once_they_exist(capsys):
    """PHASE-6.md Step 3b: gemma is a Google model grading a Google model, so the
    non-Google judge's verdicts decide the rule and gemma's only measure agreement."""
    rows = [{"id": "g1", "refused": False, "verdict": "SUPPORTED", "verdict_nvidia": "PARTIAL",
             "prompt_tokens": 1, "output_tokens": 1},
            {"id": "g2", "refused": False, "verdict": "SUPPORTED", "verdict_nvidia": "SUPPORTED",
             "prompt_tokens": 1, "output_tokens": 1}]
    s = escalate.summarise(rows, expected=2)
    assert s["supported"] == ["g2"] and (s["agree"], s["both"]) == (1, 2)


def test_nvidia_transport_speaks_openai_and_returns_gemini_shape(monkeypatch):
    import json as _json
    from rag import faithful
    seen = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _json.dumps({"choices": [{"message": {"content": "SUPPORTED\nok"}}]}).encode()

    def fake_urlopen(req, timeout):
        seen["body"] = _json.loads(req.data); seen["auth"] = req.headers["Authorization"]
        return Resp()

    monkeypatch.setattr(faithful.urllib.request, "urlopen", fake_urlopen)
    out = faithful.nvidia_post("models/mistralai/mistral-large-2-instruct:generateContent",
                               {"contents": [{"parts": [{"text": "p"}]}]}, "k")
    assert seen["body"]["model"] == "mistralai/mistral-large-2-instruct"
    assert seen["body"]["temperature"] == 0.0 and seen["auth"] == "Bearer k"
    assert out["candidates"][0]["content"]["parts"][0]["text"].startswith("SUPPORTED")


def test_an_empty_answer_is_neither_answered_nor_refused():
    """A reasoning model that spends its budget thinking returns no text. Scoring
    that as an answer would inflate `answered`; as a refusal, `refused`."""
    post = lambda path, body, key: reply("")
    rows = escalate.generate_rows([{"id": "g1", "question": "q"}], key="k", post=post,
                                  retrieve=lambda q: [hit()], log=lambda *a: None, sleep=lambda s: None)
    s = escalate.summarise(rows, expected=1)
    assert rows[0]["empty"] and not rows[0]["refused"]
    assert s["answered"] == [] and s["refused"] == [] and s["empty"] == ["g1"]


def test_the_two_escalation_sets_are_disjoint_and_together_are_every_refusal():
    """A cascade escalates every refusal (D98: 53). 3b took the 20 it can fix;
    3c takes the rest. Overlap would double-count, a gap would hide a cost."""
    present, rest = escalate.escalation_ids("present"), escalate.escalation_ids("rest")
    assert not set(present) & set(rest)
    assert (len(present), len(rest)) == (20, 33)


def test_shadow_cost_multiplies_counted_tokens_by_the_snapshot_price():
    prices = {"models": {escalate.MODEL: {"pricing": {"prompt": "0.000001", "completion": "0.000002"}}}}
    rows = [{"prompt_tokens": 1000, "output_tokens": 500}, {"prompt_tokens": None, "output_tokens": 10}]
    assert abs(escalate.shadow_cost(rows, prices) - (0.001 + 0.001 + 0.00002)) < 1e-12


def test_the_rest_report_uses_its_own_rules_not_3bs(capsys):
    """The first 3c report printed 3b's 'answered >= 15 -> MIXED' over a set
    that rule was never written for."""
    golden = {"u1": {"answerable": False}, "u2": {"answerable": False}, "a1": {"answerable": True}}
    rows = [{"id": "u1", "refused": False, "prompt_tokens": 1, "output_tokens": 1, "answer": "x"},
            {"id": "u2", "refused": True, "prompt_tokens": 1, "output_tokens": 1, "answer": "x"},
            {"id": "a1", "refused": False, "verdict_nvidia": "PARTIAL", "prompt_tokens": 1,
             "output_tokens": 1, "answer": "x"}]
    r = escalate.report_rest(rows, golden, None)
    out = capsys.readouterr().out
    assert r["fabricated"] == ["u1"] and "rule >= 15" not in out
    assert "refusals stay honest" in out  # 1 of 2 is under the bar of 2
