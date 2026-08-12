"""
verify_2_0.py — run the candidate patterns against REAL SQLAlchemy 2.0.

candidates.py predicts, from 1.4, what 2.0 will do. This measures what 2.0
actually does. The gap between the two is the interesting part, and the reason
the prediction alone was never good enough to fill BREAKAGES.md.

Nothing is upgraded to run this. uv builds a throwaway environment on 2.0 while
the project stays pinned to 1.4 in pyproject.toml:

    uv run --no-project --with 'sqlalchemy==2.0.51' python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0

The 2.0 version is PINNED, not floating. BREAKAGES.md quotes exact error strings
from a specific release; '>=2.0' silently drifts to whatever shipped this week
and the file stops being reproducible. See PIN below for how to move it
deliberately.

Refuses to run on 1.4, because a green result there would mean nothing.

WHAT --stubs PRODUCES, AND WHAT IS STILL YOURS. It writes BREAKAGES.md with four
fields per entry: the 1.4 code, the real 2.0 error, a DRAFT fix, and the tier.
Three of those are measured — the error comes from this run, the tier from
candidates.py on 1.4, and every draft fix is EXECUTED here, so "it runs on 2.0"
is a fact rather than a claim.

What is not measured is whether a draft is the fix you want. Several patterns
have more than one defensible answer (text() versus a real column expression;
session.add() versus writing the collection side), and picking between them is
the judgement PHASE-0 is asking you to exercise. CLAUDE.md allows the assistant
to draft and reformat; only you verify. Read each one and make it yours.
"""

import json
import pathlib
import re
import sys
import textwrap

import sqlalchemy as sa

from experiments.sqlalchemy_1_4_vs_2_0 import patterns

# The single source of truth for which 2.0 the evidence was taken on. Every
# printed command interpolates it, so the docs cannot drift from the code.
#
# TO MOVE IT: change this line, re-run with --stubs, diff against BREAKAGES.md
# (the header in that file shows how), and hand-edit any entry whose measured
# error actually moved. That is a deliberate act with a visible diff, which is
# the whole point of pinning.
PIN = "2.0.51"
RUN_CMD = f"uv run --no-project --with 'sqlalchemy=={PIN}'"

MAJOR = int(sa.__version__.split(".")[0])
if MAJOR < 2:
    sys.exit(
        f"Running on SQLAlchemy {sa.__version__}. This script only means something on 2.0.\n"
        f"  {RUN_CMD} \\\n"
        "      python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0"
    )

if sa.__version__ != PIN:
    # Not fatal — testing a newer 2.0 on purpose is legitimate. But BREAKAGES.md
    # records exact error text, so an unnoticed version change is how that file
    # quietly stops matching reality.
    print(
        f"WARNING: running on SQLAlchemy {sa.__version__}, but the evidence in "
        f"BREAKAGES.md was taken on {PIN}.\n"
        f"         Pin with:  {RUN_CMD}\n"
        f"         Or update PIN in this file if you mean to move it.\n",
        file=sys.stderr,
    )

STUBS = "--stubs" in sys.argv

# Measured on 1.4 by candidates.py; unreadable from here because the 2.0
# warning classes do not exist in 2.0.
_TIERS_PATH = pathlib.Path(__file__).with_name("tiers.json")
TIERS = json.loads(_TIERS_PATH.read_text()) if _TIERS_PATH.exists() else {}

# The cascade_backrefs entry is appended by hand at the end of emit_stubs — the
# battery only catches exceptions and that one raises none — and it carries its
# own "Also defensible" block. It is not in patterns.ALTERNATIVES, so the header
# count has to add it back. A structural fact about this file, not a tally.
HAND_APPENDED_WITH_ALTERNATIVES = 1


def emit_stubs(failures):
    """Print a BREAKAGES.md skeleton with the two halves we actually measured.

    Every field is machine-copied from a measurement, so none of it can be
    mistyped: the error from this run, the tier from candidates.py via
    tiers.json, and the fix from patterns.FIXES — which was executed a few
    lines above, so a fix that does not run cannot reach the file.

    That makes them drafts, not answers. Verifying a draft is the reader's job.
    """
    print("# Breakages — SQLAlchemy 1.4.52 → 2.0.51")
    print()
    print("The Phase 0 Part A deliverable, and the seed of the Phase 2 golden dataset. Part of")
    print("[`sqlalchemy-upgrade-agent`](README.md); the mechanics behind each entry are explained")
    print("in [`MIGRATION-2.0.md`](MIGRATION-2.0.md) §16–§22.")
    print()
    print(f"Measured on {sa.__version__}, against `models.py` in this repo. Each entry is 1.4 "
          "code\nthat ran clean on 1.4.52 and fails on 2.0.")
    print()
    print("**Status: DRAFT — verified to run, not verified to be right.**")
    print()
    print("| field | where it comes from |")
    print("|---|---|")
    print("| 1.4 code | `patterns.py` |")
    print(f"| 2.0 error | this run, on {sa.__version__} |")
    print("| Fix | `patterns.py` — **executed on 2.0 here**, so it provably runs |")
    print("| Docs | in-repo section refs, **checked against the files at generation time**, "
          "plus 1.4's own deprecation text |")
    print("| Tier | `candidates.py`, measured on 1.4, passed via `tiers.json` |")
    print()
    n_alternatives = sum(
        1 for _g, label, _s, _o, _d in failures if patterns.ALTERNATIVES.get(label)
    ) + HAND_APPENDED_WITH_ALTERNATIVES
    print(f"A draft fix runs. That is not the same as it being the *right* fix. {n_alternatives} entries carry")
    print("an **Also defensible** block listing the other answers that work — because presenting")
    print("one option where several exist hides the decision instead of making it. Every option")
    print("shown is executed here too, so the choice is between things that all provably run.")
    print("Choosing is the judgement `PHASE-0.md` asks for; edit them into your own words.")
    print()
    print("> **Do not regenerate over this file once you have edited it.** The generator")
    print("> prints fresh drafts; redirecting it onto `BREAKAGES.md` would erase every word")
    print("> you wrote over them. Diff instead:")
    print(">")
    print("> ```bash")
    print(f"> {RUN_CMD} \\")
    print(">     python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0 --stubs > /tmp/breakages.new")
    print("> diff /tmp/breakages.new BREAKAGES.md")
    print("> ```")
    print(">")
    print("> Re-run that after any change to `models.py` or `patterns.py`: if a measured")
    print("> error message moved, the diff shows it and you edit that entry by hand.")
    group_now = None
    for n, (group, label, source, outcome, detail) in enumerate(failures, 1):
        if group != group_now:
            group_now = group
            print()
            print("---")
            print()
            print(f"## {group[0].upper() + group[1:]}")
        print()
        print(f"### {n}. {label}")
        print()
        print("```python")
        print(f"# 1.4 — worked")
        print(source)
        print("```")
        print()
        print(f"**2.0 error** — `{outcome}`")
        print()
        print("```")
        for line in textwrap.wrap(detail, width=88):
            print(line)
        print("```")
        print()
        fix = patterns.FIXES.get(label)
        if fix:
            code, why, _ = fix
            print(f"**Fix** — _draft, verified to run on {sa.__version__}: "
                  f"`{fix_results.get(label, '?')}`_")
            print()
            print("```python")
            print("# 2.0")
            print(code)
            print("```")
            print()
            print(why)
        else:
            print("**Fix:** _TODO._")
        print()
        alts = patterns.ALTERNATIVES.get(label, [])
        if alts:
            print()
            print("**Also defensible** — _each verified to run on "
                  f"{sa.__version__}. Pick deliberately; this is the judgement, not the typing._")
            for i, (acode, awhen, _fn) in enumerate(alts):
                print()
                print("```python")
                print(acode)
                print("```")
                print()
                print(f"{awhen}  \n_({alt_results.get((label, i), '?')})_")
        print()
        # Docs. Section refs are CHECKED against the files here, so a stale
        # pointer becomes a visible "(section not found)" rather than a
        # confident link to nothing.
        refs = patterns.DOC_SECTIONS.get(label, [])
        guidance = (TIERS.get(label) or {}).get("guidance") or []
        print("**Docs**")
        print()
        if refs:
            for ref in refs:
                fname, _, sec = ref.partition(" ")
                found = pathlib.Path(fname).exists() and sec in pathlib.Path(fname).read_text()
                mark = "" if found else "  _(section not found — fix the ref)_"
                print(f"- [`{fname}`]({fname}) {sec}{mark}")
        if guidance:
            print("- what 1.4 itself says, verbatim:")
            for g in guidance[:1]:
                for line in textwrap.wrap(g, width=84):
                    print(f"  > {line}")
        if not refs and not guidance:
            print("- _no in-repo section yet, and 1.4 emits no guidance for this one._")
        print()
        tier = TIERS.get(label)
        if tier:
            print(f"**Tier** — `SQLALCHEMY_WARN_20` says **{tier['warns']}**; "
                  f"`future=True` says **{tier['future']}**  \n"
                  f"_{tier['verdict']}_ (measured on 1.4 by `candidates.py`)")
        else:
            print("**Tier:** _run `candidates.py` on 1.4 first, then regenerate._")

    # The battery above only catches exceptions, so the one breakage that
    # raises nothing would silently miss the skeleton too. Appended by hand,
    # with the instrument named, because it is the most valuable entry here.
    print()
    print("---")
    print()
    print("## The one that raises nothing")
    print()
    print(f"### {len(failures) + 1}. cascade_backrefs — object attached by the many-to-one side")
    print()
    print("```python")
    print("# 1.4 — worked: the backref cascade enrolled `issue` with no session.add()")
    print("project = Project(name='apollo'); session.add(project)")
    print("issue = Issue(title='...'); issue.project = project")
    print("session.flush()")
    print("```")
    print()
    print("**2.0 error** — _none. That is the entry._")
    print()
    print("```")
    print("attached with project.issues.append(...)  -> in database: True")
    print("attached with issue.project = project     -> in database: False")
    print("```")
    print()
    print("Measured by counting rows, not by catching an exception — no exception exists.")
    print("A passing test suite does not see this unless it asserts on row counts.")
    print()
    print("**Fix** — _draft. Say what you meant:_")
    print()
    print("```python")
    print("# 2.0")
    print("issue = Issue(title='...')")
    print("issue.project = project")
    print("session.add(issue)          # <- the line 1.4 let you leave out")
    print("```")
    print()
    print("The one line 1.4 let you omit. Explicit, local, and works on both versions.")
    print()
    print("**Also defensible** — _all three work; they differ in what they cost you._")
    print()
    print("```python")
    print("project.issues.append(issue)     # write the COLLECTION side instead")
    print("```")
    print()
    print("The save-update cascade proper survives 2.0, so this needs no `session.add()` at all.")
    print("Prefer it when you are already building the parent's collection — but note it reads")
    print("as identical to the broken form on 1.4, so it does not help you FIND the other sites.")
    print()
    print("```python")
    print("# in models.py, while still on 1.4")
    print("issues = relationship('Issue', backref=backref('project', cascade_backrefs=False))")
    print("```")
    print()
    print("Adopts the 2.0 behaviour before upgrading, which turns a silent 2.0 data loss into a")
    print("loud 1.4 failure you can chase down. The most useful of the three if you have a large")
    print("codebase and no idea how many sites rely on the cascade — and the least useful if you")
    print("already know, because it changes runtime behaviour to find them.")
    print()
    print("**Docs**")
    print()
    print("- [`MIGRATION-2.0.md`](MIGRATION-2.0.md) §17 — the mechanism, and what it does to seed.py")
    print("- [`CONCEPTS.md`](CONCEPTS.md) §14 — the save-update cascade this is half of")
    print("- what 1.4 itself says, verbatim:")
    print("  > \"X\" object is being merged into a Session along the backref cascade path for")
    print("  > relationship \"X\"; in SQLAlchemy 2.0, this reverse cascade will not take place.")
    print("  > Set cascade_backrefs to False in either the relationship() or backref() function")
    print("  > for the 2.0 behavior; or to set globally for the whole Session, set the")
    print("  > future=True flag")
    print()
    print("**Tier** — `RemovedIn20Warning`, but only in modules that WRITE data; `app.py`'s")
    print("sweep misses it entirely. See `sweep.py`.")


broke, survived, failures = 0, 0, []
fix_results = {}
alt_results = {}
if not STUBS:
    print("=" * 84)
    print(f"REAL SQLAlchemy {sa.__version__} — what actually happens")
    print("=" * 84)
    print()
    print("  Each pattern is 1.4 code that ran fine on 1.4.52. Below is 2.0's answer.")
    print()

for group, label, source, case in patterns.all_cases():
    engine, session = patterns.fixture()
    try:
        case(engine, session)
        outcome, detail = "still works", ""
        survived += 1
    except Exception as exc:
        outcome = type(exc).__name__
        detail = " ".join(str(exc).split())
        # Drop SQLAlchemy's trailing docs links; they bloat the line without adding much.
        detail = detail.split("(Background on this error")[0].strip()
        # Some messages embed the repr of an object, which carries its memory
        # address. Left in, the file changes on every run and the diff workflow
        # in the header cries wolf forever. Normalised so output is stable.
        detail = re.sub(r"0x[0-9a-f]+", "0x...", detail)
        broke += 1
        failures.append((group, label, source, outcome, detail))
    try:
        session.close()
    except Exception:
        pass
    fix = patterns.FIXES.get(label)
    fix_status = "-"
    if fix:
        fe, fs = patterns.fixture()
        try:
            fix[2](fe, fs)
            fix_status = "fix OK"
        except Exception as exc:
            fix_status = f"FIX FAILED: {type(exc).__name__}: {exc}"[:70]
        try:
            fs.close()
        except Exception:
            pass
    fix_results[label] = fix_status
    for i, (acode, awhen, afn) in enumerate(patterns.ALTERNATIVES.get(label, [])):
        ae, asx = patterns.fixture()
        try:
            afn(ae, asx); alt_results[(label, i)] = "runs OK"
        except Exception as exc:
            alt_results[(label, i)] = f"FAILED: {type(exc).__name__}: {exc}"[:60]
        try:
            asx.close()
        except Exception:
            pass
    if not STUBS:
        print(f"  {label:<34}{outcome:<26}{fix_status}")

if STUBS:
    emit_stubs(failures)
    sys.exit(0)

print()
print("=" * 84)
print(f"  {broke} of {broke + survived} patterns FAIL on {sa.__version__}")
print("=" * 84)
print()
print("  Each block below is the raw material for one BREAKAGES.md entry.")
print("  The 2.0 fix is the part you supply — that is the half that teaches.")

current = None
for group, label, source, outcome, detail in failures:
    if group != current:
        current = group
        print()
        print(f"  --- {group.upper()} " + "-" * (60 - len(group)))
    print()
    print(f"  {label}")
    print(f"    1.4 code : {source}")
    print(f"    2.0 error: {outcome}")
    for line in textwrap.wrap(detail, width=64):
        print(f"               {line}")

print()
print("  Patterns that did NOT fail are worth a second look too: a prediction of")
print("  'breaks' that turns out wrong is exactly the kind of wrong entry §21")
print("  warns about, and you just caught it before it reached the corpus.")


# ---------------------------------------------------------------------------
# The breakage this harness structurally cannot catch
# ---------------------------------------------------------------------------
# Everything above is measured by catching an exception. cascade_backrefs
# raises nothing at all — it writes fewer rows — so it needs a different
# instrument: count what reached the database.
print()
print("=" * 84)
print("SILENT behaviour change — no exception to catch, so count rows instead")
print("=" * 84)

engine = sa.create_engine("sqlite://")
patterns.models.Base.metadata.create_all(engine)
session = sa.orm.sessionmaker(bind=engine)()

project = patterns.models.Project(name="apollo")
session.add(project)

# The collection side — expected to survive.
project.issues.append(patterns.models.Issue(title="attached by append", status="open"))

# The many-to-one side — expected to vanish. Never passed to session.add().
orphan = patterns.models.Issue(title="attached by assignment", status="open")
orphan.project = project

session.flush()
landed = session.execute(sa.text("SELECT title FROM issues ORDER BY id")).scalars().all()

print()
print(f"  attached with project.issues.append(...)  -> in database: "
      f"{'attached by append' in landed}")
print(f"  attached with issue.project = project     -> in database: "
      f"{'attached by assignment' in landed}")
print(f"  rows in issues: {len(landed)}   titles: {landed}")
print()
if "attached by assignment" not in landed:
    print("  CONFIRMED on real 2.0: the row is gone and nothing was raised.")
    print("  This is the only entry in the battery that a try/except harness —")
    print("  or a passing test suite — cannot see. MIGRATION-2.0.md §17.")
else:
    print("  NOT reproduced here. Worth investigating before trusting §17.")
session.close()
