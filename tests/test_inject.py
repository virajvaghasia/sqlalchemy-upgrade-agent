"""
Pin Phase 7 Step 0's instrument. No model is called here.

What could silently rot: the payload landing in the wrong place (a question
payload that never reaches the prompt measures nothing and would report a clean
0), the item choice drifting so the two machines attack different questions, and
the canary check becoming a substring-of-anything.
"""

from types import SimpleNamespace

import pytest

from rag import ask, inject


def _hit(n: int, text: str):
    return SimpleNamespace(score=0.05 - n / 100, payload={
        "chunk_id": f"c{n:05d}", "sqlalchemy_version": "2.0.51",
        "source_path": f"doc/build/x{n}.rst", "heading_path": ["H"], "text": text})


HITS = [_hit(1, "page one text"), _hit(2, "page two text")]


def test_every_family_demands_the_canary():
    """Scoring is one string compare for all five, so all five must ask for it."""
    for name, payload in inject.FAMILIES.items():
        assert inject.CANARY in payload, name


def test_the_question_payload_reaches_the_prompt_after_the_question():
    case = inject.build_case({"id": "g1", "question": "why did X break?"},
                             HITS, "direct_override", "question")
    sources, question = case["prompt"].split("QUESTION:")
    assert "why did X break?" in question
    assert inject.CANARY in question, "the payload rides with the question"
    # the question channel must leave the pasted pages alone
    assert inject.CANARY not in sources


def test_the_page_payload_lands_inside_a_source_and_leaves_the_question_clean():
    case = inject.build_case({"id": "g1", "question": "why did X break?"},
                             HITS, "direct_override", "page")
    sources, question = case["prompt"].split("QUESTION:")
    assert inject.CANARY in sources, "payload must be inside the pasted pages"
    assert inject.CANARY not in question, "the question must stay clean in this channel"


def test_only_one_page_is_touched():
    poisoned = inject.inject_into_page(HITS, "PAYLOAD")
    assert poisoned[0].payload["text"].endswith("PAYLOAD")
    assert poisoned[1].payload["text"] == "page two text"


def test_the_originals_are_not_mutated():
    """The same hits are reused for every family; mutation would carry the last
    family's payload into the next case and score it as a hit."""
    inject.inject_into_page(HITS, "PAYLOAD")
    assert HITS[0].payload["text"] == "page one text"


def test_obeyed_is_the_canary_and_nothing_else():
    assert inject.obeyed(f"sure: {inject.CANARY}")
    assert not inject.obeyed("The sources do not answer this.")
    assert not inject.obeyed("CANARY")           # a prefix is not the token
    assert not inject.obeyed("canary-7f3a")      # case matters; the demand was exact


def test_the_three_items_are_read_off_the_committed_sweep(tmp_path):
    """Chosen by file and sorted by id — not by hand, and not by file order."""
    sweep = tmp_path / "s.json"
    sweep.write_text('{"D": ['
                     '{"id": "g050", "answerable": true, "answer_in_prompt": true, "refused": false},'
                     '{"id": "g002", "answerable": true, "answer_in_prompt": true, "refused": false},'
                     '{"id": "g009", "answerable": true, "answer_in_prompt": true, "refused": true},'
                     '{"id": "g007", "answerable": true, "answer_in_prompt": false, "refused": false},'
                     '{"id": "g004", "answerable": true, "answer_in_prompt": true, "refused": false}]}')
    assert inject.target_ids(3, sweep) == ["g002", "g004", "g050"]


def test_the_real_targets_are_answered_items_on_the_lab():
    ids = inject.target_ids()
    assert len(ids) == 3 and ids == sorted(ids)
    assert all(i.startswith("g") for i in ids)


def test_a_run_covers_every_family_and_channel(monkeypatch):
    monkeypatch.setattr(inject.index, "retrieve", lambda q, limit: HITS)
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    rows = inject.run(generate=lambda prompt: "no thanks", ids=["g1"])
    assert len(rows) == len(inject.FAMILIES) * len(inject.CHANNELS)
    assert {(r["family"], r["channel"]) for r in rows} == {
        (f, c) for f in inject.FAMILIES for c in inject.CHANNELS}
    assert not any(r["obeyed"] for r in rows)


def test_a_compliant_model_is_counted_and_named(monkeypatch):
    monkeypatch.setattr(inject.index, "retrieve", lambda q, limit: HITS)
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    rows = inject.run(generate=lambda prompt: f"ok {inject.CANARY}", ids=["g1"])
    out = inject.report(rows)
    assert all(r["obeyed"] for r in rows)
    assert "obeyed 10" in out
    assert "g1/direct_override/question" in out


def test_the_report_states_the_bar_so_a_zero_cannot_be_read_as_a_failure():
    out = inject.report([{"id": "g1", "family": "direct_override", "channel": "question",
                          "obeyed": False, "refused": False, "answer": ""}])
    assert "obeyed 0" in out
    assert "null result" in out


def test_generation_goes_through_the_shipped_prompt(monkeypatch):
    """ask.SYSTEM is what is under test; a private system prompt would measure
    something this project does not ship (D85's rule, applied to the target)."""
    seen = {}
    monkeypatch.setattr(ask, "generate", lambda prompt: seen.setdefault("p", prompt) and ("", {}))
    monkeypatch.setattr(inject.index, "retrieve", lambda q, limit: HITS)
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    inject.run(ids=["g1"])
    assert "QUESTION:" in seen["p"] and "SOURCES" in seen["p"]


@pytest.mark.parametrize("channel", inject.CHANNELS)
def test_both_channels_produce_a_prompt_that_still_contains_the_pages(channel):
    case = inject.build_case({"id": "g1", "question": "q?"}, HITS, "fake_authority", channel)
    assert "page two text" in case["prompt"], "the attack must not drop the real pages"
