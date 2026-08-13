"""A test that fails on purpose, to prove CI blocks rather than reports.

PHASE-0.md's Days 8-9 gate is "a PR containing a deliberately failing test,
and GitHub refuses to let it merge." This is that test. It is expected to be
deleted once the gate has been demonstrated — it exists to be red.
"""

from experiments.sqlalchemy_1_4_vs_2_0 import models


def test_deliberately_wrong_table_count():
    """Asserts 9 tables. There are 8. This must fail."""
    assert len(models.Base.metadata.tables) == 9
