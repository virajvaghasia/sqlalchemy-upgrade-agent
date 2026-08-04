"""
migration.py — the 1.4 → 2.0 migration mechanics, measured on 1.4.52.

MIGRATION-2.0.md (§16-§22) makes a series of claims that are easy to assert and
easy to get wrong. Every one of them is measured here rather than believed:

  §16  session.query() and select() emit near-identical SQL — a rename, not a
       rewrite. Same for Query.get() vs Session.get().
  §17  session.execute() returns Row tuples, not objects. That is why .scalars()
       exists, and why it is the single most common 2.0 papercut.
  §18  a Session begins its transaction lazily, on first use — not at
       construction. "Autocommit removal" is really "autobegin".
  §19  the 2.0 warnings are OFF by default. The two that mark real breakages
       are invisible unless you ask for them.
  §20  future=True makes a 1.4 engine enforce 2.0's rules, so you can hit the
       2.0 errors today without upgrading anything.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration

§19 also needs a second run against the real query layer, because that is where
the deprecated calls live:
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


def seed(session):
    project = models.Project(name="apollo")
    session.add(project)
    session.add_all([
        models.Issue(title=f"issue {n}", status="open", project=project)
        for n in range(1, 4)
    ])
    session.commit()
    return project


engine = fresh_engine()
session = sessionmaker(bind=engine)()
seed(session)

captured = []
event.listen(engine, "before_cursor_execute",
             lambda conn, cur, stmt, *rest: captured.append(stmt))


def sql_for(work):
    """Run `work` against a cold cache and return the first statement it sent."""
    session.expire_all()
    captured.clear()
    work()
    return " ".join(captured[0].split())


# ---------------------------------------------------------------------------
# 1. §16 — is the query-style migration a rewrite, or a rename?
# ---------------------------------------------------------------------------
section("1. session.query() vs select() — what each actually sends")

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
# "AS issues_id" column labels; select() does not. A labelling difference is
# not a difference in work performed.
for part in ("FROM", "WHERE"):
    same = legacy[legacy.index(part):] == modern[modern.index(part):]
    print(f"     identical from {part} onward: {same}")
print(f"     identical including column labels: {legacy == modern}")

# The same question for the other headline rename.
old_get = sql_for(lambda: session.query(models.Issue).get(1))
new_get = sql_for(lambda: session.get(models.Issue, 1))
print()
print(f"     Query.get(1) vs Session.get(Issue, 1) — identical SQL: {old_get == new_get}")


# ---------------------------------------------------------------------------
# 2. §17 — what session.execute() actually hands back
# ---------------------------------------------------------------------------
section("2. The Result API — why .scalars() exists")

rows = session.execute(select(models.Issue)).all()
print("session.execute(select(Issue)).all()")
print(f"  element type : {type(rows[0]).__name__}   <- a Row, NOT an Issue")
print(f"  first element: {rows[0]}")
print(f"  rows[0][0]   : {rows[0][0]}   <- the Issue is INSIDE a one-tuple")
print()

scalars = session.execute(select(models.Issue)).scalars().all()
print("session.execute(select(Issue)).scalars().all()")
print(f"  element type : {type(scalars[0]).__name__}")
print(f"  first element: {scalars[0]}")
print()
print("  session.query(Issue).all() returned Issue objects directly. select()")
print("  is Core-shaped: it returns ROWS, and a row of one column is still a")
print("  one-column row. .scalars() unwraps it. Forgetting it is the most")
print("  common 2.0 papercut, and the error it causes is confusing:")
print("  AttributeError: 'Row' object has no attribute 'title'")
print()

# The narrowing helpers, for when you expect exactly one row.
one = session.execute(
    select(models.Issue).where(models.Issue.id == 1)
).scalar_one_or_none()
print(f"  scalar_one_or_none() on a 1-row result -> {one}")
try:
    session.execute(select(models.Issue)).scalar_one()
except Exception as exc:
    print(f"  scalar_one() on a 3-row result         -> {type(exc).__name__}")
    print(f"      {exc}")
print("  scalar_one() states an expectation the database then enforces.")


# ---------------------------------------------------------------------------
# 3. §18 — when does a transaction actually begin?
# ---------------------------------------------------------------------------
section("3. Autobegin — the transaction starts on first use, not on construct")

probe = sessionmaker(bind=engine)()
print(f"  fresh session, nothing done yet   in_transaction: {probe.in_transaction()}")
probe.execute(select(models.Issue)).scalars().all()
print(f"  after a single SELECT             in_transaction: {probe.in_transaction()}")
probe.commit()
print(f"  after commit()                    in_transaction: {probe.in_transaction()}")
probe.close()
print()
print("  Nothing was explicitly begun. The Session opened a transaction the")
print("  moment it first needed one, and commit() closed it. This is why")
print("  'SELECTs are inside a transaction' surprises people coming from 1.x")
print("  autocommit — and why commit() matters even for read-only work.")


# ---------------------------------------------------------------------------
# 4. §20 — future=True: 2.0's rules on the version already installed
# ---------------------------------------------------------------------------
section("4. future=True — hitting the 2.0 error without upgrading")

normal = fresh_engine()
future = fresh_engine(future=True)

print(f"  normal engine : {type(normal).__module__}.{type(normal).__name__}")
print(f"  future engine : {type(future).__module__}.{type(future).__name__}")
print()

for label, eng in (("normal 1.4 engine ", normal), ("future=True engine", future)):
    try:
        # The 1.4-ism, doing two deprecated things at once: connectionless
        # execution, and a bare SQL string.
        eng.execute("SELECT 1")
        outcome = "worked (silently, unless WARN_20 is set)"
    except NotImplementedError as exc:
        outcome = f"{type(exc).__name__}: {exc}"
    print(f'  engine.execute("SELECT 1") on {label} -> {outcome}')

print()
print("  The future engine raises TODAY, on 1.4.52. You do not have to upgrade")
print("  to find out what 2.0 will reject.")
print()

# Equally important: what future=True does NOT reject. Style is not breakage.
future_session = sessionmaker(bind=future, future=True)()
seed(future_session)
still_fine = future_session.query(models.Project).all()
print(f"  session.query(Project) on a future=True session -> {still_fine}")
print("  Not everything that looks 1.4-ish is a problem. Query survives 2.0.")
future_session.close()


# ---------------------------------------------------------------------------
# 5. The 2.0 form of the broken call, so the fix is on the page
# ---------------------------------------------------------------------------
section("5. The 2.0 replacement — explicit connection, explicit text()")

with future.connect() as conn:
    total = conn.execute(text("SELECT count(*) FROM issues")).scalar()

print("  with future.connect() as conn:")
print("      conn.execute(text('SELECT count(*) FROM issues')).scalar()")
print(f"  -> {total}   (runs clean on the future=True engine)")
print()
print("  Two fixes in one line, matching the two warnings §19 counts:")
print("    connectionless execution -> with engine.connect() as conn")
print("    bare SQL string          -> text(...)")

session.close()
