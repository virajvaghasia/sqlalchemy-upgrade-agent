"""Days 8–9 gate: a test that is red on purpose.

This file must never merge to main. The point is GitHub refusing the PR
because the required check named `tests` fails. See phases/PHASE-0.md Days 8–9.

A green CI on this branch would mean the gate is broken, not that the code is good.
"""


def test_ci_gate_deliberately_fails():
    assert False, (
        "Days 8–9 gate: this failure is the point. "
        "If this PR can merge, branch protection is advisory only."
    )
