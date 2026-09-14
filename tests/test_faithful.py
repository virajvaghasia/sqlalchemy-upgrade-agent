"""Phase 4 — the faithfulness judge's plumbing.

Every test here runs with no key and no network: `generate()` takes its
transport as an argument for exactly that reason. A test suite that needed a
credential would be skipped in CI and would therefore pin nothing.
"""

import json
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


# --- retrying: a 503 is not a broken key ------------------------------------
#
# D75 in a second transport. The bug there was not "too few excepts" -- it was
# two conditions collapsed into one: the service being gone must stop the run,
# one unlucky call must not.

def flaky_post(codes, reply="SUPPORTED\nbecause [1] says so"):
    """A transport that raises the given HTTP codes in order, then succeeds.
    Records how many times it was called."""
    calls = []

    def post(path, body, key, timeout=120):
        calls.append(path)
        if len(calls) <= len(codes):
            raise urllib.error.HTTPError(
                "u", codes[len(calls) - 1], "busy", {}, None)
        return {"candidates": [{"content": {"parts": [{"text": reply}]}}]}

    post.calls = calls
    return post


def test_a_503_is_retried_and_then_succeeds():
    """Measured 2026-09-03: gemini-3.6-flash returned 503 'high demand' on a
    key that was perfectly valid. Without this the whole sweep dies."""
    post = flaky_post([503])
    out = faithful.retrying(post, backoff=0, sleep=lambda s: None)(
        "models/x:generateContent", {}, "k")
    assert out["candidates"]
    assert len(post.calls) == 2


def test_a_429_is_retried():
    """Rate limiting is the free tier's normal weather, not a failure."""
    post = flaky_post([429, 429])
    faithful.retrying(post, backoff=0, sleep=lambda s: None)(
        "models/x:generateContent", {}, "k")
    assert len(post.calls) == 3


def test_a_404_is_NOT_retried():
    """A wrong model id is wrong four times too. The 2026-08-31 404 on
    gemini-2.5-flash must surface immediately, not after four backoffs."""
    post = flaky_post([404, 404, 404, 404])
    with pytest.raises(urllib.error.HTTPError):
        faithful.retrying(post, backoff=0, sleep=lambda s: None)(
            "models/x:generateContent", {}, "k")
    assert len(post.calls) == 1


def test_retrying_gives_up_and_raises_rather_than_returning_none():
    """A transport that quietly returned None would produce a KeyError deep in
    generate() and read as a parsing bug rather than an outage."""
    post = flaky_post([503, 503, 503, 503])
    with pytest.raises(urllib.error.HTTPError):
        faithful.retrying(post, attempts=4, backoff=0, sleep=lambda s: None)(
            "models/x:generateContent", {}, "k")
    assert len(post.calls) == 4


def test_a_socket_timeout_is_retried_not_walked_past():
    """D75 exactly: socket.timeout is a TimeoutError and is NOT a URLError, so
    a handler written for one does not cover the other."""
    calls = []

    def post(path, body, key, timeout=120):
        calls.append(path)
        if len(calls) == 1:
            raise TimeoutError("timed out")
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED"}]}}]}

    faithful.retrying(post, backoff=0, sleep=lambda s: None)(
        "models/x:generateContent", {}, "k")
    assert len(calls) == 2


# --- what gets sent to the judge --------------------------------------------

def test_prose_drops_fenced_code():
    """Code grounding is judge.ungrounded_calls' half (D77) and it is exact.
    Sending the code here would spend a call to re-answer it worse."""
    answer = "Use [1] the new API.\n```python\nop.create_view('v')\n```\nThat is all."
    assert "create_view" not in faithful.prose(answer)
    assert "the new API" in faithful.prose(answer)


def test_prose_uses_judges_own_fence_pattern():
    """One home per pattern. probe.py once held a private copy of a detector
    and silenced the signal it existed for."""
    from rag import judge
    assert faithful.judge.CODE_FENCE is judge.CODE_FENCE


def test_a_code_only_answer_is_NO_PROSE_and_not_SUPPORTED():
    """Calling it SUPPORTED because there was nothing to read is the
    flattering direction -- D62's trap."""
    row = faithful.judge_answer("```python\nx = 1\n```", ["p"], key="k",
                                post=fake_post("SUPPORTED\nfine"))
    assert row["verdict"] == "NO_PROSE"


def test_a_real_answer_reaches_the_judge():
    row = faithful.judge_answer(
        "In 2.0 Query.from_self is removed and you use a subquery instead.",
        ["from_self is removed"], key="k",
        post=fake_post("SUPPORTED\n[1] states it"))
    assert row["verdict"] == "SUPPORTED"
    assert row["judge_model"] == faithful.MODEL


def test_sentences_do_not_split_on_a_dotted_api_name():
    """Query.from_self() and 2.0 are not sentence ends. The split needs
    whitespace after the period, which is the only case that actually bit."""
    out = faithful.sentences(
        "SQLAlchemy 2.0 removes Query.from_self() from the ORM entirely. "
        "Rewrite it with a subquery and aliased entities instead.")
    assert len(out) == 2
    assert "Query.from_self()" in out[0]


# --- the sweep --------------------------------------------------------------

ITEMS = [
    {"id": "g001", "question": "q one", "verified_by": "human"},
    {"id": "g002", "question": "q two", "verified_by": "human"},
    {"id": "g003", "question": "q three", "verified_by": "human"},
]


def saved_two_arms():
    return {
        "D": [
            {"id": "g001", "answer": "The sources do not answer this.",
             "provenance": "breakages"},
            {"id": "g002", "answer": "D says use a subquery in place of "
                                     "from_self, per the migration notes.",
             "provenance": "github"},
            {"id": "g003", "answer": "", "failed": True, "provenance": "x"},
        ],
        "H": [
            {"id": "g001", "answer": "[2] The sources do not answer this.",
             "provenance": "breakages"},
            {"id": "g002", "answer": "H says use a subquery in place of "
                                     "from_self, per the migration notes.",
             "provenance": "github"},
            {"id": "g003", "answer": "H answered where D failed, using "
                                     "select() and scalars() as shown.",
             "provenance": "x"},
        ],
    }


def counting_retrieve():
    seen = []

    def retrieve(question):
        seen.append(question)
        return [f"passage for {question}"]

    retrieve.seen = seen
    return retrieve


def test_refusals_are_excluded_before_any_call_is_made():
    """A decline has nothing to be faithful to, and counting it UNSUPPORTED
    would make the system look worse the more honest it got (D62)."""
    retrieve = counting_retrieve()
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                               post=fake_post("SUPPORTED\nyes"),
                               retrieve=retrieve, log=lambda *a: None)
    assert [r["id"] for r in rows["D"]] == ["g002"]


def test_a_CITED_refusal_is_still_a_refusal_here():
    """D76: H produced '[2] The sources do not answer this.' on six items and
    the bare prefix test scored every one as an answer. This module must not
    reintroduce that by testing the raw string itself."""
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["H"], key="k",
                               post=fake_post("SUPPORTED\nyes"),
                               retrieve=counting_retrieve(),
                               log=lambda *a: None)
    assert "g001" not in [r["id"] for r in rows["H"]]


def test_a_failed_row_is_neither_an_answer_nor_a_refusal():
    """D75: control-failed / variant-answered is a missing measurement, not a
    win. It is dropped on the side that failed and kept on the side that did
    not, because there is nothing to compare it against either way."""
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                               post=fake_post("SUPPORTED\nyes"),
                               retrieve=counting_retrieve(),
                               log=lambda *a: None)
    assert "g003" not in [r["id"] for r in rows["D"]]
    assert "g003" in [r["id"] for r in rows["H"]]


def test_both_arms_are_judged_against_ONE_retrieval_of_the_query():
    """Two lookups of the same query would almost certainly agree, and 'almost
    certainly' is how a difference between prompts becomes a difference between
    lookups. D74 retrieves once for the same reason."""
    retrieve = counting_retrieve()
    faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                        post=fake_post("SUPPORTED\nyes"),
                        retrieve=retrieve, log=lambda *a: None)
    assert retrieve.seen == ["q two", "q three"]      # once each, not per arm


def test_an_item_no_arm_answered_is_never_retrieved():
    saved = {"D": [{"id": "g001", "answer": "The sources do not answer this."}]}
    retrieve = counting_retrieve()
    faithful.sweep_rows(saved, ITEMS, ["D"], key="k",
                        post=fake_post("SUPPORTED\nyes"), retrieve=retrieve,
                        log=lambda *a: None)
    assert retrieve.seen == []


def test_every_row_carries_the_judge_that_produced_it():
    """D78: the tight property is not that the model never changes, it is that
    a row never loses track of which model read it."""
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D"], key="k",
                               post=fake_post("SUPPORTED\nyes"),
                               retrieve=counting_retrieve(),
                               log=lambda *a: None)
    assert all(r["judge_model"] == faithful.MODEL for r in rows["D"])


# --- the aggregate ----------------------------------------------------------

def rows_of(*verdicts):
    return [{"id": f"g{n:03d}", "verdict": v, "reason": "r", "claim": "c",
             "judge_model": faithful.MODEL, "variant": "D"}
            for n, v in enumerate(verdicts, 1)]


def test_PARTIAL_is_not_counted_as_supported():
    """Half a supported answer is what g065 looks like under prompt H: a
    paraphrase of one page plus a leap. Rolling it into SUPPORTED would erase
    the only distinction D77 found that a count could not see."""
    agg = faithful.aggregate(rows_of("SUPPORTED", "PARTIAL"))
    assert agg["supported_rate"] == 0.5


def test_NO_PROSE_is_outside_every_rate():
    """It is not a pass and not a failure; it is an answer this half cannot
    read. Putting it in the denominator would move the rate for a reason that
    has nothing to do with faithfulness."""
    agg = faithful.aggregate(rows_of("SUPPORTED", "NO_PROSE"))
    assert agg["judged"] == 1 and agg["supported_rate"] == 1.0


def test_UNPARSED_is_kept_and_not_coerced():
    """A judge that stopped following the format is a fact about the run.
    Mapping it onto UNSUPPORTED would move a number in the flattering
    direction, which is the ask.refused failure of D76."""
    agg = faithful.aggregate(rows_of("SUPPORTED", "UNPARSED"))
    assert agg["UNPARSED"] == 1
    assert agg["judged"] == 1


def test_an_empty_run_does_not_divide_by_zero():
    """report() crashed on an empty run once already (D71)."""
    assert faithful.aggregate([])["supported_rate"] == 0.0


# --- Step 5: the sample a human reads ---------------------------------------

def test_the_agreement_sample_puts_the_risky_verdicts_first():
    """Risk-weighted, like the golden signature's ten (§H CLOSED). A uniform
    sample from a mostly-SUPPORTED set measures agreement where it is
    easiest."""
    by_variant = {"D": rows_of("SUPPORTED", "SUPPORTED", "UNSUPPORTED",
                               "PARTIAL", "SUPPORTED")}
    sample = faithful.agreement_sample(by_variant, n=3)
    assert [r["verdict"] for r in sample] == ["UNSUPPORTED", "PARTIAL",
                                              "SUPPORTED"]


def test_the_sample_still_includes_SUPPORTED_rows():
    """Without them the sheet can only catch the judge accusing wrongly, never
    the judge missing something -- and a miss is the g065 failure mode."""
    by_variant = {"D": rows_of("UNSUPPORTED", "SUPPORTED", "SUPPORTED")}
    assert "SUPPORTED" in [r["verdict"]
                           for r in faithful.agreement_sample(by_variant, n=3)]


def test_the_sample_records_which_variant_each_verdict_came_from():
    by_variant = {"D": rows_of("SUPPORTED"), "H": rows_of("UNSUPPORTED")}
    sample = faithful.agreement_sample(by_variant, n=2)
    assert sample[0]["variant"] == "H"


def test_the_sheet_asks_for_a_verdict_and_supplies_none(tmp_path):
    """D06 in the artifact, not only in the docstring."""
    out = tmp_path / "sheet.md"
    faithful.agreement_sheet(
        faithful.agreement_sample({"D": rows_of("UNSUPPORTED")}, n=1),
        ITEMS, out, retrieve=lambda q: [("c00001", "a passage")])
    text = out.read_text()
    assert faithful.HUMAN_VERDICT + " _______" in text
    assert "does not fill it in" in text
    assert faithful.read_agreement(out) == {"n": 1, "filled": 0, "agree": 0,
                                           "corrections": [],
                                            "rate": None}


def test_the_sweep_checkpoints_so_a_dead_run_is_not_a_lost_run(monkeypatch):
    """D75, literally: the first full prompt sweep died at generation 150 of
    300 with zero rows saved. These rows cost API calls, not just time."""
    monkeypatch.setattr(faithful, "CHECKPOINT_EVERY", 1)
    written = []
    faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                        post=fake_post("SUPPORTED\nyes"),
                        retrieve=counting_retrieve(), log=lambda *a: None,
                        checkpoint=lambda rows: written.append(
                            {v: len(r) for v, r in rows.items()}))
    assert written == [{"D": 1, "H": 1}, {"D": 1, "H": 2}]


def test_the_model_travels_into_the_rows_when_it_is_overridden():
    """2026-09-03: the pinned id answered 503 all day while three neighbours
    answered. --model must change what is USED and what is RECORDED together,
    or a row claims a reader that never read it (D78)."""
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D"], key="k",
                               model="gemini-3.8-flash",
                               post=fake_post("SUPPORTED\nyes"),
                               retrieve=counting_retrieve(),
                               log=lambda *a: None)
    assert rows["D"][0]["judge_model"] == "gemini-3.8-flash"


# --- reading the filled sheet back ------------------------------------------

def sheet_with(*answers) -> str:
    out = []
    for a in answers:
        out += [f"## x", faithful.HUMAN_VERDICT + f" {a}", ""]
    return "\n".join(out)


def test_DISAGREE_is_not_read_as_AGREE(tmp_path):
    """DISAGREE contains AGREE as a substring. A naive `in` test scores every
    disagreement as agreement -- the flattering direction, which is where every
    detector bug in this phase has landed (D76, D79)."""
    f = tmp_path / "s.md"
    f.write_text(sheet_with("DISAGREE", "AGREE"))
    assert faithful.read_agreement(f) == {
        "n": 2, "filled": 2, "agree": 1,
        "corrections": [{"id": None, "judge_said": None, "should_be": None}],
                                          "rate": 0.5}


def test_an_unfilled_row_is_never_counted_as_agreement(tmp_path):
    f = tmp_path / "s.md"
    f.write_text(sheet_with("_______", "AGREE"))
    got = faithful.read_agreement(f)
    assert got["filled"] == 1 and got["agree"] == 1 and got["n"] == 2


def test_a_missing_sheet_reports_no_rate_rather_than_a_hundred_percent(tmp_path):
    """None is not 1.0. A judge whose agreement was never measured must not
    read as a judge that agreed with everything."""
    assert faithful.read_agreement(tmp_path / "absent.md")["rate"] is None


def test_decoration_around_the_answer_still_parses(tmp_path):
    """Someone will write `AGREE` with backticks. The verdict parser already
    learned this lesson once with **SUPPORTED**."""
    f = tmp_path / "s.md"
    f.write_text(sheet_with("`AGREE`"))
    assert faithful.read_agreement(f)["agree"] == 1


def test_the_sweep_paces_itself_between_calls_but_not_before_the_first():
    """The free tier limit is per minute. Measured 2026-09-03: an unpaced run
    of ~110 calls did not finish ten items in seven minutes, because every few
    calls earned a 429 and then a backoff far longer than the pause would have
    been. A leading sleep would just be dead time."""
    waits = []
    faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                        post=fake_post("SUPPORTED\nyes"),
                        retrieve=counting_retrieve(), log=lambda *a: None,
                        pace=6.0, sleep=waits.append)
    assert waits == [6.0, 6.0]          # 3 calls, 2 gaps


def test_the_report_names_the_judge_that_actually_read_the_rows(capsys):
    """The first draft printed the module constant and so announced
    `gemini-3.7-flash` over a run judged by `gemma4:e4b`. A report that
    misnames its own instrument is what stamp() exists to prevent (D78)."""
    rows = rows_of("SUPPORTED")
    for r in rows:
        r["judge_model"] = "gemma4:e4b"
    faithful.report({"D": rows})
    out = capsys.readouterr().out
    assert "gemma4:e4b" in out and faithful.MODEL not in out


def test_two_judges_in_one_run_is_called_out_as_void(capsys):
    """D78's tight property is one judge across both arms. Two ids means the
    comparison is not a comparison, and silence there would let it be read as
    one."""
    a, b = rows_of("SUPPORTED"), rows_of("UNSUPPORTED")
    b[0]["judge_model"] = "some-other-model"
    faithful.report({"D": a, "H": b})
    assert "TWO JUDGES IN ONE RUN" in capsys.readouterr().out


# --- the local transport ----------------------------------------------------

def test_the_local_judge_pins_its_context_window():
    """Ollama's default context is 4096 and it truncates SILENTLY past it: no
    error, just a judge that read four of the five passages. Measured
    2026-09-03 the judge prompt is 1800-2800 tokens, which fits 4096 today --
    which is precisely when to pin it, because the run that overflows reports
    numbers rather than a failure."""
    seen = {}

    def fake_urlopen(request, timeout=None):
        import json as j
        seen.update(j.loads(request.data))

        class R:
            def read(self):
                return j.dumps({"message": {"content": "SUPPORTED\nyes"}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    import urllib.request
    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        faithful.local_post("models/gemma4:e4b:generateContent",
                            {"contents": [{"parts": [{"text": "hi"}]}]}, "")
    finally:
        urllib.request.urlopen = real
    assert seen["options"]["num_ctx"] == faithful.LOCAL_CONTEXT
    assert seen["options"]["temperature"] == 0.0
    assert seen["model"] == "gemma4:e4b"


def test_the_local_judge_is_not_the_generator():
    """ROADMAP.md's objection is to SELF-grading. A judge sharing weights with
    ask.MODEL would be exactly that."""
    from rag import ask
    assert faithful.LOCAL_MODEL != ask.MODEL


# --- resuming a killed run --------------------------------------------------

def test_resume_skips_items_both_arms_already_judged():
    """A killed run costs hours here. But an item is skipped only when EVERY
    selected arm already has it -- a half-judged item would leave one arm short
    and turn a paired comparison into two averages (D61)."""
    prior = {"D": [{"id": "g002", "verdict": "SUPPORTED", "reason": "r",
                    "claim": "c", "judge_model": faithful.MODEL}],
             "H": [{"id": "g002", "verdict": "SUPPORTED", "reason": "r",
                    "claim": "c", "judge_model": faithful.MODEL}]}
    retrieve = counting_retrieve()
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                               post=fake_post("UNSUPPORTED\nno"),
                               retrieve=retrieve, log=lambda *a: None,
                               resume=prior)
    assert retrieve.seen == ["q three"]              # g002 never re-retrieved
    assert [r["verdict"] for r in rows["D"]] == ["SUPPORTED"]


def test_a_half_judged_item_is_finished_not_skipped():
    """Only D judged g002 last time. Skipping it would leave H one row short
    on an item D has -- the unpaired shape D61 exists to prevent."""
    prior = {"D": [{"id": "g002", "verdict": "SUPPORTED", "reason": "r",
                    "claim": "c", "judge_model": faithful.MODEL}], "H": []}
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                               post=fake_post("PARTIAL\nhalf"),
                               retrieve=counting_retrieve(),
                               log=lambda *a: None, resume=prior)
    assert [r["id"] for r in rows["D"]] == ["g002"]          # not re-judged
    assert "g002" in [r["id"] for r in rows["H"]]            # finished


# --- judging the arms of one item at the same time --------------------------

def test_rows_keep_variant_order_when_an_arm_is_slower():
    """Rows must not land in completion order.

    NOTE ON WHAT THIS DOES AND DOES NOT PIN. The guarantee comes from
    `pool.map` returning results in INPUT order, not from the append loop -- a
    mutation swapping that loop to iterate the results dict passes this test,
    which was checked rather than assumed. So this pins the observable
    behaviour and the comment in `sweep_rows` names the real mechanism: moving
    to `as_completed` would break it and nothing here would notice."""
    import time as _t

    def slow_for_D(path, body, key, timeout=120):
        # D's prompt is the one containing "D says"; make it finish last.
        if "D says" in body["contents"][0]["parts"][0]["text"]:
            _t.sleep(0.05)
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED\nx"}]}}]}

    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                               post=slow_for_D, retrieve=counting_retrieve(),
                               log=lambda *a: None, workers=2)
    assert [r["id"] for r in rows["D"]] == ["g002"]
    assert [r["id"] for r in rows["H"]] == ["g002", "g003"]


def test_pacing_forces_the_sequential_path():
    """`pace` exists to stay under a per-minute API ceiling. Firing concurrent
    calls at a rate limit is exactly the behaviour it was added to stop, so a
    paced run must not go parallel."""
    waits = []
    faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], key="k",
                        post=fake_post("SUPPORTED\nyes"),
                        retrieve=counting_retrieve(), log=lambda *a: None,
                        pace=6.0, sleep=waits.append, workers=8)
    assert waits == [6.0, 6.0]


def test_concurrent_arms_produce_the_same_rows_as_sequential():
    """Concurrency changes WHEN a call happens, not what it reads."""
    args = dict(key="k", post=fake_post("PARTIAL\nhalf"),
                retrieve=counting_retrieve(), log=lambda *a: None)
    one = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], workers=1, **args)
    two = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D", "H"], workers=2, **args)
    assert one == two


def test_the_sample_reserves_supported_controls_even_when_risky_rows_fill_it():
    """Measured 2026-09-03: the finished run has 7 UNSUPPORTED and 5 PARTIAL,
    so ranking by risk alone put ZERO SUPPORTED rows in the ten. A sheet of
    only accusations can catch the judge condemning wrongly and is
    structurally incapable of catching the judge waving something through --
    which is the g065 failure mode."""
    by_variant = {"D": rows_of(*(["UNSUPPORTED"] * 7 + ["PARTIAL"] * 5
                                 + ["SUPPORTED"] * 20))}
    sample = faithful.agreement_sample(by_variant, n=10)
    assert len(sample) == 10
    assert sum(r["verdict"] == "SUPPORTED" for r in sample) == faithful.CONTROLS


def test_a_run_with_no_supported_rows_still_returns_a_full_sheet():
    """The reservation must not shrink the sheet when there is nothing to
    reserve."""
    by_variant = {"D": rows_of(*(["UNSUPPORTED"] * 12))}
    assert len(faithful.agreement_sample(by_variant, n=10)) == 10


def test_controls_prefer_a_supported_verdict_on_an_UNANSWERABLE_item():
    """Measured 2026-09-03: g056 -- the item D77 names as the reason a prose
    judge was needed -- came back SUPPORTED from both arms while D78 records
    gemini-3.6-flash judging it PARTIAL. The first version of this sample put
    no controls in at all, and the second would have picked arbitrary ones. A
    SUPPORTED row nobody suspects teaches a human nothing.

    An item the golden set marks unanswerable, answered and then called
    grounded, is two of this repo's own instruments disagreeing -- which is
    exactly the row a human should rule on."""
    rows = rows_of("SUPPORTED", "SUPPORTED", "SUPPORTED", "UNSUPPORTED")
    rows[0]["answerable"] = True                       # ordinary
    rows[1]["answerable"] = False                      # a fabrication
    rows[2]["answerable"] = True
    rows[2]["answer_in_prompt"] = False                # the open cell
    sample = faithful.agreement_sample({"D": rows}, n=4, controls=2)
    controls = [r for r in sample if r["verdict"] == "SUPPORTED"]
    assert controls[0]["answerable"] is False          # fabrication first
    assert controls[1]["answer_in_prompt"] is False    # open cell second


def test_the_sheet_shows_a_second_model_and_flags_disagreement(tmp_path):
    """Measured 2026-09-03: a second judge disagreed on 6 of the sheet's 10.
    Hiding that would hand a human ten verdicts and no signal about which ones
    two models already read differently."""
    out = tmp_path / "s.md"
    sample = faithful.agreement_sample({"D": rows_of("SUPPORTED")}, n=1)
    faithful.agreement_sheet(
        sample, ITEMS, out, retrieve=lambda q: [("c1", "p")],
        second={"D:g001": {"verdict": "PARTIAL", "reason": "half of it",
                           "judge_model": "gemini-3.5-flash"}})
    text = out.read_text()
    assert "A second model says:** `PARTIAL`" in text
    assert "they DISAGREE" in text


def test_the_sheet_is_unchanged_when_there_is_no_second_opinion(tmp_path):
    """--cross-check is optional; the sheet must render without it."""
    out = tmp_path / "s.md"
    faithful.agreement_sheet(
        faithful.agreement_sample({"D": rows_of("SUPPORTED")}, n=1),
        ITEMS, out, retrieve=lambda q: [("c1", "p")])
    assert "A second model says" not in out.read_text()
    assert faithful.HUMAN_VERDICT in out.read_text()


# --- a name is not an identity ----------------------------------------------

def test_two_tags_of_one_model_are_recognised_as_the_same_model():
    """Measured 2026-09-03 on this Mac: `gpt-5.5:latest` and `gemma4:e4b` share
    the digest c6eb396dbd59 -- two tags, one set of weights. A cross-check
    comparing only the strings would report high agreement while measuring a
    model against itself, which is the most flattering result this tool could
    produce from a log that looks entirely legitimate."""
    digests = {"gpt-5.5:latest": "sha256:c6eb396dbd59",
               "gemma4:e4b": "sha256:c6eb396dbd59",
               "qwen2.5-coder:7b": "sha256:dae161e27b0e"}
    assert faithful.same_model("gemma4:e4b", "gpt-5.5:latest", digests)
    assert not faithful.same_model("gemma4:e4b", "qwen2.5-coder:7b", digests)


def test_two_hosted_ids_are_different_models_even_with_no_digests():
    """A hosted id has no local digest to compare. Falling back to the names is
    right there: two different hosted ids are genuinely different models."""
    assert not faithful.same_model("gemini-3.5-flash", "gemini-3.8-flash", {})
    assert faithful.same_model("gemini-3.5-flash", "gemini-3.5-flash", {})


def test_an_unreachable_ollama_does_not_make_digest_lookup_explode():
    """--cross-check against a hosted model must work with Ollama stopped."""
    import urllib.request as u
    real = u.urlopen
    u.urlopen = lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("down"))
    try:
        assert faithful.local_digests() == {}
    finally:
        u.urlopen = real


def test_a_PER_DAY_429_is_not_retried():
    """A 429 is two conditions in one status code. Measured 2026-09-03 the body
    names which: quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier.
    A per-minute limit clears in under a minute and a backoff is right; a
    per-day limit does not clear today, so four retries cost 90 seconds to
    reach the same refusal -- and ten items of that is fifteen minutes of a
    tool looking busy while it fails."""
    import io
    calls = []

    def post(path, body, key, timeout=120):
        calls.append(path)
        raise urllib.error.HTTPError(
            "u", 429, "quota", {},
            io.BytesIO(b'{"error":{"details":[{"quotaId":'
                       b'"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}'))

    with pytest.raises(urllib.error.HTTPError):
        faithful.retrying(post, backoff=0, sleep=lambda s: None)(
            "models/x:generateContent", {}, "k")
    assert len(calls) == 1


def test_a_PER_MINUTE_429_is_still_retried():
    """The rate limit that clears in a minute is exactly what backoff is for."""
    import io
    calls = []

    def post(path, body, key, timeout=120):
        calls.append(path)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                "u", 429, "quota", {},
                io.BytesIO(b'{"error":{"details":[{"quotaId":'
                           b'"GenerateRequestsPerMinutePerProject"}]}}'))
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED"}]}}]}

    faithful.retrying(post, backoff=0, sleep=lambda s: None)(
        "models/x:generateContent", {}, "k")
    assert len(calls) == 2


def test_an_unreadable_429_body_still_gets_its_retries():
    """Guessing wrong here should cost a wait, not a stopped run."""
    post = flaky_post([429])
    faithful.retrying(post, backoff=0, sleep=lambda s: None)(
        "models/x:generateContent", {}, "k")
    assert len(post.calls) == 2


# --- the machine is part of a row's provenance ------------------------------

def test_every_row_records_the_machine_that_produced_it():
    """Measured 2026-09-05: same judge, same saved answers, same corpus,
    temperature 0 — prompt D's supported rate was 85% on the Mac and 77% on the
    lab 3060 (D83). Verdicts are not machine-independent, so a row carrying
    only its judge is under-labelled.

    **This goes through `sweep_rows`, not `stamp()`, and that is the point.**
    The first version called `stamp()` directly and passed for a full release
    while the pipeline dropped the field on the way out — `sweep_rows` builds
    its output dict field by field and simply did not copy it. Every row the
    lab saved on 2026-09-10 lacked a machine, and `report()` printed
    `judge gemma4:e4b on ?` over a run whose machine was known. A test that
    pins a function instead of the path the data takes pins nothing."""
    rows = faithful.sweep_rows(saved_two_arms(), ITEMS, ["D"], key="k",
                               post=fake_post("SUPPORTED\nyes"),
                               retrieve=counting_retrieve(),
                               log=lambda *a: None)
    assert rows["D"], "no rows produced"
    assert all(r["machine"] == faithful.machine() for r in rows["D"])
    assert "-" in rows["D"][0]["machine"]     # System-arch, e.g. Darwin-arm64


def test_stamp_itself_still_carries_the_machine():
    """Kept as the unit-level check, but it is NOT the one that matters."""
    assert faithful.stamp({"claim": "c"})["machine"] == faithful.machine()


def test_the_report_flags_rows_from_more_than_one_machine(capsys):
    """Not fatal the way two judges is, but it must be visible: a scorecard
    reading one machine's judge rows beside another's answers cannot tell."""
    a, b = rows_of("SUPPORTED"), rows_of("SUPPORTED")
    a[0]["machine"] = "Darwin-arm64"
    b[0]["machine"] = "Linux-x86_64"
    faithful.report({"D": a, "H": b})
    assert "ROWS FROM MORE THAN ONE MACHINE" in capsys.readouterr().out


def test_the_machine_stamp_is_not_a_hostname():
    """It identifies a machine CLASS, not a person's laptop."""
    import platform
    assert platform.node() not in faithful.machine()


def test_the_default_rows_path_carries_the_machine():
    """A stamp says afterwards which machine a row came from; a distinct path
    stops the second machine destroying the first one's evidence. The lab's run
    overwrote the Mac's `faithfulness-phase4.json` and the Mac's rows survived
    only because git had them (D83)."""
    assert faithful.machine() in faithful.ROWS_DEFAULT.name
    assert faithful.ROWS_LEGACY.name == "faithfulness-phase4.json"


# --- a transport failure must cost one item, not the run --------------------

def failing_post(fail_on: str, exc=None):
    """A transport that raises for one claim and answers every other call."""
    def post(path, body, key, timeout=120):
        text = json.dumps(body)
        if fail_on in text:
            raise exc or TimeoutError("timed out")
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED\nyes"}]}}]}
    return post


def test_one_timed_out_item_does_not_kill_the_sweep():
    """Measured the hard way 2026-09-10: the sweep died at item 63 of 64.

    `retrying()` behaved correctly -- it caught the `TimeoutError` that `D75`
    is about and gave up after four attempts -- and then the exception
    propagated out of `sweep_rows` and took the whole run with it. Three hours
    of judging survived only because checkpoints exist.

    **`compare_prompts` already learned this and `faithful` had not.** D75's
    own words: one retry, then the item is recorded `failed` and the sweep
    continues. The lesson never travelled between the two modules, and nothing
    failed until a real timeout arrived."""
    rows = faithful.sweep_rows(
        saved_two_arms(), ITEMS, ["D", "H"], key="k",
        post=failing_post("subquery in place of"),
        retrieve=counting_retrieve(), log=lambda *a: None)
    assert rows["H"], "the run must survive and produce rows"
    failed = [r for r in rows["D"] + rows["H"] if r["verdict"] == "FAILED"]
    assert failed, "the timed-out item must be recorded, not dropped silently"
    assert all(r.get("failed") for r in failed)


def test_a_failed_verdict_is_not_counted_as_judged():
    """A failure is not an answer and not a verdict; it is a missing
    measurement (D75). Counting it in the denominator would move the supported
    rate for a reason that has nothing to do with the answers."""
    rows = [{"id": "a", "verdict": "SUPPORTED"},
            {"id": "b", "verdict": "FAILED", "failed": True}]
    got = faithful.aggregate(rows)
    assert got["judged"] == 1
    assert got["FAILED"] == 1
    assert got["supported_rate"] == 1.0


def test_resume_retries_a_failed_item_rather_than_skipping_it():
    """The opposite bug to the one above, and just as quiet: if a `FAILED` row
    counted as done, `--resume` would treat a transport failure as a verdict
    and the item would never be judged at all -- a permanently missing row
    that looks like a completed run."""
    prior = {"D": [{"id": "g002", "verdict": "FAILED", "failed": True,
                    "reason": "timed out", "claim": "",
                    "judge_model": "m", "machine": faithful.machine()}],
             "H": []}
    rows = faithful.sweep_rows(
        saved_two_arms(), ITEMS, ["D"], key="k",
        post=fake_post("SUPPORTED\nyes"), retrieve=counting_retrieve(),
        resume=prior, log=lambda *a: None)
    g002 = [r for r in rows["D"] if r["id"] == "g002"]
    assert len(g002) == 1, "the failed row must be replaced, not duplicated"
    assert g002[0]["verdict"] == "SUPPORTED"


def test_the_report_names_the_items_that_failed(capsys):
    """A failure that does not appear in the report is indistinguishable from
    an item nobody asked about."""
    faithful.report({"D": [{"id": "g007", "verdict": "FAILED", "failed": True,
                            "reason": "timed out", "claim": "",
                            "judge_model": "gemma4:e4b",
                            "machine": "Darwin-arm64"}]})
    out = capsys.readouterr().out
    assert "g007" in out and "FAILED" in out


# --- reading the filled sheet back -------------------------------------------

AGREEMENT_SHEET = """# sheet

## 1. `g045`  (variant `D`, breakages)
**Judge says:** `UNSUPPORTED` — because.
{v} AGREE
{s} _______

## 2. `g080`  (variant `D`, github)
**Judge says:** `UNSUPPORTED` — because.
{v} DISAGREE
{s} PARTIAL

## 3. `g056`  (variant `H`, stackoverflow)
**Judge says:** `SUPPORTED` — because.
{v} DISAGREE
{s} PARTIAL
"""


def _sheet(tmp_path):
    p = tmp_path / "JUDGE-AGREEMENT.md"
    p.write_text(AGREEMENT_SHEET.format(v=faithful.HUMAN_VERDICT,
                                        s=faithful.SHOULD_HAVE_BEEN))
    return p


def test_the_corrections_are_read_back_not_just_the_rate(tmp_path):
    """A bare "70% agreement" is the least useful true sentence available.

    Measured 2026-09-11 on the real sheet: all three disagreements said the
    verdict should have been **PARTIAL** — the judge was not wrong at random,
    it was too extreme in both directions. That is a different defect from
    "30% inaccurate" and it needs the corrections, not the count."""
    got = faithful.read_agreement(_sheet(tmp_path))
    assert got["rate"] == 1 / 3
    assert [c["id"] for c in got["corrections"]] == ["g080", "g056"]
    assert {c["should_be"] for c in got["corrections"]} == {"PARTIAL"}
    assert got["corrections"][0]["judge_said"] == "UNSUPPORTED"


def test_a_disagreement_with_no_correction_is_still_a_disagreement(tmp_path):
    """The rate must not depend on whether the reader filled the second blank."""
    p = tmp_path / "s.md"
    p.write_text(f"**Judge says:** `SUPPORTED` — x.\n"
                 f"{faithful.HUMAN_VERDICT} DISAGREE\n"
                 f"{faithful.SHOULD_HAVE_BEEN} _______\n")
    got = faithful.read_agreement(p)
    assert got["filled"] == 1 and got["agree"] == 0
    assert got["corrections"] == [{"id": None, "judge_said": "SUPPORTED",
                                   "should_be": None}]


# --- Round 22: Phase 4's judge given the pages as the model saw them ------------

def _payload():
    return {"chunk_id": "c7", "text": "Use autoload_with.", "heading_path": ["Guide", "\"bound metadata\" removed"],
            "sqlalchemy_version": "2.0.51", "source_path": "doc/build/changelog/migration_20.rst"}


def test_passage_as_shown_is_the_block_ask_build_prompt_gives_the_model():
    import types
    from rag import ask, escalate
    h = types.SimpleNamespace(payload=_payload())
    block = ask.build_prompt("q?", [h]).split("SOURCES\n\n", 1)[1].split("\n\n---\n\n", 1)[0]
    assert block == "[1] " + faithful.passage_as_shown(_payload())
    assert escalate.passage_as_shown is faithful.passage_as_shown, "one definition, two callers"


def test_passages_for_gives_text_only_or_the_whole_block():
    import types
    hits = [types.SimpleNamespace(payload=_payload())]
    assert faithful.passages_for(hits, headings=False) == ["Use autoload_with."]
    assert faithful.passages_for(hits, headings=True) == [faithful.passage_as_shown(_payload())]


def test_a_headings_run_never_writes_over_the_text_only_rows():
    assert faithful.judged_rows_path(headings=True) != faithful.judged_rows_path(headings=False)
    assert "headings" in faithful.judged_rows_path(headings=True).name


def _v(**by_id):
    return [{"id": i, "verdict": v} for i, v in by_id.items()]


def test_compare_headings_counts_flips_per_arm_and_pairs_the_arms_with_headings():
    text = {"D": _v(g1="PARTIAL", g2="SUPPORTED", g3="PARTIAL"), "H": _v(g1="SUPPORTED", g2="PARTIAL", g4="SUPPORTED")}
    head = {"D": _v(g1="SUPPORTED", g2="SUPPORTED", g3="UNPARSED"), "H": _v(g1="SUPPORTED", g2="SUPPORTED", g4="PARTIAL")}
    c = faithful.compare_headings(text, head)
    assert (c["D"]["n"], c["D"]["up"], c["D"]["down"]) == (2, ["g1"], [])
    assert (c["H"]["up"], c["H"]["down"]) == (["g2"], ["g4"])
    assert c["paired"]["n"] == 2 and c["paired"]["h_only"] == [] and c["paired"]["d_only"] == []


def test_the_round_22_rule_matches_step_4g():
    arm = lambda up, down: {"n": 50, "up": ["u"] * up, "down": ["d"] * down}
    assert faithful.headings_verdict({"D": arm(6, 0), "H": arm(0, 0)}) == "headings MATTER"
    assert faithful.headings_verdict({"D": arm(3, 12), "H": arm(0, 0)}) == "headings do NOT matter"
    assert faithful.headings_verdict({"D": arm(2, 0), "H": arm(2, 0)}) == "headings do NOT matter"


def test_a_headings_sweep_sends_the_heading_to_the_judge(monkeypatch):
    """The wiring, end to end without a model: with headings=True the judge prompt
    carries the heading line; without it, it does not."""
    import types
    from rag import index
    hit = types.SimpleNamespace(payload=_payload())
    monkeypatch.setattr(index, "retrieve", lambda q, limit=5, **kw: [hit])
    prompts = []

    def post(path, body, key, timeout=120):
        prompts.append(json.dumps(body))
        return {"candidates": [{"content": {"parts": [{"text": "SUPPORTED\nPassage [1]."}]}}]}

    saved = {"D": [{"id": "g1", "answer": "Use autoload_with, since bound metadata was removed in 2.0. " * 2,
                    "refused": False, "answerable": True, "answer_in_prompt": True}]}
    items = [{"id": "g1", "question": "q", "answerable": True, "provenance": "breakages"}]
    for headings in (False, True):
        faithful.sweep_rows(saved, items, ["D"], key="k", post=post, headings=headings, log=lambda *a: None)
    assert "Guide > " not in prompts[0] and "Guide > " in prompts[1], "the heading line reaches the judge only with headings"
    assert "SQLAlchemy 2.0.51" in prompts[1] and "SQLAlchemy 2.0.51" not in prompts[0]
