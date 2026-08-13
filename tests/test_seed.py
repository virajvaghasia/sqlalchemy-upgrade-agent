"""The seed is deterministic, idempotent, and does not eat existing data.

Every measured number in this repo — the 204-query N+1, the row counts in
PRACTICE-APP.md, the before/after in study/02-MIGRATION-2.0.md — assumes seeding the same
data twice produces the same database. Nothing enforced that until now.
"""

from sqlalchemy import create_engine, func, select

from experiments.sqlalchemy_1_4_vs_2_0 import models, seed as seed_mod

# The counts study/03-PRACTICE-APP.md publishes. If a change to seed.py moves any of
# them, the doc is wrong and this test says so before a reader finds out.
EXPECTED_COUNTS = {
    "users": 5,
    "projects": 3,
    "labels": 8,
    "issues": 200,
    "comments": 710,
    "issue_labels": 387,
    "issue_assignments": 303,
    "issue_blocks": 60,
}


def _counts(engine):
    # select(func.count()).select_from(t), not t.count(): the latter was removed
    # in 1.4, and this form is the one that also runs on 2.0 — the tests should
    # not themselves be written in the style BREAKAGES.md documents as broken.
    with engine.connect() as conn:
        return {
            name: conn.execute(select(func.count()).select_from(table)).scalar()
            for name, table in models.Base.metadata.tables.items()
        }


def test_seed_produces_the_documented_counts(engine):
    session = seed_mod.seed(engine)
    session.close()
    assert _counts(engine) == EXPECTED_COUNTS


def test_seed_is_deterministic(tmp_path):
    """Two fresh databases, same fixed RANDOM_SEED, identical content.

    Not just identical counts — identical titles in identical order. A seed that
    produced the right number of different rows would still invalidate every
    before/after comparison in the docs.
    """
    titles = []
    for name in ("a.db", "b.db"):
        eng = create_engine(f"sqlite:///{tmp_path / name}")
        seed_mod.seed(eng).close()
        with eng.connect() as conn:
            titles.append(
                [r[0] for r in conn.execute(
                    models.Issue.__table__.select().order_by(models.Issue.__table__.c.id)
                ).fetchall()][:20]
            )
        eng.dispose()
    assert titles[0] == titles[1]


def test_seed_is_idempotent(engine):
    """Re-running rebuilds rather than appending.

    seed() opens with drop_all() precisely so this holds. Without it the counts
    would double on every run and every measured number would drift.
    """
    seed_mod.seed(engine).close()
    first = _counts(engine)
    seed_mod.seed(engine).close()
    assert _counts(engine) == first


def test_is_seeded_false_on_empty_schema(empty_schema):
    """Tables exist, no rows — there is nothing to lose, so seeding is safe."""
    assert seed_mod.is_seeded(empty_schema) is False


def test_is_seeded_false_when_tables_are_missing(engine):
    """No schema at all. Must not raise looking for a table that isn't there."""
    assert seed_mod.is_seeded(engine) is False


def test_is_seeded_true_after_seeding(engine):
    """The guard that stops entrypoint.sh dropping a populated Postgres volume.

    This is the one with teeth: if it ever returns False against real data, the
    container's startup seed silently destroys the database it was meant to use.
    """
    seed_mod.seed(engine).close()
    assert seed_mod.is_seeded(engine) is True
