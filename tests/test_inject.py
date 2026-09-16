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
    rows = inject.run(generate=lambda system, prompt: "no thanks", ids=["g1"])
    assert len(rows) == len(inject.FAMILIES) * len(inject.CHANNELS)
    assert {(r["family"], r["channel"]) for r in rows} == {
        (f, c) for f in inject.FAMILIES for c in inject.CHANNELS}
    assert not any(r["obeyed"] for r in rows)


def test_a_compliant_model_is_counted_and_named(monkeypatch):
    monkeypatch.setattr(inject.index, "retrieve", lambda q, limit: HITS)
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    rows = inject.run(generate=lambda system, prompt: f"ok {inject.CANARY}", ids=["g1"])
    out = inject.report(rows)
    assert all(r["obeyed"] for r in rows)
    assert "obeyed 10" in out
    assert "g1/direct_override/question" in out


def test_the_report_prints_refused_beside_obeyed(): 
    """D109: refusal_hijack scored 0 obeyed and still made the system decline three
    questions it answers. A report that hides `refused` scores that attack as a win."""
    out = inject.report([{"id": "g1", "family": "refusal_hijack", "channel": "question",
                          "obeyed": False, "refused": True, "answer": "The sources do not answer this."}])
    assert "obeyed 0" in out and "refused 1" in out
    assert "DECLINE" in out


def test_generation_goes_through_the_shipped_prompt(monkeypatch):
    """ask.SYSTEM is what is under test; a private system prompt would measure
    something this project does not ship (D85's rule, applied to the target)."""
    seen = {}
    monkeypatch.setattr(inject.cp, "generate",
                        lambda system, prompt: seen.setdefault("call", (system, prompt)) and "")
    monkeypatch.setattr(inject.index, "retrieve", lambda q, limit: HITS)
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    inject.run(ids=["g1"])
    system, prompt = seen["call"]
    assert system == ask.SYSTEM, "the control arm must attack the SHIPPED system prompt"
    assert "QUESTION:" in prompt and "SOURCES" in prompt


@pytest.mark.parametrize("channel", inject.CHANNELS)
def test_both_channels_produce_a_prompt_that_still_contains_the_pages(channel):
    case = inject.build_case({"id": "g1", "question": "q?"}, HITS, "fake_authority", channel)
    assert "page two text" in case["prompt"], "the attack must not drop the real pages"


def test_every_arm_is_attacked_and_carries_its_own_system_prompt(monkeypatch):
    """Step 1 compares arms in ONE sitting (D54), so the control is re-run beside
    the candidates rather than read off Round 25's file."""
    from rag import fence
    seen = []
    monkeypatch.setattr(inject.cp, "generate",
                        lambda system, prompt: seen.append((system, prompt)) or "no")
    monkeypatch.setattr(inject.index, "retrieve", lambda q, limit: HITS)
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    rows = inject.run(ids=["g1"], arms=["shipped", "fence_both"])
    assert {r["arm"] for r in rows} == {"shipped", "fence_both"}
    assert len(rows) == 2 * len(inject.FAMILIES) * len(inject.CHANNELS)
    systems = {s for s, _ in seen}
    assert systems == {ask.SYSTEM, fence.system_for("fence_both")}


def test_retrieval_runs_once_per_question_not_once_per_arm(monkeypatch):
    """Re-retrieving per arm would let an index difference read as a prompt effect."""
    calls = []
    monkeypatch.setattr(inject.index, "retrieve",
                        lambda q, limit: calls.append(q) or HITS)
    monkeypatch.setattr(inject.cp, "generate", lambda system, prompt: "no")
    monkeypatch.setattr(inject, "golden_items",
                        lambda: {"g1": {"id": "g1", "question": "q?"}})
    inject.run(ids=["g1"], arms=["shipped", "fence_user", "fence_both"])
    assert len(calls) == 1


def test_compare_pairs_by_attempt_and_names_what_broke():
    """D61: flipped attempts, not a difference of two averages."""
    def row(arm, family, obeyed):
        return {"id": "g1", "family": family, "channel": "question", "arm": arm,
                "obeyed": obeyed, "refused": False, "answer": ""}
    rows = [row("shipped", "direct_override", True), row("shipped", "exfiltration", False),
            row("fence_user", "direct_override", False), row("fence_user", "exfiltration", True)]
    out = inject.compare(rows)
    assert "fixed" in out and "broken" in out
    assert "g1/exfiltration/question" in out, "a newly obeyed attempt must be named"
