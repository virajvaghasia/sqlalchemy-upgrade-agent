"""Phase 6, Step 3a — before pricing a router, can it tell which questions to send?

    uv run python -m rag.route --signals     # needs Qdrant + the reranker; writes the signals file
    uv run python -m rag.route --report      # no model: reads committed files only

IN PLAIN TERMS

A router sends some questions to a stronger (paid) model and keeps the rest on
the free local one. That only saves money if it sends the RIGHT questions --
the ones the local pipeline would have failed -- and only helps if the strong
model could actually do better on them.

**The second half is the one people skip.** Our pipeline fails a question in
two unrelated ways, and a stronger generator can only fix one of them:

    page ABSENT   retrieval never put the answer in the prompt. A stronger model
                  gets the same five wrong pages. It can only answer from memory,
                  which is g065's fabrication, not a fix.
    page PRESENT  the page was there and the local model refused it (D72's
                  over-refusals). A stronger model plausibly fixes these.

WHAT IS JOINED, AND WHY THAT IS ALLOWED

Outcomes come from the LAB's Round 16 run of the shipped prompt (`D`, 38/91
delivered), because `D95` says quoted numbers are the lab's. The cross-encoder
signals are recomputed wherever `--signals` runs. Joining the two is only valid
because retrieval is identical across machines (`D83`) -- so `report()` checks
that first, item by item, and refuses to print a router result if a single
page-present flag disagrees.

TWO DESIGNS

    A  predictive   before generating, route the BUDGET share of questions whose
                    best shipped page scores lowest on the cross-encoder
    B  cascade      generate locally; escalate only if the answer is a refusal

Rules for both were written into phases/PHASE-6.md before the numbers (`D98`).
"""

from __future__ import annotations

import json
import sys
from math import comb

from rag import ask, judge, score

OUTCOMES = judge.DELIVERABLES / "prompt-sweep-round16.Linux-x86_64.json"
BUDGET = 30          # of 100 questions -- the pre-registered share for design A
CAPTURE_BAR = 27     # of the 53 local failures -- pre-registered pass line


def signals_path():
    from rag import faithful
    return judge.DELIVERABLES / f"route-signals-phase6.{faithful.machine()}.json"


def compute_signals(items, retrieve=None, ce=None) -> list[dict]:
    """The five shipped pages per question and the cross-encoder score of each.

    Injected `retrieve`/`ce` keep this testable without Qdrant or a model.
    """
    if retrieve is None:
        from rag import index
        retrieve = lambda q: index.retrieve(q, limit=ask.DEFAULT_K)
    if ce is None:
        from rag import rerank
        ce = rerank.ce_scores
    out = []
    for it in items:
        points = retrieve(it["question"])
        out.append({"id": it["id"], "hits": [p.payload["chunk_id"] for p in points],
                    "ce": [round(s, 6) for s in ce(it["question"], points)]})
    return out


def delivered(row: dict) -> bool:
    """D72's definition: the page reached the prompt AND the model answered."""
    return row["answer_in_prompt"] and not ask.refused(row["answer"])


def join_check(signals: dict, outcomes: dict, golden: dict, chunks: dict) -> list[str]:
    """Items whose page-present flag differs between the two machines. Must be empty."""
    return [i for i, r in outcomes.items()
            if r["answerable"] and i in signals
            and (score.rank_of_first_hit(signals[i]["hits"], golden[i], chunks) is not None)
            != r["answer_in_prompt"]]


def random_routing(n_items: int, n_failures: int, budget: int) -> list[float]:
    """P(a router that picks `budget` questions at random catches exactly k failures).

    Exact hypergeometric: `budget` drawn WITHOUT replacement from `n_items`, of
    which `n_failures` are failures. Computed, not simulated. A first version
    simulated it and re-drew the sample once per failure, which is a binomial
    with a fatter tail (P(>= 20) = 0.14 against the true 0.057), and made a
    marginal signal look like chance. See D98.
    """
    return [comb(n_failures, k) * comb(n_items - n_failures, budget - k) / comb(n_items, budget)
            for k in range(budget + 1)]


def _quantile(pmf: list[float], q: float) -> int:
    total = 0.0
    for k, pk in enumerate(pmf):
        total += pk
        if total >= q:
            return k
    return len(pmf) - 1


def evaluate(signals: dict, outcomes: dict, budget: int = BUDGET) -> dict:
    answerable = [i for i, r in outcomes.items() if r["answerable"]]
    failures = [i for i in answerable if not delivered(outcomes[i])]
    present_failures = [i for i in failures if outcomes[i]["answer_in_prompt"]]

    routed = set(sorted(signals, key=lambda i: (max(signals[i]["ce"]), i))[:budget])
    a_caught = [i for i in failures if i in routed]

    pmf = random_routing(len(signals), len(failures), budget)

    escalated = [i for i, r in outcomes.items() if ask.refused(r["answer"])]
    b_answerable = [i for i in escalated if outcomes[i]["answerable"]]
    return {
        "n_items": len(outcomes), "answerable": len(answerable), "failures": failures,
        "present_failures": present_failures,
        "A": {"routed": sorted(routed), "caught": a_caught,
              "caught_present": [i for i in a_caught if outcomes[i]["answer_in_prompt"]],
              "wasted": [i for i in routed if i in answerable and i not in failures],
              "unanswerable": [i for i in routed if not outcomes[i]["answerable"]],
              "random_median": _quantile(pmf, 0.5),
              "random_p95": _quantile(pmf, 0.95),
              "p_random_at_least": sum(pmf[len(a_caught):])},
        "B": {"escalated": escalated,
              "present": [i for i in b_answerable if outcomes[i]["answer_in_prompt"]],
              "absent": [i for i in b_answerable if not outcomes[i]["answer_in_prompt"]],
              "unanswerable": [i for i in escalated if not outcomes[i]["answerable"]],
              "unseen_failures": [i for i in failures if i not in escalated]},
    }


def report(e: dict) -> None:
    a, b = e["A"], e["B"]
    n_fail, n_pf = len(e["failures"]), len(e["present_failures"])
    print(f"local pipeline (lab, Round 16, prompt D): {e['answerable'] - n_fail}/{e['answerable']} "
          f"delivered, {n_fail} failures, {n_pf} of them with the page PRESENT")
    print()
    verdict = "PASS" if len(a["caught"]) >= CAPTURE_BAR else "FAIL"
    print(f"A  predictive, route {BUDGET} lowest max-CE")
    print(f"   failures caught      {len(a['caught'])} of {n_fail}   bar {CAPTURE_BAR}  -> {verdict}")
    print(f"   random routing       median {a['random_median']}, 95th percentile {a['random_p95']}, "
          f"P(>= {len(a['caught'])}) = {a['p_random_at_least']:.3f}  (exact hypergeometric)")
    print(f"   caught, page present {len(a['caught_present'])} of {n_pf}")
    print(f"   routed but delivered locally {len(a['wasted'])}, routed unanswerable {len(a['unanswerable'])}")
    print()
    print("B  cascade, escalate on refusal")
    print(f"   escalated            {len(b['escalated'])} of {e['n_items']}")
    print(f"   answerable, page present {len(b['present'])} of {n_pf}   page absent {len(b['absent'])}")
    print(f"   unanswerable escalated   {len(b['unanswerable'])}")
    print(f"   failures never escalated {len(b['unseen_failures'])}  (answered without the page)")


def main() -> None:
    argv = sys.argv[1:]
    golden = {i["id"]: i for i in score.load_golden()}
    if "--signals" in argv:
        rows = compute_signals(list(golden.values()))
        signals_path().write_text(json.dumps(rows, indent=1) + "\n")
        print(f"saved {len(rows)} rows to {signals_path().name}")
        return
    path = judge.DELIVERABLES / "route-signals-phase6.Darwin-arm64.json"
    signals = {r["id"]: r for r in json.loads(path.read_text())}
    outcomes = {r["id"]: r for r in json.loads(OUTCOMES.read_text())["D"]}
    if "--no-join-check" not in argv:
        mismatches = join_check(signals, outcomes, golden, score.load_chunks())
        if mismatches:
            sys.exit(f"retrieval differs between machines on {mismatches}; "
                     "the join is not valid (D83) and no router result is printed")
    report(evaluate(signals, outcomes))


if __name__ == "__main__":
    main()
