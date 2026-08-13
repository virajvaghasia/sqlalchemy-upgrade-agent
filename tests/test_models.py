"""The schema is what the docs describe.

These are not "does SQLAlchemy work" tests. Each one pins a claim some document
makes, so that editing models.py breaks the test rather than silently making a
doc wrong. PRACTICE-APP.md already asserted "Six tables" once and was wrong by
two; that is the failure mode being closed here.
"""

from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from experiments.sqlalchemy_1_4_vs_2_0 import models


def test_mappers_configure():
    """Nothing is only wired up lazily.

    Mapper configuration is deferred until first use, so a broken relationship
    stays invisible until something queries it. check.py exists for this reason;
    this makes it a test instead of a script someone remembers to run.
    """
    configure_mappers()


def test_six_mapped_classes_eight_tables():
    """PRACTICE-APP.md's headline numbers.

    They differ because issue_labels and issue_blocks are association *tables*
    with no class of their own — which is the point of the schema.
    """
    assert len(models.Base.registry.mappers) == 6
    assert len(models.Base.metadata.tables) == 8


def test_association_table_carries_only_keys():
    """issue_labels is a plain secondary table: two FKs and nothing else."""
    cols = {c.name for c in models.issue_labels.columns}
    assert cols == {"issue_id", "label_id"}


def test_association_object_carries_its_own_data():
    """issue_assignments is an association OBJECT — it has columns of its own.

    This is the distinction PRACTICE-APP.md turns on: the moment a join table
    has a column that is neither foreign key, it needs a mapped class.
    """
    cols = {c.name for c in models.IssueAssignment.__table__.columns}
    assert {"issue_id", "user_id"} < cols
    assert {"role", "assigned_at"} <= cols


def test_self_referential_relationship_exists():
    """Issue points at Issue, in both directions, through issue_blocks."""
    rels = inspect(models.Issue).relationships
    assert {"blocks", "blocked_by"} <= set(rels.keys())
    assert rels["blocks"].mapper.class_ is models.Issue
    assert rels["blocked_by"].mapper.class_ is models.Issue


def test_schema_creates_cleanly(engine):
    """create_all() emits a schema the database accepts."""
    models.Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == set(models.Base.metadata.tables)
