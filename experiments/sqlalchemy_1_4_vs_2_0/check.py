"""Smoke test: force SQLAlchemy to actually wire up the relationships.

Importing models.py is NOT enough — SQLAlchemy configures mappers lazily, so a
broken relationship stays silent until something first uses it. configure_mappers()
does that work up front, so errors surface here instead of at runtime.

    uv run python -m experiments.sqlalchemy_1_4_vs_2_0.check
"""

from sqlalchemy.orm import configure_mappers

from experiments.sqlalchemy_1_4_vs_2_0 import models  # noqa: F401

configure_mappers()
print("mappers configured OK")
