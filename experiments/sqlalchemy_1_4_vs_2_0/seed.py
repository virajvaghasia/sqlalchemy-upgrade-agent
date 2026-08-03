"""
seed.py — build a database big enough for the problems to show up.

`explore.py` seeds 21 rows you can hold in your head. This seeds ~200 issues, which
is the point: an N+1 over 9 rows is a curiosity, an N+1 over 200 is a bug you can
measure. Step 5 counts the queries against this data, and Step 9 compares.

Writes a real SQLite **file** (not in-memory), because `app.py` in Step 4 needs to
open the same database in a separate process.

Run:  uv run python -m experiments.sqlalchemy_1_4_vs_2_0.seed

Re-running drops and rebuilds — the row counts stay identical because RANDOM_SEED is
fixed, so the query counts you write down in Step 5 remain reproducible.
"""

import random
from datetime import datetime, timedelta

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker

from experiments.sqlalchemy_1_4_vs_2_0 import models

DB_PATH = "issues.db"
DB_URL = f"sqlite:///{DB_PATH}"

# Fixed so the counts never move between runs. If this changed run to run, the
# "202 queries before, 2 after" comparison in Step 9 would be meaningless.
RANDOM_SEED = 20260803

N_ISSUES = 200
START = datetime(2026, 1, 1, 9, 0)

USERS = [
    ("Alice Nguyen", "alice@example.com"),
    ("Bob Okafor", "bob@example.com"),
    ("Chandra Rao", "chandra@example.com"),
    ("Dana Whitfield", "dana@example.com"),
    ("Eli Bergstrom", "eli@example.com"),
]

PROJECTS = ["Apollo", "Borealis", "Cinder"]

LABELS = [
    "bug", "urgent", "ui", "backend",
    "regression", "docs", "perf", "good-first-issue",
]

AREAS = [
    "Login page", "Dashboard", "CSV export", "Search", "Email digest",
    "Issue detail", "Bulk close", "Avatar upload", "Filter bar", "Audit log",
    "Webhook delivery", "Timeline view", "Saved views", "Keyboard shortcuts",
    "Project settings", "Label picker", "Comment editor", "Notification bell",
    "API pagination", "Session refresh",
]

PROBLEMS = [
    "returns 500 on submit", "times out past 50 rows", "renders blank for new users",
    "loses state on browser back", "double-fires on slow networks",
    "ignores the timezone setting", "shows stale data after an edit",
    "rejects valid input", "leaks the previous user's filter",
    "breaks under RTL layout",
]

BODIES = [
    "Reproduced on staging — attaching the trace.",
    "Can't reproduce locally; might be environment-specific.",
    "This regressed somewhere in the last two releases.",
    "Patch is up, needs a second pair of eyes.",
    "Root cause is the permission check reading the wrong field.",
    "Duplicate of an older report, but this one has better steps.",
    "Works after a hard refresh, so likely a cache issue.",
    "Bumping — still hitting this daily.",
]

ROLES = ["owner", "reviewer", "watcher"]


def make_engine(echo=False):
    """Single source of truth for the DB location, imported by app.py in Step 4."""
    return create_engine(DB_URL, echo=echo)


def seed(engine):
    rng = random.Random(RANDOM_SEED)

    # Drop first so re-running is idempotent rather than additive.
    models.Base.metadata.drop_all(engine)
    models.Base.metadata.create_all(engine)

    session = sessionmaker(bind=engine)()

    users = [models.User(name=n, email=e) for n, e in USERS]
    projects = [
        models.Project(name=n, created_at=START + timedelta(days=i * 3))
        for i, n in enumerate(PROJECTS)
    ]
    labels = [models.Label(name=n) for n in LABELS]
    session.add_all(users + projects + labels)
    session.flush()

    issues = []
    for n in range(N_ISSUES):
        created = START + timedelta(hours=n * 7, minutes=rng.randrange(60))
        issue = models.Issue(
            title=f"{rng.choice(AREAS)} {rng.choice(PROBLEMS)}",
            description=rng.choice(BODIES),
            # weighted so most issues are open — a realistic backlog, and it makes
            # the "list open issues" query in Step 4 return something interesting
            status=rng.choices(
                ["open", "in_progress", "closed"], weights=[6, 2, 3]
            )[0],
            created_at=created,
        )
        # Attach to a project via the relationship, never by writing project_id.
        # The save-update cascade pulls the issue into the session too (CONCEPTS §14).
        rng.choice(projects).issues.append(issue)
        issues.append(issue)

        # 1–3 labels, sampled without replacement: the issue_labels PK is the pair,
        # so the same label twice on one issue would be an IntegrityError.
        for label in rng.sample(labels, rng.randrange(1, 4)):
            issue.labels.append(label)

        # 2–5 comments, each by some user
        for _ in range(rng.randrange(2, 6)):
            comment = models.Comment(
                body=rng.choice(BODIES),
                created_at=created + timedelta(hours=rng.randrange(1, 200)),
            )
            comment.issue = issue
            comment.author = rng.choice(users)

        # 1–2 assignments with distinct users — IssueAssignment's PK is
        # (issue_id, user_id), so the same person cannot hold two roles here.
        for user, role in zip(
            rng.sample(users, rng.randrange(1, 3)), rng.sample(ROLES, 2)
        ):
            a = models.IssueAssignment(
                role=role, assigned_at=created + timedelta(hours=1)
            )
            a.issue = issue
            a.user = user

    session.flush()

    # Blocking pairs. Guard against self-blocks and duplicates: both would violate
    # the composite PK or produce a nonsense row.
    seen = set()
    for _ in range(60):
        blocker, blocked = rng.sample(issues, 2)
        pair = (blocker.id, blocked.id)
        if pair in seen or (pair[1], pair[0]) in seen:
            continue
        seen.add(pair)
        blocker.blocks.append(blocked)

    session.commit()
    return session


def report(session, engine):
    counts = [
        ("users", session.query(models.User).count()),
        ("projects", session.query(models.Project).count()),
        ("issues", session.query(models.Issue).count()),
        ("labels", session.query(models.Label).count()),
        ("comments", session.query(models.Comment).count()),
        ("issue_assignments", session.query(models.IssueAssignment).count()),
        ("issue_labels", len(session.execute(models.issue_labels.select()).fetchall())),
        ("issue_blocks", len(session.execute(models.issue_blocks.select()).fetchall())),
    ]
    width = max(len(name) for name, _ in counts)
    print(f"seeded {DB_PATH}\n")
    for name, n in counts:
        print(f"  {name:<{width}}  {n:>5}")

    print("\nby status:")
    for status in ("open", "in_progress", "closed"):
        n = session.query(models.Issue).filter(models.Issue.status == status).count()
        print(f"  {status:<12}  {n:>5}")


if __name__ == "__main__":
    engine = make_engine()
    session = seed(engine)
    report(session, engine)
    session.close()
