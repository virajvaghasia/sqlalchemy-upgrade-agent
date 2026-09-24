"""Shared fixtures.

Every test gets its own throwaway SQLite file. Deliberately NOT the repo's
`issues.db`: a test suite that mutates the file the docs measure would make the
measured counts depend on whether tests
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


@pytest.fixture(autouse=True)
def _ledger_in_tmp(tmp_path, monkeypatch):
    """Keep the token ledger out of the repo's own file during tests.

    Same rule as `db_path` above: a suite that writes into the artifact it
    measures makes that artifact depend on whether tests were run. Caught on
    2026-09-16, when a faked NVIDIA reply in test_faithful landed a real row in
    `logs/nvidia-usage.jsonl`.
    """
    from rag import usage

    monkeypatch.setattr(usage, "LEDGER", tmp_path / "nvidia-usage.jsonl")
