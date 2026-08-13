"""Database location and reachability — the two things Compose changed.

`DATABASE_URL` is what lets the same code run against SQLite locally and Postgres
in a container. `wait_for_db` is what lets it start before the server is ready.
Both were added by hand during Phase 0 Part C and neither had a test.
"""

import importlib

import pytest
from sqlalchemy import create_engine

from experiments.sqlalchemy_1_4_vs_2_0 import seed as seed_mod


def test_db_url_defaults_to_sqlite(monkeypatch):
    """With no env var set, Part A behaviour is unchanged.

    This is the property that keeps every measurement in BREAKAGES.md and
    MIGRATION-2.0.md valid — they were all taken against the SQLite default.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reloaded = importlib.reload(seed_mod)
    assert reloaded.DB_URL == "sqlite:///issues.db"


def test_database_url_overrides_the_default(monkeypatch):
    """Compose sets this; the app reads it. No code change, no edit."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://app:pw@db:5432/issues")
    reloaded = importlib.reload(seed_mod)
    assert reloaded.DB_URL == "postgresql+psycopg2://app:pw@db:5432/issues"


@pytest.fixture(autouse=True)
def _restore_module(monkeypatch):
    """Reload once more after each test so module state cannot leak.

    seed.DB_URL is read at import time, so a test that reloads the module with a
    Postgres URL would leave it there for everything that follows.
    """
    yield
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(seed_mod)


def test_wait_for_db_returns_when_the_database_answers(engine):
    """The happy path costs one connection and no sleeping."""
    seed_mod.wait_for_db(engine, attempts=1, delay=0)


def test_wait_for_db_gives_up_rather_than_hanging(tmp_path):
    """An unreachable database must fail, not retry forever.

    A retry loop with no ceiling is worse than no retry loop: the container
    never starts and never says why. The error has to name both the attempt
    count and the underlying cause.
    """
    unreachable = create_engine("sqlite:////nonexistent-dir-xyz/x.db")
    with pytest.raises(RuntimeError) as exc:
        seed_mod.wait_for_db(unreachable, attempts=2, delay=0)
    assert "2 attempts" in str(exc.value)
    assert exc.value.__cause__ is not None


def test_make_engine_can_skip_waiting(engine, monkeypatch):
    """wait=False exists so tests and tooling need no live database."""
    monkeypatch.setattr(seed_mod, "DB_URL", "sqlite:////nonexistent-dir-xyz/x.db")
    seed_mod.make_engine(wait=False)  # must not raise
