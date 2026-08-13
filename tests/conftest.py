"""Shared fixtures.

Every test gets its own throwaway SQLite file. Deliberately NOT the repo's
`issues.db`: a test suite that mutates the file the docs measure would make the
measured counts in PRACTICE-APP.md and MIGRATION-2.0.md depend on whether tests
had been run, which is exactly the kind of hidden coupling this repo keeps
finding and removing.

Deliberately not `:memory:` either. `seed.py` writes a real file on purpose —
`app.py` opens the same database in a separate process — so testing against a
file keeps the tests on the same footing as the thing they describe.
"""

import pytest
from sqlalchemy import create_engine

from experiments.sqlalchemy_1_4_vs_2_0 import models


@pytest.fixture
def db_path(tmp_path):
    """A fresh SQLite path, thrown away after each test."""
    return tmp_path / "test.db"


@pytest.fixture
def engine(db_path):
    """An engine on an empty database, schema not yet created."""
    eng = create_engine(f"sqlite:///{db_path}")
    yield eng
    eng.dispose()


@pytest.fixture
def empty_schema(engine):
    """Tables created, no rows. For testing what an un-seeded database does."""
    models.Base.metadata.create_all(engine)
    return engine
