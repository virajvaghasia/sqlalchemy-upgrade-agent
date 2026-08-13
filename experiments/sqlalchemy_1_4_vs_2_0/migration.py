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
       2.0 errors today without upgrading anything — and what it does NOT
       catch, which matters just as much if you use it as a gate.
  §17  .unique() — the one place where query() -> select() is NOT purely
       cosmetic. Query de-duplicated joined eager loads silently; select()
       refuses to guess.
  §21  the N+1 in app.issue_report() is version-independent, and costs a
       number nobody in this repo had actually counted.
  §17  cascade_backrefs — the only breakage here that does NOT raise. Under
       2.0, an object attached by the MANY-TO-ONE side of a relationship
       (comment.issue = issue) is never enrolled in the session and its
       INSERT silently never runs; the collection side survives. Found by
       sweeping every module in this package — app.py only queries, so its
       inventory misses it entirely.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.migration

Section 7 reads the seeded file DB, so seed it first:
      uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed

§19 also needs a second run against the real query layer, because that is where
the deprecated calls live:
      SQLALCHEMY_WARN_20=1 uv run python -W always::DeprecationWarning \\
          -m experiments.sqlalchemy_1_4_vs_2_0.app
"""

import textwrap
import warnings
from collections import Counter

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import configure_mappers, joinedload, sessionmaker
from sqlalchemy.util import deprecations

from experiments.sqlalchemy_1_4_vs_2_0 import models


def section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_wrapped(message, indent, width=64):
    """Print a long library message across several lines, wrapped HERE.

    SQLAlchemy's errors are single long strings. Wrapping them in the script
    rather than by hand in study/02-MIGRATION-2.0.md keeps every "# runnable" block a
    literal paste of what the program prints.
    """
    for line in textwrap.wrap(message, width=width):
        print(f"{'':<{indent}}{line}")


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

def fold_columns(sql):
    """Abbreviate the SELECT list for DISPLAY only, so the line fits a doc block.

    Every comparison below runs on the full, unfolded strings. Folding here
    rather than by hand in study/02-MIGRATION-2.0.md is deliberate: a block labelled
    "# runnable" has to be reproducible by running it.
    """
    cols, _, rest = sql.partition(" FROM ")
    parts = [c.strip() for c in cols[len("SELECT "):].split(",")]
    if len(parts) <= 2:
        return sql
    return f"SELECT {parts[0]}, {parts[1]}, ... FROM {rest}"


print("1.x  session.query(Issue).filter(...)")
print(f"     {fold_columns(legacy)}")
print()
print("2.0  session.execute(select(Issue).where(...))")
print(f"     {fold_columns(modern)}")
print("     (column lists folded for display; the comparisons below use the full SQL)")
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
print(f"  element type : {type(rows[0]).__name__}".ljust(46) + "<- a Row, NOT an Issue")
print(f"  first element: {rows[0]}".ljust(46) + "<- note the trailing comma: a one-tuple")
print(f"  rows[0][0]   : {rows[0][0]}".ljust(46) + "<- the Issue is INSIDE it")
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

# The reflex that fixes the papercut becomes a bug the moment you select more
# than one column — and nothing tells you. Worth measuring, because "it throws
# away the other columns" reads as advice until you see it happen in silence.
two_cols = select(models.Issue.id, models.Issue.title)
print("  .scalars() is NOT 'unwrap the row'. It is 'project down to ONE column':")
print(f"    select(Issue.id, Issue.title).all()        -> {session.execute(two_cols).all()}")
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    truncated = session.execute(two_cols).scalars().all()
raised = [w.category.__name__ for w in caught]
print(f"    ...same select, .scalars().all()           -> {truncated}")
print(f"    warnings raised while discarding 'title'   -> {raised or 'NONE'}")
print(f"    the index is a parameter: .scalars(1).all()-> {session.execute(two_cols).scalars(1).all()}")
print()
print("  So the rule is not 'always add .scalars()'. It is 'add it when you")
print("  selected ONE thing'. On a wider select it silently returns column 0,")
print("  which is the opposite of the loud .unique() error in §6: same release,")
print("  one method guesses and the other refuses to.")
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
        outcome, detail = "worked (silently, unless WARN_20 is set)", None
    except NotImplementedError as exc:
        outcome, detail = f"{type(exc).__name__}:", str(exc)
    print(f'  engine.execute("SELECT 1") on {label} -> {outcome}')
    if detail:
        print_wrapped(detail, indent=33)

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
print()

# But do NOT read that as "clean under future=True means ready to upgrade".
# The flag is an engine/connection-level gate. It is silent about migration
# items that live elsewhere — which is exactly why §19's warning sweep is a
# separate step and not an alternative to this one.
print("  What future=True stays SILENT about (all real migration items):")

legacy_get = future_session.query(models.Project).get(1)
print(f"    Query.get(1)          -> {legacy_get}   (a LegacyAPIWarning item, accepted here)")
print( "    declarative_base      -> models.py still imports it from")
print( "                             sqlalchemy.ext.declarative, and the future")
print( "                             engine built every table from those models")
print( "                             without a word. That is a MovedIn20Warning")
print( "                             item, and only §19's sweep reports it.")
print()
print("  So: future=True fails what will FAIL AT THE ENGINE. It does not")
print("  enumerate what will WARN. Steps 1 and 4 of the recipe answer")
print("  different questions; passing one is not passing the other.")
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


# ---------------------------------------------------------------------------
# 6. §17 — .unique(): where "a rename, not a rewrite" stops being true
# ---------------------------------------------------------------------------
section("6. .unique() — the one place query() -> select() changes behaviour")

# §1 measured the SQL and found no difference. That result is real but narrow:
# it covers what gets SENT. This section covers what comes BACK, and here the
# two APIs genuinely disagree.
uni_engine = fresh_engine()
uni_session = sessionmaker(bind=uni_engine)()
uni_project = models.Project(name="apollo")
uni_session.add(uni_project)
for n in range(1, 4):
    issue = models.Issue(title=f"issue {n}", status="open", project=uni_project)
    # n comments on issue n, so the JOIN has something to multiply: 1 + 2 + 3.
    issue.comments = [models.Comment(body=f"comment {c} on {n}") for c in range(n)]
    uni_session.add(issue)
uni_session.commit()

stmt = select(models.Issue).options(joinedload(models.Issue.comments))

# Run it on a Core connection to see the rows the database actually returned —
# the ORM Result refuses to hand these over at all (that is the point of the
# section), so this is the only way to look at them.
with uni_engine.connect() as conn:
    raw = conn.execute(stmt).all()
print(f"  the JOIN returns {len(raw)} raw rows for 3 issues"
      f"  (they have 1, 2 and 3 comments)")
print()

legacy_rows = uni_session.query(models.Issue).options(
    joinedload(models.Issue.comments)
).all()
print(f"  1.x  query(Issue).options(joinedload(...)).all()")
print(f"       -> {len(legacy_rows)} Issue objects, no complaint (Query de-duplicated silently)")
print()

print("  2.0  session.execute(stmt).scalars().all()")
try:
    uni_session.execute(stmt).scalars().all()
    print("       -> no error")
except Exception as exc:
    print(f"       -> {type(exc).__name__}:")
    print_wrapped(str(exc), indent=10)
print()

deduped = uni_session.execute(stmt).unique().scalars().all()
print(f"  2.0  session.execute(stmt).unique().scalars().all()")
print(f"       -> {len(deduped)} Issue objects")
print()
print("  Same SQL, different contract. Query decided for you; select() refuses")
print("  to guess. This is the counter-example to §16: the query-style")
print("  migration is cosmetic EXCEPT where joined eager loading against a")
print("  collection is involved, and then it raises until you say .unique().")
print()

# WHEN does the requirement actually fire? The doc used to justify it with a
# "if you selected columns..." scenario, which cannot happen — you cannot
# joinedload onto a column select at all. Measure the boundary instead of
# reasoning about it.
print("  When does the requirement fire? Only one of these three:")
for label, probe in (
    ("select(Issue) + joinedload(collection)",
     lambda: uni_session.execute(
         select(models.Issue).options(joinedload(models.Issue.comments))).all()),
    ("select(Issue.id) + joinedload         ",
     lambda: uni_session.execute(
         select(models.Issue.id).options(joinedload(models.Issue.comments))).all()),
    ("select(Issue.id, Issue.title)  plain  ",
     lambda: uni_session.execute(
         select(models.Issue.id, models.Issue.title)).all()),
):
    try:
        print(f"    {label} -> ok, {len(probe())} rows")
    except Exception as exc:
        print(f"    {label} -> {type(exc).__name__}")
print()
print("  So the error is an ENTITY-only event. A column select never triggers")
print("  it. That matters, because the reason .unique() is not automatic is a")
print("  different question from the reason it raises here.")
print()

# WHY it is not automatic: .unique() dedupes entities by identity, but plain
# rows by VALUE. Two genuinely distinct rows that happen to match would be
# destroyed. Shown with rows that differ only in a column we did not select.
print("  Why it is not automatic — .unique() dedupes on different things:")
dedupe_session = sessionmaker(bind=fresh_engine())()
dupe_project = models.Project(name="apollo")
dedupe_session.add(dupe_project)
for _ in range(2):
    dupe_project.issues.append(models.Issue(title="duplicate title", status="open"))
dedupe_session.commit()

kept = dedupe_session.execute(select(models.Issue)).unique().scalars().all()
print(f"    entities: two DIFFERENT issues, identical titles, ids {[i.id for i in kept]}")
print(f"              .unique().scalars().all() -> {len(kept)} objects   (dedupes by IDENTITY)")

title_stmt = select(models.Issue.title)
plain = dedupe_session.execute(title_stmt).all()
uniq = dedupe_session.execute(title_stmt).unique().all()
print(f"    columns : .all()          -> {len(plain)} rows  {plain}")
print(f"              .unique().all() -> {len(uniq)} rows  {uniq}")
print("                                        ^ a real row destroyed (dedupes by VALUE)")
dedupe_session.close()
print()
print("  That is the whole reason 2.0 makes you say it. On entities .unique()")
print("  is safe — the primary key tells it what is genuinely the same object.")
print("  On plain rows it has only the values, so two real facts that happen to")
print("  match collapse into one. The library cannot tell which case you meant,")
print("  so it refuses to pick.")
uni_session.close()


# ---------------------------------------------------------------------------
# 7. §21 — what the N+1 actually costs, counted rather than estimated
# ---------------------------------------------------------------------------
section("7. The N+1 in issue_report() — the number, measured")

# Nobody had counted THIS loop. CONCEPTS §15's 201/202 are a different loop
# (apollo.issues + per-issue .labels), extrapolated correctly from a measured
# 9-issue run; the working estimate for issue_report() was 1 + 200 + 200 = 401.
# Counting it is more interesting than either, because the two lazy loads in
# the loop behave differently and only one of them is an N+1.
from experiments.sqlalchemy_1_4_vs_2_0 import app          # noqa: E402
from experiments.sqlalchemy_1_4_vs_2_0.seed import make_engine  # noqa: E402

seeded = make_engine()
report_session = sessionmaker(bind=seeded)()
n_issues = report_session.query(models.Issue).count()

if n_issues == 0:
    print("  issues.db is empty or missing. Seed it first:")
    print("      uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed")
else:
    counted = []
    event.listen(seeded, "before_cursor_execute",
                 lambda conn, cur, stmt, *rest: counted.append(stmt))

    app.issue_report(report_session)

    tables = Counter(
        # crude but sufficient: the first table named after FROM
        " ".join(s.split()).split(" FROM ")[1].split()[0]
        for s in counted
    )
    print(f"  issues in the seed              : {n_issues}")
    print(f"  queries fired by issue_report() : {len(counted)}")
    print()
    for table, n in tables.most_common():
        print(f"    {n:>4}x  SELECT ... FROM {table}")
    print()
    print("  Read the breakdown, not the total. Both attribute reads in the loop")
    print("  are lazy loads, but only ONE of them is an N+1:")
    print()
    print("    issue.comments  one-to-many  -> a collection is never in the")
    print("                                    identity map as a WHOLE, so every")
    print("                                    issue pays a query.        <- the N+1")
    print("    issue.project   many-to-one  -> a single object with a known PK, so")
    print("                                    SQLAlchemy checks the identity map")
    print("                                    first and only misses once per")
    print("                                    distinct project.          <- 3, not 200")
    print()
    print("  That is CONCEPTS §13's correction showing up at scale: 'a lazy load")
    print("  fires a query' is false for many-to-one on an object you already")
    print("  have. Estimating this loop as 1 + 200 + 200 overshoots by 197.")

report_session.close()


# ---------------------------------------------------------------------------
# 8. §17 — cascade_backrefs: the breakage that fails SILENTLY
# ---------------------------------------------------------------------------
# Found by sweeping every module in this package, not just app.py. app.py never
# builds an object graph, so its 5-warning inventory misses this entirely — and
# this is the most dangerous item in the repo, because unlike engine.execute()
# it raises nothing. It just stops doing the work.
section("8. cascade_backrefs — the 2.0 change that fails silently")

print("  CONCEPTS §14 teaches that you need not session.add() an object if you")
print("  attach it to one already in the session — the save-update cascade")
print("  enrolls it. Half of that is still true in 2.0. The half that isn't")
print("  loses rows without raising anything.")
print()
print("  Which half depends ENTIRELY on the direction you write:")
print()


def attach_trial(build, **kwargs):
    """Attach an Issue to a Project by `build`, flush, count what landed."""
    eng = fresh_engine(**kwargs)
    sess = sessionmaker(bind=eng, **kwargs)()
    proj = models.Project(name="apollo")
    sess.add(proj)
    build(proj)
    sess.flush()
    rows = sess.execute(text("SELECT count(*) FROM issues")).scalar()
    sess.close()
    return rows


def new_issue():
    return models.Issue(title="login button broken", status="open")


FORMS = [
    ("project.issues.append(issue)", lambda p: p.issues.append(new_issue())),
    ("project.issues = [issue]", lambda p: setattr(p, "issues", [new_issue()])),
    ("issue.project = project", lambda p: setattr(new_issue(), "project", p)),
    ("Issue(..., project=project)",
     lambda p: models.Issue(title="t", status="open", project=p)),
]

print("  Each row below attaches exactly ONE issue to a project that is already")
print("  in the session, calls flush(), then asks the database:")
print("      SELECT count(*) FROM issues        1 = the INSERT ran, 0 = it did not")
print()
print(f"  {'how you attach the one issue':<32}{'1.4':>6}{'2.0':>6}   verdict")
print(f"  {'-' * 32}{'-' * 6}{'-' * 6}   {'-' * 22}")
for label, build in FORMS:
    old, new = attach_trial(build), attach_trial(build, future=True)
    verdict = "survives" if old == new else f"SILENT LOSS ({old} -> {new})"
    print(f"  {label:<32}{old:>6}{new:>6}   {verdict}")
print(f"  {'':<32}{'^^^^^^^^^^^^':>12}")
print(f"  {'':<32}{'rows in issues':>14}")

print()
print("  Writing the COLLECTION side is the save-update cascade, and 2.0 keeps")
print("  it. Writing the MANY-TO-ONE side relies on the backref populating the")
print("  collection first, and THAT leg is what 2.0 drops. In 1.4 the two are")
print("  interchangeable, so nothing in the code says which one you picked.")
print()

# The payoff: this repo's own seed uses BOTH forms, and the choice decides
# which tables survive. Replicated here rather than re-running seed.py, so
# issues.db is not rewritten mid-script.
print("  seed.py uses both. Replicating its exact pattern:")
print("      issues       via projects.issues.append(issue)   (seed.py:122)")
print("      comments     via comment.issue = issue           (seed.py:136)")
print("      assignments  via a.issue = issue                 (seed.py:147)")
print("  ...and only users, projects and labels are ever session.add()ed:")
print()


def seed_shape(**kwargs):
    eng = fresh_engine(**kwargs)
    sess = sessionmaker(bind=eng, **kwargs)()
    users = [models.User(name="alice", email="a@x")]
    projects = [models.Project(name="apollo")]
    sess.add_all(users + projects)
    for n in range(3):
        issue = models.Issue(title=f"i{n}", status="open")
        projects[0].issues.append(issue)
        for c in range(2):
            comment = models.Comment(body=f"c{c}")
            comment.issue = issue
            comment.author = users[0]
        assignment = models.IssueAssignment(role="owner")
        assignment.issue = issue
        assignment.user = users[0]
    sess.flush()
    counts = {
        t: sess.execute(text(f"SELECT count(*) FROM {t}")).scalar()
        for t in ("projects", "users", "issues", "comments", "issue_assignments")
    }
    sess.close()
    return counts


old_counts, new_counts = seed_shape(), seed_shape(future=True)
print(f"      {'table':<20}{'1.4':>6}{'2.0':>6}")
for table in old_counts:
    gone = "   <-- GONE, silently" if new_counts[table] == 0 < old_counts[table] else ""
    print(f"      {table:<20}{old_counts[table]:>6}{new_counts[table]:>6}{gone}")

print()
print("  The seed would still 'succeed'. No exception, no warning at runtime,")
print("  a database that looks populated — with every comment and assignment")
print("  missing. engine.execute() raises the first time it runs and cannot be")
print("  shipped by accident. This can.")
print()

# How wide is the exposure? Read it off the mappers rather than claiming "all
# of them" — the same rule states.py §7 follows for the join multiplication.
configure_mappers()
backref_rels = [
    f"{m.class_.__name__}.{r.key}"
    for m in models.Base.registry.mappers
    for r in m.relationships
    if r.backref
]
total_rels = sum(len(m.relationships) for m in models.Base.registry.mappers)
print(f"  Exposure: {len(backref_rels)} of {total_rels} relationships in models.py are declared")
print("  with backref=, so every one of them carries the droppable leg:")
print_wrapped(", ".join(sorted(backref_rels)), indent=6, width=62)
print()
print("  The fix is to say what you meant: session.add(comment). Relying on the")
print("  cascade was always implicit; 2.0 removes the implicitness, not the")
print("  capability. cascade_backrefs=False adopts the 2.0 behaviour today.")


# ---------------------------------------------------------------------------
# 9. §19/§20 — the warning sweep and future=True miss DIFFERENT things
# ---------------------------------------------------------------------------
# Written after conflating two counts: "distinct RemovedIn20Warning messages"
# is not "things that break in 2.0". Neither tool alone produces the breakage
# inventory, and this is the measurement that shows why.
section("9. Neither tool is the inventory — what each one misses")


def classify(build_case):
    """Return (warning classes under WARN_20, outcome under 2.0 rules).

    SQLALCHEMY_WARN_20 is normally read from the environment at import time,
    which is why §19's sweep has to spawn a subprocess. The same switch is a
    plain module flag underneath, so this section can toggle it in place and
    measure both tools in one run.
    """
    def run(**kwargs):
        eng = fresh_engine(**kwargs)
        sess = sessionmaker(bind=eng, **kwargs)()
        proj = models.Project(name="apollo")
        sess.add(proj)
        proj.issues.append(models.Issue(title="i", status="open"))
        sess.commit()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                build_case(eng, sess)
                result = "ok"
            except Exception as exc:
                result = type(exc).__name__
        classes = sorted({w.category.__name__ for w in caught
                          if "In20" in w.category.__name__
                          or "LegacyAPI" in w.category.__name__})
        try:
            sess.close()
        except Exception:
            pass
        return classes, result

    deprecations.SQLALCHEMY_WARN_20 = True
    try:
        warned, _ = run()
    finally:
        deprecations.SQLALCHEMY_WARN_20 = False
    _, under_20 = run(future=True)
    return ",".join(c.replace("Warning", "") for c in warned) or "— nothing —", under_20


CASES = [
    ("engine.execute('SELECT 1')", lambda e, s: e.execute("SELECT 1")),
    ("select([Issue.id]) list form",
     lambda e, s: s.execute(select([models.Issue.id])).all()),
    ("joinedload('issues') by string",
     lambda e, s: s.query(models.Project).options(joinedload("issues")).all()),
    ("engine.table_names()", lambda e, s: e.table_names()),
    ("Query.filter('raw string')",
     lambda e, s: s.query(models.Issue).filter("status='open'").all()),
    ("Row attr access, no .scalars()",
     lambda e, s: s.execute(select(models.Issue)).all()[0].title),
]

print(f"  {'1.4 pattern':<32}{'WARN_20 says':<16}{'future=True says':<24}")
print(f"  {'-' * 32}{'-' * 16}{'-' * 24}")
for label, case in CASES:
    warned, under_20 = classify(case)
    print(f"  {label:<32}{warned:<16}{under_20:<24}")

print()
print("  Read the table as three groups, because they need different tools:")
print()
print("    rows 1     both agree — warned AND rejected at the engine.")
print("    rows 2-3   WARNED, but future=True runs them happily. They are")
print("               construction-time removals, not engine rules, so the")
print("               flag has no opinion. Real 2.0 rejects them.")
print("    rows 4-6   NO warning at all, and they fail. The sweep cannot see")
print("               them; only running the code finds them.")
print()
print("  So: the sweep is not the inventory, and future=True is not the")
print("  verdict on the whole inventory. A breakage list built from either")
print("  one alone is short, and short in a way you cannot detect from")
print("  inside that tool.")
print()
print("  This is why PHASE-0 asks for breakages 'personally caused, hit and")
print("  fixed' rather than swept: the last group only exists once the code")
print("  actually runs on 2.0.")

session.close()
