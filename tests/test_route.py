"""Phase 6 Step 3a — routing signals. No Qdrant, no model."""
import types

from rag import ask, route

REFUSE = ask.REFUSAL_OPENING + " this."


def out(answerable=True, present=True, answer="an answer [1]"):
    return {"answerable": answerable, "answer_in_prompt": present, "answer": answer}


def test_delivered_needs_the_page_AND_an_answer():
    """An answer without the page is not delivered, and neither is a
    refusal with the page."""
    assert route.delivered(out())
    assert not route.delivered(out(present=False))
    assert not route.delivered(out(answer=REFUSE))


def test_the_random_baseline_is_hypergeometric_not_binomial():
    """The first version re-drew its sample per failure: a binomial, whose tail
    at these numbers is 0.14 against the true 0.057. It made a marginal signal
    look like chance."""
    pmf = route.random_routing(100, 53, 30)
    assert abs(sum(pmf) - 1) < 1e-12
    assert round(sum(pmf[20:]), 4) == 0.0571


def test_router_A_routes_the_lowest_max_ce_and_splits_what_it_catches():
    signals = {"low": {"ce": [0.1, 0.2]}, "mid": {"ce": [0.5]}, "high": {"ce": [3.0]}}
    outcomes = {"low": out(present=False), "mid": out(answer=REFUSE), "high": out()}
    e = route.evaluate(signals, outcomes, budget=2)
    assert e["A"]["routed"] == ["low", "mid"]
    assert sorted(e["A"]["caught"]) == ["low", "mid"]
    assert e["A"]["caught_present"] == ["mid"]


def test_cascade_B_escalates_refusals_only_and_separates_page_present():
    signals = {i: {"ce": [1.0]} for i in "abcd"}
    outcomes = {"a": out(answer=REFUSE), "b": out(present=False, answer=REFUSE),
                "c": out(present=False), "d": out(answerable=False, present=False, answer=REFUSE)}
    b = route.evaluate(signals, outcomes, budget=1)["B"]
    assert b["present"] == ["a"] and b["absent"] == ["b"] and b["unanswerable"] == ["d"]
    assert b["unseen_failures"] == ["c"], "answered without the page: the cascade never sees it"


def test_join_check_names_any_item_whose_page_flag_differs_between_machines():
    """The join is only legitimate because retrieval reproduces; one
    disagreement and no router result may be printed."""
    golden = {"g": {"answer_chunks": ["c1"]}}
    chunks = {"c1": {"source_path": "x", "heading_path": [], "text": "t"}}
    outcomes = {"g": out(present=True)}
    assert route.join_check({"g": {"hits": ["c1"]}}, outcomes, golden, chunks) == []
    assert route.join_check({"g": {"hits": ["zz"]}}, outcomes, golden, chunks) == ["g"]


def test_compute_signals_keeps_the_five_shipped_pages_and_their_scores():
    pts = [types.SimpleNamespace(payload={"chunk_id": c}) for c in ("c1", "c2")]
    rows = route.compute_signals([{"id": "g", "question": "q"}],
                                 retrieve=lambda q: pts, ce=lambda q, p: [0.1234567, 2.0])
    assert rows == [{"id": "g", "hits": ["c1", "c2"], "ce": [0.123457, 2.0]}]
