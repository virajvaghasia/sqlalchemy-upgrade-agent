"""
candidates.py — a shortlist of 1.4 patterns worth TESTING for BREAKAGES.md.

READ THIS BEFORE USING THE OUTPUT.

This does NOT produce breakage entries. It produces *candidates*: 1.4 patterns
that the library, right now, either warns about or refuses. A candidate becomes
a BREAKAGES.md entry only after you have written it into real code, run it on
real 2.0, hit the real error, and fixed it — that is what PHASE-0 means by
"breakages he personally caused, hit, and fixed".

The distinction is not bureaucratic. CLAUDE.md's design notes call an
auto-generated golden set "grading your own homework with your own answer key",
and MIGRATION-2.0.md §21 spells out why a wrong entry costs more than a missing
one. A list generated here and pasted into BREAKAGES.md would be exactly that
failure, dressed up as measurement.

What this file is genuinely good for: it stops you guessing which patterns are
worth putting into the app before you upgrade. Every row below is a real result
from 1.4.52, not a recollection of the migration guide.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.candidates
"""

import json
import pathlib
import warnings

from sqlalchemy.util import deprecations

from experiments.sqlalchemy_1_4_vs_2_0 import patterns


def classify(case):
    guidance = []

    def run(**kwargs):
        engine, session = patterns.fixture(**kwargs)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                case(engine, session)
                outcome = "ok"
            except Exception as exc:
                outcome = type(exc).__name__
        classes = sorted({w.category.__name__ for w in caught
                          if "In20" in w.category.__name__ or "LegacyAPI" in w.category.__name__})
        msgs = [" ".join(str(w.message).split()) for w in caught
                if "In20" in w.category.__name__ or "LegacyAPI" in w.category.__name__]
        guidance.clear()
        guidance.extend(msgs)
        try:
            session.close()
        except Exception:
            pass
        return classes, outcome

    deprecations.SQLALCHEMY_WARN_20 = True
    try:
        warned, _ = run()
    finally:
        deprecations.SQLALCHEMY_WARN_20 = False
    said = list(guidance)
    _, under_20 = run(future=True)
    guidance[:] = said
    return ",".join(c.replace("Warning", "") for c in warned) or "—", under_20, list(guidance)


print("=" * 88)
print("CANDIDATES to test — not breakages. See this file's docstring.")
print("=" * 88)
print()
print(f"  {'1.4 pattern':<38}{'WARN_20':<14}{'future=True':<26}{'why it is a candidate'}")
print(f"  {'-' * 38}{'-' * 14}{'-' * 26}{'-' * 22}")

tally = {"both": 0, "warn-only": 0, "silent": 0, "not a breakage": 0}
tiers = {}
current = None
for group, label, _source, case in patterns.all_cases():
    if group != current:
        current = group
        print(f"\n  {group.upper()}")
    warned, under_20, guide = classify(case)
    breaks = under_20 != "ok"
    # LegacyAPI and Moved are real migration items but not breakages: the
    # code keeps working. Only Removed-tier or an actual failure counts.
    removed = "RemovedIn20" in warned
    if removed and breaks:
        verdict, key = "both tools agree", "both"
    elif removed:
        verdict, key = "sweep only - flag misses it", "warn-only"
    elif breaks:
        verdict, key = "SILENT to the sweep", "silent"
    else:
        verdict, key = "not a breakage (works in 2.0)", "not a breakage"
    tally[key] += 1
    tiers[label] = {"warns": warned, "future": under_20, "verdict": verdict,
                    "guidance": guide}
    print(f"  {label:<38}{warned:<14}{under_20:<26}{verdict}")

total = tally["both"] + tally["warn-only"] + tally["silent"]
print()
print("=" * 88)
print(f"  {total} candidates worth testing, {tally['not a breakage']} rejected as non-breakages.")
print("=" * 88)
print(f"    {tally['both']:>3}  caught by BOTH the sweep and future=True")
print(f"    {tally['warn-only']:>3}  warned by the sweep, but future=True runs them —")
print( "         construction-time removals the engine never sees")
print(f"    {tally['silent']:>3}  NO warning at all — only running the code finds these")
print()
print("  The last group is the reason a swept list is not an inventory, and the")
print("  middle group is the reason a green future=True run is not a clearance.")
print()
print("  NEXT STEP, and it is not automatable: put the ones you care about into")
print("  real code, upgrade, hit the error, fix it, and write down what actually")
print("  happened. A row here is a hypothesis. BREAKAGES.md holds results.")

# Persist the measured tiers so verify_2_0.py can quote them. It runs on 2.0,
# where RemovedIn20Warning does not exist, so it cannot measure this itself —
# and hardcoding the answer there would be exactly the asserted-number habit
# CLAUDE.md forbids.
TIERS_PATH = pathlib.Path(__file__).with_name("tiers.json")
TIERS_PATH.write_text(json.dumps(tiers, indent=2, sort_keys=True) + "\n")
print()
print(f"  Tiers written to {TIERS_PATH.name} — verify_2_0.py --stubs reads it.")
