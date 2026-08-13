"""
patterns.py — the 1.4 patterns under test, shared by candidates.py and verify_2_0.py.

One list, imported by both, so a prediction and its verification can never drift
apart. Everything is wrapped in a lambda: nothing here executes at import time,
which is what lets this module load on 1.4 AND on 2.0 even though several of the
cases are constructs 2.0 removed entirely.

Deliberately, the fixture attaches issues with `project.issues.append(issue)` —
the collection side — because that is the direction that survives 2.0
(MIGRATION-2.0.md §17). If the fixture used the many-to-one side, every case
below would run against an empty database on 2.0 and the results would be
garbage.
"""

import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import joinedload, sessionmaker, subqueryload

from experiments.sqlalchemy_1_4_vs_2_0 import models

Issue = models.Issue


def fixture(**kwargs):
    """Two projects' worth of rows, built the way that works on both versions."""
    engine = create_engine("sqlite://", **kwargs)
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, **kwargs)()
    project = models.Project(name="apollo")
    session.add(project)
    for n in range(2):
        issue = models.Issue(title=f"issue {n}", status="open")
        project.issues.append(issue)
        issue.comments.append(models.Comment(body="a comment"))
    session.commit()
    return engine, session


# (group, [(label, 1.4 source shown in reports, callable)])
GROUPS = [
    ("raw SQL / connectionless", [
        ("engine.execute(string)", 'engine.execute("SELECT 1")',
         lambda e, s: e.execute("SELECT 1")),
        ("engine.scalar(string)", 'engine.scalar("SELECT 1")',
         lambda e, s: e.scalar("SELECT 1")),
        ("conn.execute(bare string)", 'engine.connect().execute("SELECT 1")',
         lambda e, s: e.connect().execute("SELECT 1")),
        ("session.execute(bare string)", 'session.execute("SELECT 1")',
         lambda e, s: s.execute("SELECT 1")),
    ]),
    ("schema / reflection helpers", [
        ("engine.table_names()", "engine.table_names()",
         lambda e, s: e.table_names()),
        ("engine.has_table()", 'engine.has_table("issues")',
         lambda e, s: e.has_table("issues")),
        ("MetaData(bind=engine)", "MetaData(bind=engine)",
         lambda e, s: sa.MetaData(bind=e)),
    ]),
    ("statement construction", [
        ("select([...]) list form", "select([Issue.id])",
         lambda e, s: s.execute(select([Issue.id])).all()),
        ("case([...]) list form", 'case([(Issue.id == 1, "a")], else_="b")',
         lambda e, s: s.execute(select(sa.case([(Issue.id == 1, "a")], else_="b"))).all()),
        ("orm.relation() alias", "sqlalchemy.orm.relation(Comment)",
         lambda e, s: sa.orm.relation(models.Comment)),
    ]),
    ("Query API", [
        ("Query.filter(raw string)", 'query(Issue).filter("status=\'open\'")',
         lambda e, s: s.query(Issue).filter("status='open'").all()),
        ("Query.from_self()", "query(Issue).from_self()",
         lambda e, s: s.query(Issue).from_self().all()),
        ("Query.join(aliased=True)", "query(Issue).join(Comment, aliased=True)",
         lambda e, s: s.query(Issue).join(models.Comment, aliased=True).all()),
        ("Query.get(pk)", "query(Issue).get(1)",
         lambda e, s: s.query(Issue).get(1)),
    ]),
    ("loader options as strings", [
        ("joinedload(string)", 'query(Issue).options(joinedload("comments"))',
         lambda e, s: s.query(Issue).options(joinedload("comments")).all()),
        ("subqueryload(string)", 'query(Issue).options(subqueryload("comments"))',
         lambda e, s: s.query(Issue).options(subqueryload("comments")).all()),
    ]),
    ("results and rows", [
        ("Row attr access, no .scalars()", "session.execute(select(Issue)).all()[0].title",
         lambda e, s: s.execute(select(Issue)).all()[0].title),
        # These two build the row through a path that works on BOTH versions
        # (connect() + text()), so that what is under test is the ROW API and
        # not engine.execute(). An earlier version used engine.execute() here
        # and only ever re-measured that; both cases reported the same
        # "'Engine' object has no attribute 'execute'" and told us nothing.
        ("row['colname'] mapping access", 'conn.execute(text("SELECT id FROM issues")).fetchone()["id"]',
         lambda e, s: e.connect().execute(sa.text("SELECT id FROM issues")).fetchone()["id"]),
        ("row.keys()", 'conn.execute(text("SELECT id FROM issues")).fetchone().keys()',
         lambda e, s: e.connect().execute(sa.text("SELECT id FROM issues")).fetchone().keys()),
        ("joinedload(coll), no .unique()", "execute(select(Issue).options(joinedload(Issue.comments))).all()",
         lambda e, s: s.execute(select(Issue).options(joinedload(Issue.comments))).all()),
    ]),
    ("session lifecycle", [
        ("Session(autocommit=True)", "sessionmaker(bind=engine, autocommit=True)()",
         lambda e, s: sessionmaker(bind=e, autocommit=True)()),
        ("session.begin(subtransactions)", "session.begin(subtransactions=True)",
         lambda e, s: s.begin(subtransactions=True)),
        ("session.transaction attribute", "session.transaction",
         lambda e, s: s.transaction),
    ]),
    ("mapping / imports", [
        ("declarative_base from ext", "from sqlalchemy.ext.declarative import declarative_base",
         lambda e, s: __import__("sqlalchemy.ext.declarative", fromlist=["x"]).declarative_base()),
    ]),
]


def all_cases():
    for group, cases in GROUPS:
        for label, source, fn in cases:
            yield group, label, source, fn


# ---------------------------------------------------------------------------
# The 2.0 replacement for each pattern above.
# ---------------------------------------------------------------------------
# These are DRAFTS for deliverables/BREAKAGES.md, and they are drafts in a specific sense:
# every one is executed on real 2.0 by verify_2_0.py, so "it runs" is measured,
# not claimed. What is NOT measured is whether it is the fix YOU want — several
# have more than one reasonable answer, and the note says so where that is true.
#
# keyed by the label used in GROUPS above
FIXES = {
    "engine.execute(string)": (
        'with engine.connect() as conn:\n    conn.execute(text("SELECT 1"))',
        "Connectionless execution is gone. The connection — and therefore the transaction "
        "boundary — becomes visible in the source.",
        lambda e, s: [e.connect().execute(sa.text("SELECT 1"))],
    ),
    "engine.scalar(string)": (
        'with engine.connect() as conn:\n    conn.scalar(text("SELECT 1"))',
        "Same removal as engine.execute(); .scalar() still exists on Connection.",
        lambda e, s: [e.connect().scalar(sa.text("SELECT 1"))],
    ),
    "conn.execute(bare string)": (
        'conn.execute(text("SELECT 1"))',
        "A bare string is no longer coerced. text() makes 'this is raw SQL, I mean it' "
        "explicit — and greppable during an audit.",
        lambda e, s: [e.connect().execute(sa.text("SELECT 1"))],
    ),
    "session.execute(bare string)": (
        'session.execute(text("SELECT 1"))',
        "Same rule on the Session as on the Connection.",
        lambda e, s: [s.execute(sa.text("SELECT 1"))],
    ),
    "engine.table_names()": (
        "inspect(engine).get_table_names()",
        "Reflection helpers moved off Engine and onto the Inspector, which is where the rest "
        "of them already lived.",
        lambda e, s: [sa.inspect(e).get_table_names()],
    ),
    "engine.has_table()": (
        'inspect(engine).has_table("issues")',
        "Same move to the Inspector.",
        lambda e, s: [sa.inspect(e).has_table("issues")],
    ),
    "MetaData(bind=engine)": (
        "MetaData()   # then pass the engine explicitly:\n"
        "metadata.create_all(engine)",
        "Implicit binding is gone everywhere. The engine is passed at the point of use, so "
        "you can read which database a statement goes to.",
        lambda e, s: [sa.MetaData()],
    ),
    "select([...]) list form": (
        "select(Issue.id)",
        "Columns are positional now, not a list. 2.0's own error suggests this fix.",
        lambda e, s: [s.execute(select(Issue.id)).all()],
    ),
    "case([...]) list form": (
        'case((Issue.id == 1, "a"), else_="b")',
        "The whens became positional, matching select().",
        lambda e, s: [s.execute(select(sa.case((Issue.id == 1, "a"), else_="b"))).all()],
    ),
    "orm.relation() alias": (
        "sqlalchemy.orm.relationship(Comment)",
        "relation() was an alias for relationship() kept since 0.x. Only the long name "
        "survives.",
        lambda e, s: [sa.orm.relationship(models.Comment)],
    ),
    "Query.filter(raw string)": (
        'query(Issue).filter(Issue.status == "open")\n'
        '# or, if it really must be SQL:  .filter(text("status=\'open\'"))',
        "The column expression is better than text() here: it is checked, and it composes. "
        "text() is the escape hatch, not the fix.",
        lambda e, s: [s.query(Issue).filter(Issue.status == "open").all()],
    ),
    "Query.from_self()": (
        "subq = select(Issue).subquery()\n"
        "inner = aliased(Issue, subq)\n"
        "session.execute(select(inner)).scalars().all()",
        "from_self() was removed as too implicit. You now name the subquery and alias the "
        "entity onto it, which is what it was doing invisibly.",
        lambda e, s: [
            s.execute(select(sa.orm.aliased(Issue, select(Issue).subquery()))).scalars().all()
        ],
    ),
    "Query.join(aliased=True)": (
        "target = aliased(Comment)\n"
        "query(Issue).join(target, Issue.comments)",
        "The implicit aliasing flag is gone; you create the alias and join to it.",
        lambda e, s: [
            (lambda t: s.query(Issue).join(t, Issue.comments).all())(sa.orm.aliased(models.Comment))
        ],
    ),
    "joinedload(string)": (
        "query(Issue).options(joinedload(Issue.comments))",
        "Strings are not accepted for attribute names in loader options. The class-bound "
        "attribute is checked at construction instead of at query time.",
        lambda e, s: [s.query(Issue).options(joinedload(Issue.comments)).all()],
    ),
    "subqueryload(string)": (
        "query(Issue).options(subqueryload(Issue.comments))",
        "Same rule for every loader option.",
        lambda e, s: [s.query(Issue).options(subqueryload(Issue.comments)).all()],
    ),
    "Row attr access, no .scalars()": (
        "session.execute(select(Issue)).scalars().all()[0].title",
        "execute() returns Rows; .scalars() projects to the first column. Only add it when "
        "you selected ONE thing — on a wider select it silently discards the rest.",
        lambda e, s: [s.execute(select(Issue)).scalars().all()[0].title],
    ),
    "row['colname'] mapping access": (
        'row._mapping["id"]',
        "Row is a named tuple in 2.0. The dict-like view moved to ._mapping, so the two "
        "access styles stopped overlapping.",
        lambda e, s: [
            e.connect().execute(sa.text("SELECT id FROM issues")).fetchone()._mapping["id"]
        ],
    ),
    "row.keys()": (
        "row._mapping.keys()",
        "Same move. On 2.0 a bare .keys() is read as a COLUMN lookup, which is why the error "
        "says 'Could not locate column'.",
        lambda e, s: [
            e.connect().execute(sa.text("SELECT id FROM issues")).fetchone()._mapping.keys()
        ],
    ),
    "joinedload(coll), no .unique()": (
        "session.execute(stmt).unique().scalars().all()",
        "Only for joined eager loads against a COLLECTION. On entities .unique() dedupes by "
        "primary key, so it can only remove copies the JOIN invented.",
        lambda e, s: [
            s.execute(select(Issue).options(joinedload(Issue.comments))).unique().scalars().all()
        ],
    ),
    "Session(autocommit=True)": (
        "Session(bind=engine)      # autobegin: the transaction opens on first use\n"
        "...\nsession.commit()          # and you end it explicitly",
        "Library-level autocommit is removed outright — there is no replacement flag. The "
        "transaction now begins on first use and ends where you say.",
        lambda e, s: [sessionmaker(bind=e)()],
    ),
    "session.begin(subtransactions)": (
        "session.begin_nested()    # a real SAVEPOINT",
        "Subtransactions were a bookkeeping fiction that emitted no SQL. begin_nested() "
        "issues an actual SAVEPOINT.",
        lambda e, s: [s.begin_nested()],
    ),
    "session.transaction attribute": (
        "session.get_transaction()        # or session.in_transaction()",
        "The attribute became a method, so 'is there a transaction?' is a question you ask "
        "rather than an object you poke at.",
        lambda e, s: [s.get_transaction(), s.in_transaction()],
    ),
}


# ---------------------------------------------------------------------------
# Where each pattern is explained IN THIS REPO.
# ---------------------------------------------------------------------------
# Deliberately not upstream URLs. SQLAlchemy's own warnings carry only a
# generic 2.0 background link (sqlalche.me/e/b8d9) for every one of these, so
# a per-pattern upstream anchor would be something I recalled rather than
# measured — exactly the habit CLAUDE.md forbids. These refs are checked
# against the files by verify_2_0.py at generation time.
DOC_SECTIONS = {
    "engine.execute(string)":              ["MIGRATION-2.0.md §16", "MIGRATION-2.0.md §19"],
    "engine.scalar(string)":               ["MIGRATION-2.0.md §16"],
    "conn.execute(bare string)":           ["MIGRATION-2.0.md §16", "MIGRATION-2.0.md §19"],
    "session.execute(bare string)":        ["MIGRATION-2.0.md §16"],
    "engine.table_names()":                ["MIGRATION-2.0.md §16"],
    "engine.has_table()":                  ["MIGRATION-2.0.md §16"],
    "MetaData(bind=engine)":               ["MIGRATION-2.0.md §16", "MIGRATION-2.0.md §18"],
    "select([...]) list form":             ["MIGRATION-2.0.md §16"],
    "case([...]) list form":               ["MIGRATION-2.0.md §16"],
    "orm.relation() alias":                ["MIGRATION-2.0.md §16", "CONCEPTS.md §6"],
    "Query.filter(raw string)":            ["MIGRATION-2.0.md §16"],
    "Query.from_self()":                   ["MIGRATION-2.0.md §16"],
    "Query.join(aliased=True)":            ["MIGRATION-2.0.md §16", "CONCEPTS.md §9"],
    "joinedload(string)":                  ["MIGRATION-2.0.md §17", "CONCEPTS.md §15"],
    "subqueryload(string)":                ["MIGRATION-2.0.md §17", "CONCEPTS.md §15"],
    "Row attr access, no .scalars()":      ["MIGRATION-2.0.md §17"],
    "row['colname'] mapping access":       ["MIGRATION-2.0.md §17"],
    "row.keys()":                          ["MIGRATION-2.0.md §17"],
    "joinedload(coll), no .unique()":      ["MIGRATION-2.0.md §17", "CONCEPTS.md §15"],
    "Session(autocommit=True)":            ["MIGRATION-2.0.md §18", "CONCEPTS.md §14"],
    "session.begin(subtransactions)":      ["MIGRATION-2.0.md §18"],
    "session.transaction attribute":       ["MIGRATION-2.0.md §18"],
}


# ---------------------------------------------------------------------------
# Where more than one fix is defensible.
# ---------------------------------------------------------------------------
# FIXES above gives one answer per pattern, which quietly hides a choice on the
# entries that have several. Presenting a single draft as "the" fix is the same
# failure as an asserted number: it looks settled when it isn't.
#
# Every alternative here is executed on real 2.0 by verify_2_0.py, exactly like
# the primary fix — so what is offered is a set of options that all provably
# run, and the pick between them is a judgement about YOUR code.
#
# label -> [(code, when you would prefer this, callable), ...]
ALTERNATIVES = {
    "Query.filter(raw string)": [
        ('query(Issue).filter(text("status=\'open\'"))',
         "when the SQL genuinely has to stay SQL — a dialect feature, or a WHERE clause "
         "assembled elsewhere. You keep raw SQL, and text() makes it greppable. You lose "
         "the checking the column expression gives you.",
         lambda e, s: s.query(Issue).filter(sa.text("status='open'")).all()),
    ],
    "Row attr access, no .scalars()": [
        ("session.execute(select(Issue)).all()[0][0].title",
         "when you selected several columns and still want the Row — index into it instead "
         "of projecting. .scalars() would throw the other columns away, silently.",
         lambda e, s: s.execute(select(Issue)).all()[0][0].title),
    ],
    "row['colname'] mapping access": [
        ("row.id",
         "when the column name is a valid Python identifier — Row is a named tuple in 2.0, "
         "so attribute access is the natural spelling. ._mapping is for names that are not "
         "identifiers, or when you need the whole dict.",
         lambda e, s: e.connect().execute(sa.text("SELECT id FROM issues")).fetchone().id),
    ],
    "row.keys()": [
        ("row._fields",
         "the named-tuple field names, without building the mapping view. Same information; "
         "._mapping.keys() is the closer analogue if you were treating the row as a dict.",
         lambda e, s: e.connect().execute(sa.text("SELECT id FROM issues")).fetchone()._fields),
    ],
    "joinedload(coll), no .unique()": [
        ("session.execute(select(Issue).options(selectinload(Issue.comments))).scalars().all()",
         "the better answer in most cases: selectinload does not JOIN, so it never multiplies "
         "rows, so .unique() is not needed at all. Prefer this unless you specifically want "
         "one round trip — see study/01-CONCEPTS.md §15 for the tradeoff.",
         lambda e, s: s.execute(
             select(Issue).options(sa.orm.selectinload(Issue.comments))).scalars().all()),
    ],
}
