"""
states.py — SQLAlchemy 1.4 runtime behaviour, measured rather than asserted.

explore.py covers relationship *shape*: which rows appear, which foreign keys the
ORM fills in. This file covers *runtime*: what state an object is in at each
moment, what commit() does to the values cached on it, and how many SQL
statements a loop actually costs.

Nothing here is claimed. Every state comes from inspect(); every query count
comes from a listener on the engine that increments once per cursor execution.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.states

Written in 1.4 style on purpose (session.query(...), backref, etc.), matching
explore.py — those are the idioms Phase 0 migrates to 2.0 later.
"""

from collections import Counter

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import joinedload, selectinload, sessionmaker

from experiments.sqlalchemy_1_4_vs_2_0 import models


def section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def describe(label, obj):
    """One line per moment: where the object is, and what it still remembers.

    inspect() returns an InstanceState. Four of its flags are mutually
    exclusive and answer "where is this object"; .expired is a separate flag
    that only means anything while persistent. .dict is the attribute cache —
    watching it empty at commit() is what makes expiry concrete.
    """
    state = inspect(obj)
    where = (
        "transient" if state.transient
        else "pending" if state.pending
        else "persistent" if state.persistent
        else "detached" if state.detached
        else "unknown"
    )
    cached = sorted(k for k in state.dict if not k.startswith("_sa_"))
    print(f"{label:<22} {where:<11} expired={str(state.expired):<6} cached={cached}")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
# Two independent in-memory databases, on purpose. Sections 1-3 INSERT a
# throwaway Issue to watch it change state; if the counting sections shared
# that database, query(Issue).all() would return 10 rows instead of 9 and every
# count below would be off by one. A measurement must not be contaminated by
# the demo that runs before it.
def fresh_engine():
    eng = create_engine("sqlite://")
    models.Base.metadata.create_all(eng)
    return eng


engine = fresh_engine()
Session = sessionmaker(bind=engine)


def seed(session):
    """issue_labels: (1,1) (1,2) (2,3) (3,1) (3,3) (7,2) — matches explore.py."""
    apollo = models.Project(name="apollo")
    bug = models.Label(name="bug")
    urgent = models.Label(name="urgent")
    ui = models.Label(name="ui")
    issues = [
        models.Issue(title=f"issue {n}", status="open", project=apollo)
        for n in range(1, 10)
    ]
    session.add(apollo)
    session.add_all([bug, urgent, ui])

    issues[0].labels.append(bug)
    issues[0].labels.append(urgent)
    issues[1].labels.append(ui)
    issues[2].labels.append(bug)
    issues[2].labels.append(ui)
    issues[6].labels.append(urgent)

    session.commit()
    return apollo


# ---------------------------------------------------------------------------
# 1. The five states, one object, one line per moment
# ---------------------------------------------------------------------------
section("1. Object states — transient / pending / persistent / detached")

session = Session()

project = models.Project(name="apollo")
issue = models.Issue(title="login button broken", status="open")
describe("constructed", issue)

# TRANSIENT -> PENDING. Note that session.add() is never called on `issue`:
# assigning .project attaches it to something already in the session, and the
# save-update cascade enrolls it. explore.py relies on the same mechanism.
#
# THIS PARTICULAR DIRECTION IS VERSION-DEPENDENT, and it is the repo's most
# dangerous 2.0 item. Writing the MANY-TO-ONE side (issue.project = p) works in
# 1.4 only because the backref populates project.issues first, and 2.0 drops
# that leg: `issue` would stay transient, no INSERT would run, and NOTHING
# would be raised — describe() below would print `pending` on 1.4 and
# `transient` on 2.0. Writing the COLLECTION side (project.issues.append(issue))
# survives both. Measured in migration.py §8; written up in study/02-MIGRATION-2.0.md
# §17. Left as-is deliberately — this file documents 1.4 — but do not copy the
# many-to-one form into new code.
issue.project = project
session.add(project)
describe("issue.project = p", issue)
print(f"{'':<22} issue.id is {issue.id} — no INSERT has run yet")

# PENDING -> PERSISTENT. flush() emits the INSERT; the database assigns the key
# and SQLAlchemy writes it back onto the Python object.
session.flush()
describe("session.flush()", issue)
print(f"{'':<22} issue.id is {issue.id} — the database assigned it")

# Still PERSISTENT, now EXPIRED. commit() does not move the object anywhere;
# it empties the attribute cache, which is what `expired=True` means.
session.commit()
describe("session.commit()", issue)
print(f"{'':<22} cached is empty — every loaded value was discarded")


# ---------------------------------------------------------------------------
# 2. Expiry heals itself: one read re-SELECTs the whole row
# ---------------------------------------------------------------------------
section("2. Reading an expired attribute — the silent re-SELECT")

print(">>> reading issue.title while expired:")
engine.echo = True
title = issue.title
engine.echo = False
print(f"    issue.title = {title!r}")
describe("after that read", issue)
print(f"{'':<22} one read refilled the ENTIRE row, not just .title")

print()
print(">>> reading issue.title a second time (expect no SQL):")
engine.echo = True
_ = issue.title
engine.echo = False
print("    ...no SQL. The value is cached again.")


# ---------------------------------------------------------------------------
# 3. Detached: the asymmetry that produces DetachedInstanceError
# ---------------------------------------------------------------------------
section("3. Detached — loaded attributes survive, unloaded ones raise")

session.close()
describe("session.close()", issue)

print(f"    issue.title  -> {issue.title!r}   (was loaded before the close)")
try:
    issue.labels
except Exception as exc:
    print(f"    issue.labels -> {type(exc).__name__}")
    print(f"                    {str(exc)[:88]}...")

print()
print("    Expired and detached are not the same thing:")
print("      expired  = values discarded, session still there -> silently re-queries")
print("      detached = no session at all                     -> raises")


# ---------------------------------------------------------------------------
# 4. The identity map: one row = one Python object, per session
# ---------------------------------------------------------------------------
section("4. Identity map")

# Fresh database: sections 1-3 left a throwaway Issue behind, and the counts in
# section 5 depend on there being exactly 9.
count_engine = fresh_engine()
session = sessionmaker(bind=count_engine)()
apollo = seed(session)

a = session.query(models.Issue).filter_by(id=1).one()
b = session.query(models.Issue).filter_by(id=1).one()
print(f"two separate queries for issue 1 -> a is b: {a is b}")
print("that is why a many-to-one like issue.project can skip SQL entirely:")
print("it checks this map by primary key before it considers emitting a query.")


# ---------------------------------------------------------------------------
# 5. Counting queries — where N+1 comes from, and what fixes it
# ---------------------------------------------------------------------------
section("5. Query counts — lazy vs selectinload vs joinedload")

# The counts below are only meaningful against a known row count. State it out
# loud rather than trusting it: an off-by-one here silently changes every
# number in study/01-CONCEPTS.md §15.
n_issues = session.query(models.Issue).count()
print(f"issues in this database: {n_issues}")
assert n_issues == 9, f"expected 9 issues, found {n_issues} — counts below would be wrong"
print()

queries = []


@event.listens_for(count_engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):
    queries.append(statement)


def count(work):
    """Run `work` with a clean session cache and return the SQL count."""
    session.expire_all()
    queries.clear()
    work()
    return len(queries)


def walk_from_project():
    _ = apollo.name
    for i in apollo.issues:
        _ = i.labels


def loop_lazy():
    for i in session.query(models.Issue).all():
        _ = i.labels


def loop_selectinload():
    q = session.query(models.Issue).options(selectinload(models.Issue.labels))
    for i in q.all():
        _ = i.labels


def loop_joinedload():
    q = session.query(models.Issue).options(joinedload(models.Issue.labels))
    for i in q.all():
        _ = i.labels


print("Scope A — starting from an expired project object:")
print(f"  apollo.name + apollo.issues + 9x .labels   "
      f"{count(walk_from_project):>3} queries   (1 + 1 + 9)")
print()
print("Scope B — starting from a query, no project read:")
print(f"  lazy (default)                             {count(loop_lazy):>3} queries   (1 + 9)")
print(f"  selectinload                               {count(loop_selectinload):>3} queries")
print(f"  joinedload                                 {count(loop_joinedload):>3} queries")
print()
print("The two scopes differ by exactly one query: the apollo.name re-SELECT")
print("that commit() forced. The N+1 itself is the 9 — one per row in the loop.")

session.close()


# ---------------------------------------------------------------------------
# 6. flush() vs commit() — three differences, none of them guessed
# ---------------------------------------------------------------------------
section("6. flush() vs commit()")

# (a) commit() flushes for you. flush() is a SUBSET of commit(), not an
#     alternative to it.
eng = fresh_engine()
sess = sessionmaker(bind=eng)()
sess.add(models.Project(name="apollo"))
sess.commit()  # note: flush() is never called
print("(a) committed without ever calling flush() -> rows:",
      sess.query(models.Project).count())
sess.close()

# (b) flush() sends the INSERT but stays inside the transaction, so a rollback
#     still erases it.
eng = fresh_engine()
sess = sessionmaker(bind=eng)()
sess.add(models.Project(name="apollo"))
sess.flush()
visible = sess.query(models.Project).count()
open_txn = sess.in_transaction()
sess.rollback()
print(f"(b) after flush: rows visible={visible}, transaction open={open_txn}"
      f" -> after rollback: rows={sess.query(models.Project).count()}")
sess.close()

# (c) Expiry is expire_on_commit — a Session flag that merely DEFAULTS to True.
#     Same commit() call both times; only the flag differs.
print("(c) expiry is a Session flag, not a property of commit():")
for flag in (True, False):
    eng = fresh_engine()
    sess = sessionmaker(bind=eng, expire_on_commit=flag)()
    proj = models.Project(name="apollo")
    sess.add(proj)
    sess.commit()

    # Capture state BEFORE reading anything — a read un-expires the object and
    # would hide the very thing being measured.
    expired_now = inspect(proj).expired
    cached_now = sorted(k for k in inspect(proj).dict if not k.startswith("_sa_"))

    seen = []
    event.listen(eng, "before_cursor_execute",
                 lambda conn, cur, stmt, *rest, _s=seen: _s.append(stmt))
    _ = proj.name

    print(f"    expire_on_commit={str(flag):<5} -> expired={str(expired_now):<5} "
          f"cached={str(cached_now):<20} queries reading p.name: {len(seen)}")
    sess.close()


# ---------------------------------------------------------------------------
# 7. The SAME loop, three strategies, with the real SQL printed
# ---------------------------------------------------------------------------
# Section 5 counts statements. Counting tells you 10 vs 2 vs 1 but not WHY, so
# this section prints the statements themselves and, for joinedload, the raw
# rows the JOIN returns before SQLAlchemy folds them back into objects.
section("7. What each loading strategy actually sends")

seen_sql = []

# Where the "←" notes start, so they line up into a readable column.
NOTE_COL = 76


def annotate(stmt, params):
    """Say what a statement is FOR, derived from the statement itself.

    Deriving beats hardcoding for the same reason show_join_multiplication()
    counts instead of asserting: a note keyed to "this is the selectinload run"
    keeps printing confidently after the strategy or the seed changes. A note
    read off the params can't.
    """
    if not params:
        return "issues and labels together" if "JOIN" in stmt else "get the issues"
    if len(params) == 1:
        return f'"labels for issue {params[0]}?"'
    return f"ALL {len(params)} ids in ONE query"


def print_stmt(n, stmt, params):
    flat = " ".join(stmt.split())
    # Column lists are noise here; the FROM/WHERE shape is the point.
    body = flat[flat.index("FROM"):] if "FROM" in flat else flat
    note = annotate(flat, params)
    head = f"  {n}. SELECT ... {body[:58].rstrip()}"
    if params:
        print(head)
        print(f"     params: {params}".ljust(NOTE_COL) + f"← {note}")
    else:
        print(head.ljust(NOTE_COL) + f"← {note}")


def show(strategy, option):
    """Run the identical loop under one loading strategy and print its SQL."""
    session.expire_all()
    seen_sql.clear()

    query = session.query(models.Issue)
    if option is not None:
        query = query.options(option(models.Issue.labels))
    issues = query.all()
    for i in issues:
        _ = i.labels

    print(f"--- {strategy}: {len(seen_sql)} statement(s), {len(issues)} Issue objects ---")
    # The repetitive middle of an N+1 is folded HERE, in the program, and the
    # fold line names exactly which statements it covers. Doing it in the script
    # rather than by hand in study/01-CONCEPTS.md is the point: a block labelled
    # "# runnable" has to be something you can actually get by running it.
    fold = len(seen_sql) > 5
    for n, (stmt, params) in enumerate(seen_sql, 1):
        if fold and 4 <= n < len(seen_sql):
            if n == 4:
                span = f"     ... statements 4-{len(seen_sql) - 1} identical, params {seen_sql[3][1]} through {seen_sql[-2][1]}"
                print(span.ljust(NOTE_COL) + "← one round trip per issue")
            continue
        print_stmt(n, stmt, params)
    print()


event.listen(count_engine, "before_cursor_execute",
             lambda conn, cur, stmt, params, *rest: seen_sql.append((stmt, params)))

show("lazy (default)", None)
show("selectinload", selectinload)
show("joinedload", joinedload)

# Why joinedload is not free: its LEFT JOIN multiplies rows. An issue with two
# labels comes back twice, with all six issue columns repeated. SQLAlchemy
# de-duplicates by primary key afterwards, so you never see it in Python — but
# the database still built and shipped every duplicate row.
def show_join_multiplication():
    """Print the raw rows joinedload's JOIN produces, before de-duplication.

    Which issues repeat is COUNTED from the returned rows, never hardcoded. A
    literal list of ids would be an assertion about the seed rather than an
    observation of the join, and would keep printing confidently after the seed
    changed underneath it.
    """
    # NOTE: a bare SQL string here is a deliberate 1.4-ism — in 2.0 this must
    # become session.execute(text(...)). Catalogued, not accidental.
    raw = session.execute(
        "SELECT issues.id, labels.name FROM issues "
        "LEFT OUTER JOIN issue_labels ON issues.id = issue_labels.issue_id "
        "LEFT OUTER JOIN labels ON labels.id = issue_labels.label_id"
    ).fetchall()

    appearances = Counter(issue_id for issue_id, _ in raw)
    repeated = {i for i, n in appearances.items() if n > 1}

    print(f"  its JOIN returns {len(raw)} raw rows to describe {n_issues} issues:")
    for issue_id, label_name in raw:
        note = f"  <-- appears {appearances[issue_id]}x" if issue_id in repeated else ""
        print(f"    issue {issue_id}  label={str(label_name):<8}{note}".rstrip())

    extra = len(raw) - n_issues
    print(f"  {len(raw)} rows for {n_issues} issues = {extra} duplicated rows, caused by the")
    print(f"  {len(repeated)} issues that carry more than one label: {sorted(repeated)}")
    print("  SQLAlchemy folds them back into 9 objects, so Python never shows you the")
    print("  duplication — but the database still built and sent every one, each")
    print("  repeating all six issue columns. At 20 labels per issue: 180 rows.")


print("Why joinedload's 1 query is not automatically the best:")
show_join_multiplication()

session.close()
