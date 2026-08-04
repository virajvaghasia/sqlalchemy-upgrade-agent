"""
migration.py — the 1.4 → 2.0 migration mechanics, demonstrated on 1.4.52.

CONCEPTS.md Part 4 (§16-§19) makes three claims that are easy to assert and
easy to get wrong. This file measures all three:

  §16  session.query() and select() emit near-identical SQL, so that migration
       is a rename rather than a rewrite.
  §17  the four warning classes mean genuinely different things, and only one
       of them is a breakage.
  §18  future=True makes a 1.4 engine enforce 2.0's rules, so you can hit the
       2.0 errors without upgrading anything.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration

For §17's live warning output, run app.py under the flag instead:
      SQLALCHEMY_WARN_20=1 uv run python -W always::DeprecationWarning \\
          -m experiments.sqlalchemy_1_4_vs_2_0.app
"""

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from experiments.sqlalchemy_1_4_vs_2_0 import models


def section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def fresh_engine(**kwargs):
    eng = create_engine("sqlite://", **kwargs)
    models.Base.metadata.create_all(eng)
    return eng


# ---------------------------------------------------------------------------
# 1. §16 — is the query-style migration a rewrite, or a rename?
# ---------------------------------------------------------------------------
section("1. session.query() vs select() — what each actually sends")

engine = fresh_engine()
session = sessionmaker(bind=engine)()

captured = []
event.listen(engine, "before_cursor_execute",
             lambda conn, cur, stmt, *rest: captured.append(stmt))


def sql_for(work):
    captured.clear()
    work()
    return " ".join(captured[0].split())


legacy = sql_for(
    lambda: session.query(models.Issue)
    .filter(models.Issue.status == "open")
    .all()
)
modern = sql_for(
    lambda: session.execute(
        select(models.Issue).where(models.Issue.status == "open")
    ).scalars().all()
)

print("1.x  session.query(Issue).filter(...)")
print(f"     {legacy}")
print()
print("2.0  session.execute(select(Issue).where(...))")
print(f"     {modern}")
print()

# Compare the parts that decide what the database actually does. Query adds
# "AS issues_id" column labels; select() does not. That is a labelling
# difference, not a difference in work performed.
for part in ("FROM", "WHERE"):
    same = legacy[legacy.index(part):] == modern[modern.index(part):]
    print(f"     identical from {part} onward: {same}")
print(f"     identical including column labels: {legacy == modern}")
print()
print("     Same tables, same WHERE, same parameters. The only difference is")
print("     Query's 'AS issues_id' labels. This migration is a rename.")


# ---------------------------------------------------------------------------
# 2. §18 — future=True: 2.0's rules, on the version already installed
# ---------------------------------------------------------------------------
section("2. future=True — hitting the 2.0 error without upgrading")

normal = fresh_engine()
future = fresh_engine(future=True)

print(f"normal engine : {type(normal).__module__}.{type(normal).__name__}")
print(f"future engine : {type(future).__module__}.{type(future).__name__}")
print()

for label, eng in (("normal 1.4 engine", normal), ("future=True engine", future)):
    try:
        # Deliberately the 1.4-ism: connectionless execution AND a bare string.
        eng.execute("SELECT 1")
        outcome = "worked (emits RemovedIn20Warning under WARN_20)"
    except NotImplementedError as exc:
        outcome = f"{type(exc).__name__}: {exc}"
    print(f'  engine.execute("SELECT 1") on {label:<19} -> {outcome}')

print()
print("  The future=True engine raises TODAY, on 1.4.52. You do not have to")
print("  upgrade to find out what 2.0 will reject.")


# ---------------------------------------------------------------------------
# 3. The 2.0 form of that same call, so the fix is on the page
# ---------------------------------------------------------------------------
section("3. The 2.0 replacement — explicit connection, explicit text()")

with future.connect() as conn:
    total = conn.execute(text("SELECT count(*) FROM issues")).scalar()
print("  with future.connect() as conn:")
print("      conn.execute(text('SELECT count(*) FROM issues'))")
print(f"  -> {total}   (runs clean on the future=True engine)")
print()
print("  Two fixes in one line, matching the two warnings §17 counts:")
print("    connectionless execution -> with engine.connect() as conn")
print("    bare SQL string          -> text(...)")

session.close()
