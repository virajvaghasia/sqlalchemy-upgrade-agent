"""The hosted-model screen. No network, no key."""

from rag import ask, escalate, screen

CHUNK = {
    "id": "c1",
    "text": "body",
    "heading_path": ["Migration"],
    "sqlalchemy_version": "2.0.51",
    "source_path": "migration_20.rst",
}
ITEMS = [{"id": "g001", "question": "q1?"}, {"id": "g002", "question": "q2?"}]
PAGES = {"g001": ["c1"], "g002": ["c1"]}


def reply(text):
    return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2}}


def test_every_model_gets_the_shipped_prompt_and_only_the_model_name_differs():
    """If two models got different prompts the screen would compare prompts."""
    hits = [screen.Page(CHUNK)]
    body = screen.request_body("some/model", "q?", hits)
    assert body["model"] == "some/model"
    assert {k: v for k, v in body.items() if k != "model"} == {
        k: v for k, v in escalate.request_body("q?", hits).items() if k != "model"
    }
    assert body["messages"][1]["content"] == ask.build_prompt("q?", hits)


def test_a_question_the_endpoint_fails_on_is_left_out_not_scored_as_a_decline():
    def post(path, body, key):
        if "q1?" in body["messages"][1]["content"]:
            raise TimeoutError
        return reply("Use Session.get [1]")

    rows = screen.ask_model("m", ITEMS, PAGES, {"c1": CHUNK}, post=post, key="k", log=lambda *a: None)
    assert [r["id"] for r in rows] == ["g002"]
    assert rows[0]["refused"] is False and rows[0]["hits"] == ["c1"]


def test_a_reply_with_no_choices_is_a_failure_not_an_answer():
    rows = screen.ask_model(
        "m", ITEMS[:1], PAGES, {"c1": CHUNK}, post=lambda *a: {"choices": []}, key="k", log=lambda *a: None
    )
    assert rows == []


def test_a_rerun_asks_only_what_is_missing():
    asked = []

    def post(path, body, key):
        asked.append(body["messages"][1]["content"])
        return reply("answer [1]")

    done = [{"id": "g001", "answer": "kept", "refused": False, "empty": False}]
    rows = screen.ask_model("m", ITEMS, PAGES, {"c1": CHUNK}, post=post, key="k", done=done, log=lambda *a: None)
    assert len(asked) == 1 and "q2?" in asked[0]
    assert rows[0]["answer"] == "kept"


def summary(verdict="LEVEL", delivered=50, fabricated=(), missing=0):
    return {"verdict": verdict, "delivered": delivered, "fabricated": list(fabricated), "missing": missing}


def test_the_default_stays_unless_a_candidate_is_ahead():
    d = screen.decide({screen.CONTROL: summary(), "a": summary(delivered=55), "b": summary(delivered=52)})
    assert d["default"] == screen.CONTROL
    assert d["fallbacks"] == ["a", "b"]


def test_ahead_takes_the_default_and_the_measured_model_becomes_a_fallback():
    d = screen.decide({screen.CONTROL: summary(), "a": summary("AHEAD", 60)})
    assert d["default"] == "a"
    assert d["fallbacks"] == [screen.CONTROL]


def test_ahead_does_not_take_the_default_by_answering_more_unanswerable_questions():
    d = screen.decide({screen.CONTROL: summary(), "a": summary("AHEAD", 60, fabricated=["g056"])})
    assert d["default"] == screen.CONTROL
    assert d["fallbacks"] == ["a"]


def test_behind_too_many_made_up_answers_or_too_many_missing_is_not_used():
    d = screen.decide(
        {
            screen.CONTROL: summary(),
            "behind": summary("BEHIND", 30),
            "invents": summary(delivered=58, fabricated=["g056", "g065", "g001"]),
            "flaky": summary("AHEAD", 70, missing=screen.MAX_MISSING + 1),
        }
    )
    assert d["default"] == screen.CONTROL
    assert d["fallbacks"] == []
    assert sorted(d["unused"]) == ["behind", "flaky", "invents"]
