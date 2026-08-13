"""
app.py — the query layer, written badly on purpose.

Every function here works under SQLAlchemy 1.4.52 and every one is a 2.0 problem
of some kind. This is the baseline you destroy in Step 8.

Do not "improve" anything here. Code that doesn't break produces no breakage.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.app
      (seed it first: uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed)

**Three tiers, and only one of them is a real breakage.** Measured under 1.4.52
with SQLALCHEMY_WARN_20=1, not assumed:

  REMOVED — fails in 2.0. These are the deliverables/BREAKAGES.md entries.
    engine.execute("SELECT ...")   RemovedIn20Warning  (two of them: connectionless
                                   execution, and the bare string)
                                   → with engine.connect() as c: c.execute(text(...))

  DEPRECATED — warns, still runs in 2.0.
    Query.get(pk)                  LegacyAPIWarning
                                   → session.get(Model, pk)

  LEGACY — silent, still runs in 2.0. NOT a breakage.
    session.query(Model)           no warning at all
                                   → select(Model) + session.execute(...) is the
                                     2.0 *style*, but 1.x Query is still supported

  NOT A VERSION ISSUE AT ALL — same behaviour in both:
    lazy loading in a loop         an N+1; slow in 1.4, equally slow in 2.0
    returning a detached object    DetachedInstanceError fires in 1.4 too

That last group matters as much as the first. `deliverables/BREAKAGES.md` is only for things
that worked in 1.4 and stopped working in 2.0 — an N+1 is a performance bug and a
detached instance is a lifecycle bug, and putting either in the corpus would seed
Phase 2 with questions no upgrading user would ask.
"""

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import DetachedInstanceError

from experiments.sqlalchemy_1_4_vs_2_0 import models
from experiments.sqlalchemy_1_4_vs_2_0.seed import make_engine


def open_issues_for_project(session, project_name):
    """
    Legacy Query API. Measured: emits **no warning** even under WARN_20, and still
    works in 2.0 — this is a style migration, not a breakage. Kept because the
    upgrade guide pushes select(), and because "does this actually break?" is
    exactly the question deliverables/BREAKAGES.md has to answer honestly.
    """
    return (
        session.query(models.Issue)
        .join(models.Project)
        .filter(models.Project.name == project_name)
        .filter(models.Issue.status == "open")
        .order_by(models.Issue.created_at)
        .all()
    )


def get_issue(session, issue_id):
    """
    Query.get(). Measured: LegacyAPIWarning under WARN_20. Deprecated, but it still
    runs in 2.0 — a warning to fix, not a crash to fix. → session.get(Model, pk)
    """
    return session.query(models.Issue).get(issue_id)


def count_issues_raw(engine):
    """
    The one genuine breakage in this file. Two RemovedIn20Warnings from one line:
      1. engine.execute(...)  — "connectionless execution", removed in 2.0
      2. a bare SQL string    — 2.0 requires text()

    This is what Step 8 will actually crash on.
    """
    result = engine.execute("SELECT COUNT(*) FROM issues")
    return result.scalar()


def issue_report(session):
    """
    The N+1. Both attribute reads inside the loop are lazy loads, but only ONE of
    them is an N+1, and the difference is worth knowing before you "fix" it:

      .comments  one-to-many  -> 200 queries. A collection is never in the
                                 identity map as a collection, so every issue pays.
      .project   many-to-one  -> 3 queries. One object with a known PK, so the
                                 identity map answers after the first miss per
                                 project — and there are 3 projects in the seed.

    204 total, counted (migration.py §7), not the 401 the obvious arithmetic
    suggests. Left deliberately unoptimised — Step 5 counts what this costs, Step 9
    fixes it and compares. See CONCEPTS §15 and MIGRATION-2.0 §21.
    """
    lines = []
    for issue in session.query(models.Issue).all():
        lines.append(
            f"[{issue.status:<11}] {issue.project.name:<9} "
            f"{len(issue.comments)} comments  {issue.title[:44]}"
        )
    return lines


def fetch_issue_then_close(engine, issue_id):
    """
    Returns a *detached* Issue: the session that loaded it is already closed by
    the time the caller gets the object.

    `.title` still works — it was loaded before the close. `.comments` was never
    loaded, and there is no session left to load it with. See CONCEPTS §14.
    """
    session = sessionmaker(bind=engine)()
    issue = session.query(models.Issue).get(issue_id)
    _ = issue.title          # force the row to load while we still can
    session.close()
    return issue


if __name__ == "__main__":
    engine = make_engine()
    session = sessionmaker(bind=engine)()

    print("=" * 68)
    print("1. open issues for Apollo (legacy Query API)")
    print("=" * 68)
    apollo_open = open_issues_for_project(session, "Apollo")
    print(f"{len(apollo_open)} open issues")
    for issue in apollo_open[:3]:
        print(f"   #{issue.id:<4} {issue.title}")

    print()
    print("=" * 68)
    print("2. fetch one issue (Query.get)")
    print("=" * 68)
    print("  ", get_issue(session, 42))

    print()
    print("=" * 68)
    print("3. raw count (engine.execute, bare string)")
    print("=" * 68)
    print("   issues in table:", count_issues_raw(engine))

    print()
    print("=" * 68)
    print("4. report over all 200 issues — the N+1")
    print("=" * 68)
    report = issue_report(session)
    print(f"{len(report)} lines. first three:")
    for line in report[:3]:
        print("  ", line)

    print()
    print("=" * 68)
    print("5. detached instance")
    print("=" * 68)
    detached = fetch_issue_then_close(engine, 42)
    print("   .title on a detached object :", detached.title[:40])
    try:
        n = len(detached.comments)
        print(f"   .comments on a detached object: {n}  <- expected a failure here")
    except DetachedInstanceError as exc:
        print("   .comments on a detached object: DetachedInstanceError")
        print("     ", str(exc).split("\n")[0][:96])

    session.close()
