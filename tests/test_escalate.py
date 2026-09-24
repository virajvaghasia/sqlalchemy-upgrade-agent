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
    """Phase 6 Step 3b: gemma is a Google model grading a Google model, so the
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
    """A cascade escalates every refusal (53). 3b took the 20 it can fix;
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


def test_no_correctness_count_when_the_executed_calibration_fails(capsys):
    """g016 is wrong on real 2.0.51 and g007 is right. A reference judge that
    calls g016 SUPPORTED is not trusted, and prints no count."""
    bad = [{"id": "g016", "verdict_ref": "SUPPORTED"}, {"id": "g007", "verdict_ref": "SUPPORTED"}]
    assert escalate.report_reference([], bad, 38, 91) == {}
    assert "CALIBRATION FAILED" in capsys.readouterr().out
    good = [{"id": "g016", "verdict_ref": "UNSUPPORTED"}, {"id": "g007", "verdict_ref": "PARTIAL"}]
    assert escalate.calibration_ok(good)


# --- Step 4d: the hosted generator on all 100 -------------------------------

def gold(i, answerable=True, chunks=("c1",), verified="human"):
    return {"id": i, "question": "q", "answerable": answerable, "verified_by": verified,
            "answer_chunks": list(chunks) if answerable else []}


CHUNKS = {c: {"id": c, "text": c, "source_path": c, "heading_path": [c]} for c in ("c1", "c2", "c9")}


def gen(i, answer="an answer [1]", hits=("c1",), empty=False):
    return {"id": i, "answer": "" if empty else answer, "hits": list(hits), "empty": empty,
            "refused": False, "prompt_tokens": 10, "output_tokens": 2}


def test_all_ids_are_every_verified_item_sorted_and_repeat_is_the_first_twenty():
    golden = {i: gold(i) for i in [f"g{n:03d}" for n in range(30, 0, -1)]}
    golden["g999"] = gold("g999", verified="claude")
    ids = escalate.all_ids(golden)
    assert ids == sorted(i for i in golden if i != "g999")
    assert escalate.repeat_ids(golden) == ids[:20]


def test_outcome_rows_use_the_repos_definitions_and_leave_empty_rows_out():
    golden = {"g1": gold("g1"), "g2": gold("g2"), "g3": gold("g3", answerable=False), "g4": gold("g4")}
    rows = [gen("g1"), gen("g2", hits=("c9",)), gen("g3", answer=ask.REFUSAL_OPENING + " this."),
            gen("g4", empty=True)]
    out = {r["id"]: r for r in escalate.outcome_rows(rows, golden, CHUNKS)}
    assert set(out) == {"g1", "g2", "g3"}, "an EMPTY row is neither an answer nor a refusal"
    assert out["g1"]["answer_in_prompt"] and not out["g2"]["answer_in_prompt"]
    assert out["g3"]["refused"] and not out["g3"]["answer_in_prompt"]


def outcome(i, delivered, answerable=True):
    return {"id": i, "answerable": answerable, "answer_in_prompt": True,
            "answer": "an answer [1]" if delivered else ask.REFUSAL_OPENING + " this.",
            "refused": not delivered}


def test_pairing_is_by_id_on_delivered_and_drops_items_missing_on_either_side():
    new = [outcome("g1", True), outcome("g2", False), outcome("g3", True), outcome("g5", True)]
    old = [outcome("g1", False), outcome("g2", True), outcome("g3", True), outcome("g4", False)]
    p = escalate.paired(new, old)
    assert (p["n"], p["fixed"], p["broken"]) == (3, ["g1"], ["g2"])


def test_the_verdict_rules_are_the_pre_registered_ones():
    v = lambda f, b: escalate.verdict({"fixed": ["x"] * f, "broken": ["y"] * b,
                                       "p": ask_p(f, b)})
    assert v(6, 0) == "AHEAD"
    assert ask_p(12, 2) < 0.05 and v(12, 2) == "LEVEL", "broken <= 1 is part of the bar, even when p passes"
    assert v(5, 0) == "LEVEL", "fixed >= 6 is part of the bar"
    assert v(0, 8) == "BEHIND"
    assert v(3, 2) == "LEVEL"


def ask_p(f, b):
    from rag import score
    return score.mcnemar_exact(f, b)


def test_stability_counts_decisions_and_text_separately():
    first = [gen("g1", "same [1]"), gen("g2", "wording A [1]"), gen("g3", "an answer [1]")]
    second = [gen("g1", "same [1]"), gen("g2", "wording B [1]"),
              gen("g3", ask.REFUSAL_OPENING + " this.")]
    s = escalate.stability(first, second)
    assert (s["n"], s["same_decision"], s["same_text"], s["flipped"]) == (3, 2, 1, ["g3"])


def test_a_timeout_skips_that_question_and_the_run_continues():
    """The gap, in this loop: retrying() gives up and re-raises TimeoutError,
    which used to end a 100-call run at the first slow question."""
    calls = []

    def post(path, body, key):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("slow")
        return reply("an answer [1]")

    items = [{"id": f"g{n}", "question": "q"} for n in range(3)]
    rows = escalate.generate_rows(items, key="k", post=post, retrieve=lambda q: [hit()],
                                  log=lambda *a: None, sleep=lambda s: None)
    assert [r["id"] for r in rows] == ["g1", "g2"], "g0 left unasked, so a resume asks it again"


def test_the_all_report_refuses_to_quote_a_run_missing_more_than_five(capsys):
    golden = {f"g{n}": gold(f"g{n}") for n in range(10)}
    rows = [gen(f"g{n}") for n in range(4)]
    escalate.report_all(rows, [], golden, CHUNKS, qwen_lab=[], qwen_mac=[], prices=None)
    out = capsys.readouterr().out
    assert "NOT QUOTED" in out
    assert "AHEAD" not in out and "LEVEL" not in out and "BEHIND" not in out


def test_the_all_report_gives_no_faithfulness_verdict_while_judging_is_unfinished(capsys):
    golden = {f"g{n}": gold(f"g{n}") for n in range(3)}
    rows = [dict(gen("g0"), verdict_nvidia="SUPPORTED"), gen("g1"), gen("g2")]
    escalate.report_all(rows, [], golden, CHUNKS, qwen_lab=[], qwen_mac=[], prices=None)
    out = capsys.readouterr().out
    assert "judged 1 of 3" in out and "no verdict" in out


def test_an_unparsed_verdict_is_not_counted_as_judged(capsys):
    """Step 4d, found on the real run: g025's judge reply was empty, came back
    UNPARSED, and the report printed 'judged 69 of 69'. An unreadable verdict is
    not a verdict, so the faithfulness rule must wait for it."""
    golden = {f"g{n}": gold(f"g{n}") for n in range(2)}
    rows = [dict(gen("g0"), verdict_nvidia="SUPPORTED"), dict(gen("g1"), verdict_nvidia="UNPARSED")]
    escalate.report_all(rows, [], golden, CHUNKS, qwen_lab=[], qwen_mac=[], prices=None)
    out = capsys.readouterr().out
    assert "judged 1 of 2" in out and "no verdict" in out and "UNPARSED g1" in out


def test_a_judge_resume_asks_an_unparsed_row_again():
    assert escalate.needs_judging({"refused": False, "verdict_nvidia": "UNPARSED"})
    assert not escalate.needs_judging({"refused": False, "verdict_nvidia": "PARTIAL"})
    assert not escalate.needs_judging({"refused": True})
    assert not escalate.needs_judging({"refused": False, "empty": True})


# --- Step 4e: the same judge on both models ----------------------------------

def test_qwen_rows_to_judge_are_its_answers_on_nemotrons_pages():
    qwen = [outcome("g1", True), outcome("g2", False), {**outcome("g3", True), "answer_in_prompt": False}]
    nem = [gen("g1", hits=("c1", "c2")), gen("g2", hits=("c9",)), gen("g3", hits=("c9",))]
    rows = escalate.qwen_judge_rows(qwen, nem)
    assert [r["id"] for r in rows] == ["g1", "g3"], "declines are not judged"
    assert rows[0]["hits"] == ["c1", "c2"] and rows[0]["answer"] == "an answer [1]"
    assert not rows[0]["refused"] and not rows[0]["empty"]


def test_same_judge_pairing_drops_unparsed_and_page_flag_mismatches():
    nem = {"g1": "SUPPORTED", "g2": "PARTIAL", "g3": "SUPPORTED", "g4": "UNPARSED", "g5": "SUPPORTED"}
    qwen = {"g1": "PARTIAL", "g2": "SUPPORTED", "g3": "SUPPORTED", "g4": "SUPPORTED", "g5": "PARTIAL"}
    flags_differ = {"g5"}
    p = escalate.paired_support(nem, qwen, drop=flags_differ)
    assert (p["n"], p["fixed"], p["broken"]) == (3, ["g1"], ["g2"])
    assert p["dropped"] == ["g4", "g5"]


def test_the_same_judge_verdict_uses_the_pre_registered_bar():
    assert escalate.faith_verdict({"fixed": ["x"] * 6, "broken": [], "p": ask_p(6, 0)}) == "MORE faithful"
    assert escalate.faith_verdict({"fixed": ["x"] * 12, "broken": ["y"] * 2, "p": ask_p(12, 2)}) == "LEVEL"
    assert escalate.faith_verdict({"fixed": [], "broken": ["y"] * 8, "p": ask_p(0, 8)}) == "LESS faithful"


# --- Step 4f: which answers the correctness checks cover ----------------------

def test_delivered_ids_are_answerable_page_present_and_answered():
    golden = {"g1": gold("g1"), "g2": gold("g2"), "g3": gold("g3", answerable=False), "g4": gold("g4")}
    rows = [gen("g1"), gen("g2", hits=("c9",)), gen("g3"), gen("g4", answer=ask.REFUSAL_OPENING + " this.")]
    assert escalate.delivered_ids(rows, golden, CHUNKS) == ["g1"]


def test_the_committed_delivered_list_matches_the_rows():
    """tools/check_nemotron_all.py runs with nothing but SQLAlchemy installed, so it
    reads this list from a file. The file must be what the rows compute."""
    import json
    import pytest
    from rag import score
    if not score.CHUNKS_PATH.exists():
        pytest.skip("corpus/chunks.jsonl is generated and gitignored")
    golden = {i["id"]: i for i in score.load_golden()}
    rows = json.loads(escalate.ROWS_ALL.read_text())["rows"]
    saved = json.loads(escalate.DELIVERED_IDS.read_text())["ids"]
    assert saved == escalate.delivered_ids(rows, golden, score.load_chunks())


# --- the PARTIAL review sheet --------------------------------------------------

def _sheet_rows():
    return [{"id": "g1", "verdict_nvidia": "PARTIAL", "hits": ["c1"], "answer": "an answer [1]",
             "reason_nvidia": "r"}]


def test_the_review_sheet_shows_each_pages_heading_as_the_model_saw_it(tmp_path, monkeypatch):
    """ask.build_prompt gives the model each page's heading line. The first sheet showed only
    the text, and g044's human reason ('the section title is not in the excerpts') was written
    without the heading that says 'bound metadata removed'."""
    from rag import score
    monkeypatch.setattr(escalate, "SHEET", tmp_path / "sheet.md")
    monkeypatch.setattr(score, "load_chunks", lambda: {"c1": {"text": "body", "heading_path": ["Guide", "bound metadata removed"]}})
    escalate.write_sheet(_sheet_rows(), {"g1": {"question": "q", "answer_chunks": ["c1"]}})
    assert "Guide > bound metadata removed" in (tmp_path / "sheet.md").read_text()


def test_the_review_sheet_is_never_regenerated_over_human_verdicts(tmp_path, monkeypatch):
    from rag import score
    sheet = tmp_path / "sheet.md"
    sheet.write_text("**Human verdict:** PARTIAL  **Reason:** mine\n")
    monkeypatch.setattr(escalate, "SHEET", sheet)
    monkeypatch.setattr(score, "load_chunks", lambda: {"c1": {"text": "body", "heading_path": ["H"]}})
    import pytest
    with pytest.raises(SystemExit):
        escalate.write_sheet(_sheet_rows(), {"g1": {"question": "q", "answer_chunks": ["c1"]}})
    assert "mine" in sheet.read_text()


# --- Step 4g: the judge given what the model was given --------------------------

CHUNK = {"id": "c7", "text": "Use autoload_with.", "heading_path": ["Guide", "\"bound metadata\" removed"],
         "sqlalchemy_version": "2.0.51", "source_path": "doc/build/changelog/migration_20.rst"}


def test_a_passage_shown_to_the_judge_is_exactly_the_block_the_model_saw():
    h = types.SimpleNamespace(payload=CHUNK)
    prompt = ask.build_prompt("q?", [h])
    block = prompt.split("SOURCES\n\n", 1)[1].split("\n\n---\n\n", 1)[0]
    assert block == "[1] " + escalate.passage_as_shown(CHUNK)
    assert "\"bound metadata\" removed" in escalate.passage_as_shown(CHUNK)


def test_judging_with_headings_writes_new_fields_and_keeps_the_text_only_verdict():
    seen = []

    def judge(answer, passages):
        seen.append(passages)
        return {"verdict": "SUPPORTED", "reason": "heading [1]"}

    rows = [dict(gen("g1", hits=("c7",)), verdict_nvidia="PARTIAL"), gen("g2", answer=ask.REFUSAL_OPENING + " x.")]
    escalate.judge_into(rows, {"c7": CHUNK}, judge, field="verdict_nvidia_h", headings=True, log=lambda *a: None)
    assert rows[0]["verdict_nvidia"] == "PARTIAL" and rows[0]["verdict_nvidia_h"] == "SUPPORTED"
    assert "verdict_nvidia_h" not in rows[1], "a decline is not judged"
    assert seen == [[escalate.passage_as_shown(CHUNK)]]


def test_judge_into_text_only_and_resume_skips_readable_verdicts():
    calls = []
    judge = lambda a, p: calls.append(p) or {"verdict": "PARTIAL", "reason": ""}
    rows = [dict(gen("g1", hits=("c7",)), verdict_nvidia_t2="SUPPORTED"), dict(gen("g2", hits=("c7",)), verdict_nvidia_t2="UNPARSED")]
    escalate.judge_into(rows, {"c7": CHUNK}, judge, field="verdict_nvidia_t2", headings=False, log=lambda *a: None)
    assert calls == [["Use autoload_with."]] and rows[1]["verdict_nvidia_t2"] == "PARTIAL"


def test_flips_count_supported_changes_both_ways_over_readable_pairs():
    rows = [{"id": "a", "x": "PARTIAL", "y": "SUPPORTED"}, {"id": "b", "x": "SUPPORTED", "y": "PARTIAL"},
            {"id": "c", "x": "PARTIAL", "y": "UNSUPPORTED"}, {"id": "d", "x": "SUPPORTED", "y": "UNPARSED"},
            {"id": "e", "x": "UNSUPPORTED", "y": "SUPPORTED"}]
    f = escalate.flips(rows, "x", "y")
    assert (f["n"], f["up"], f["down"]) == (4, ["a", "e"], ["b"])


def test_noise_ids_are_the_first_twenty_answered_by_id():
    rows = [gen(f"g{n:03d}") for n in range(30, 0, -1)] + [gen("g000", answer=ask.REFUSAL_OPENING + " x.")]
    assert escalate.noise_ids(rows) == [f"g{n:03d}" for n in range(1, 21)]


def test_the_headings_rule_needs_low_noise_and_a_significant_upward_shift():
    up = lambda k: {"n": 60, "up": ["u"] * k, "down": [], "p": ask_p(k, 0)}
    assert escalate.headings_matter([up(6)], noise_flips=1) == "headings MATTER"
    assert escalate.headings_matter([up(6)], noise_flips=3) == "judge too noisy to attribute"
    assert escalate.headings_matter([up(2)], noise_flips=0) == "headings do NOT matter"
    assert escalate.headings_matter([{"n": 60, "up": ["u"] * 3, "down": ["d"] * 3, "p": 1.0}], noise_flips=0) == "headings do NOT matter"
    assert ask_p(3, 12) < 0.05
    assert escalate.headings_matter([{"n": 60, "up": ["u"] * 3, "down": ["d"] * 12, "p": ask_p(3, 12)}], noise_flips=0) == "headings do NOT matter", "a significant DOWNWARD shift is not headings helping"
