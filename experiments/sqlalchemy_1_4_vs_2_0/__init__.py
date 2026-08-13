"""
The SQLAlchemy 1.4 → 2.0 experiment: an app written to be broken, and the
instruments used to measure how it breaks.

Run order, for someone opening this folder for the first time:

    seed.py        build issues.db — 200 issues from a fixed random seed, so
                   every count quoted in the docs is reproducible
    check.py       smoke test: force mapper configuration, so a broken
                   relationship fails here instead of at runtime

THE APP UNDER TEST — deliberately 1.4-style, with known 2.0 problems left in.

    models.py      six mapped classes: 1:M, M:M, association object, and a
                   self-referential blocks/blocked_by pair
    app.py         the query layer — Query.get(), engine.execute("..."), and
                   an N+1 left unoptimised on purpose

PROOFS BEHIND THE DOCS — each prints what the library actually does. Nothing
here asserts a number it did not measure; that rule is the whole point.

    explore.py     study/01-CONCEPTS.md §0-§13   relationship patterns, with live SQL
    states.py      study/01-CONCEPTS.md §14-§15  object states, identity map, expiry,
                                        lazy vs selectinload vs joinedload
    migration.py   study/02-MIGRATION-2.0.md §16-§21   nine sections, ending with
                                        cascade_backrefs and the measurement
                                        showing neither migration tool is a
                                        complete inventory

MIGRATION TOOLING — the three questions you ask in order.

    sweep.py       "what does 2.0 object to?"  — the warning sweep across
                   EVERY module, then occurrences collapsed into distinct
                   problems. app.py alone reports 5 of 1052 occurrences.
    patterns.py    the shared list of 1.4 patterns under test. Imported by
                   both modules below so a prediction and its verification
                   cannot drift apart.
    candidates.py  "which are worth testing?" — classifies each pattern by
                   which tool can see it. Predicts from 1.4; does not verify.
    verify_2_0.py  "what does real 2.0 do?" — runs the same patterns on 2.0
                   and reports the actual error. Needs a 2.0 environment:

                       uv run --no-project --with 'sqlalchemy==2.0.51' \\
                           python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0

                   `--stubs` emits the BREAKAGES.md skeleton instead.

Nothing in this package is imported by the Phase 1+ retrieval system. It exists
to produce BREAKAGES.md, which is the input to that work.
"""
