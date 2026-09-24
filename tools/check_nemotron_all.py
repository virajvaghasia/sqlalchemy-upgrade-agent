"""Phase 6, Step 4f — are nemotron's 53 delivered answers CORRECT? Each central claim, executed.

    uv run --no-project --with 'sqlalchemy==2.0.51' --with aiosqlite --with greenlet python tools/check_nemotron_all.py

WHAT IT CHECKS

The 53 answers that count toward Step 4d's 0.58 (answerable, page in the prompt,
answered), listed in `deliverables/nemotron-all-delivered.json`, which
`rag.escalate --all --write-delivered` derives from the rows and a test pins.
Step 3e's `tools/check_escalated.py` does not carry over: today's answers are new
text (0 of 53 identical to the saved escalations).

HOW EACH CHECK WAS WRITTEN (Phase 6 Step 4f, rules written first)

- Claude read each answer and wrote its central checkable claim as the `CLAIM`
  string, BEFORE this file was ever run, and committed it before the first run.
- A check tests the old behaviour the answer says is gone AND the new behaviour
  it recommends. Exceptions are narrow.
- Where an answer also contains a secondary slip, the CLAIM string says so in
  words, so the verdict on the central claim does not hide it.
- `NOT_CHECKABLE` (typing, advice, "the sources do not cover X") never counts as
  correct. A crash inside a check is `ERROR`, never a verdict on the answer.
- Claims about 1.4 behaviour run in a pinned 1.4.52 subprocess, like Step 3e's g058.
- **Claude wrote these checks. This is not a human verdict.**
"""

import asyncio
import contextlib
import enum
import json
import os
import pathlib
import subprocess
import sys
import typing
import warnings

import sqlalchemy as sa
from sqlalchemy import event, exc, orm, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

ROOT = pathlib.Path(__file__).resolve().parent.parent
PIN = "2.0.51"
NOT_CHECKABLE = "NOT_CHECKABLE"
BAR = 0.80   # Phase 6 Step 4f: >= 80% of checkable answers pass


def raises(fn, *types) -> bool:
    try:
        fn()
    except types:
        return True
    return False


def models():
    class Base(DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(default="x")
        addresses: Mapped[list["Address"]] = relationship(back_populates="user")

    class Address(Base):
        __tablename__ = "addresses"
        id: Mapped[int] = mapped_column(primary_key=True)
        email: Mapped[str] = mapped_column(default="e")
        user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
        user: Mapped["User"] = relationship(back_populates="addresses")

    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Base, User, Address, engine


def table():
    return sa.Table("t", sa.MetaData(), sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("x", sa.Integer), sa.Column("y", sa.Integer))


def savepoint_engine():
    """pysqlite's own transaction handling breaks SAVEPOINT; this is the documented
    SQLAlchemy recipe that makes SQLite savepoints behave (written before any run)."""
    engine = sa.create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")
    return engine


def on_14(code: str, warn20: bool) -> str:
    """Run `code` under sqlalchemy 1.4.52 in a throwaway interpreter; return stdout."""
    env = {k: v for k, v in os.environ.items() if k != "SQLALCHEMY_WARN_20"}
    if warn20:
        env["SQLALCHEMY_WARN_20"] = "1"
    out = subprocess.run(["uv", "run", "--no-project", "--with", "sqlalchemy==1.4.52", "python", "-c", code],
                         capture_output=True, text=True, env=env)
    return out.stdout.strip()


REMOVED_IN_20_COUNT = (
    "import warnings, sqlalchemy as sa\n"
    "e = sa.create_engine('sqlite://')\n"
    "with warnings.catch_warnings(record=True) as w:\n"
    "    warnings.simplefilter('always')\n"
    "    e.execute(sa.text('select 1'))\n"
    "print(sum(x.category.__name__ == 'RemovedIn20Warning' for x in w))\n"
)

# CORRECTED AFTER THE FIRST RUN: g027 and g055 first used the count above
# and read "with 1, without 1". Without SQLALCHEMY_WARN_20, 1.4.52 still emits ONE RemovedIn20Warning,
# the summary "Deprecated API features detected! ... set SQLALCHEMY_WARN_20=1 to show all"; with it,
# the specific warning naming Engine.execute(). The claim "setting it turns the warnings on" is about
# the specific ones, so these two count warnings other than the summary. g078's claim ("leaving it
# unset suppresses them") is about ANY such warning and keeps the count above, unchanged.
SPECIFIC_REMOVED_IN_20_COUNT = REMOVED_IN_20_COUNT.replace(
    "x.category.__name__ == 'RemovedIn20Warning'",
    "x.category.__name__ == 'RemovedIn20Warning' and not str(x.message).startswith('Deprecated API features detected')")


# --- the 53 --------------------------------------------------------------------

def g002():
    CLAIM = ("Query.from_self() is gone in 2.0; select(...).subquery() + aliased(User, subq) / "
             "aliased(Address, subq) selects both entities from the subquery")
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(name="u", addresses=[Address(email="b"), Address(email="a")]))
        s.commit()
        old = not hasattr(s.query(User), "from_self")
        # The answer's code AS WRITTEN: select(ua, aa).order_by(aa.email) over a subquery that
        # selected User plus only Address.email. If the recommended code raises, the answer is
        # wrong (FAIL), not the check (ERROR).
        try:
            subq = sa.select(User, Address.email).join(User.addresses).subquery()
            ua, aa = orm.aliased(User, subq), orm.aliased(Address, subq)
            rows = s.execute(sa.select(ua, aa).order_by(aa.email)).all()
            new = (len(rows) == 2 and all(isinstance(r[0], User) for r in rows)
                   and [r[1].email for r in rows] == ["a", "b"])
        except (exc.SQLAlchemyError, AttributeError):
            new = False
        return CLAIM, old and new


def g004():
    CLAIM = ("Engine has no execute(); Connection.execute runs statements; a plain string is rejected, "
             "text() and exec_driver_sql() work; **kwargs parameters are rejected, a dict works")
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        old = (not hasattr(engine, "execute")
               and raises(lambda: c.execute("select 1"), exc.ObjectNotExecutableError)
               and raises(lambda: c.execute(text("select :x"), x=1), TypeError))
        new = (c.execute(text("select 1")).scalar() == 1 and c.exec_driver_sql("select 1").scalar() == 1
               and c.execute(text("select :x"), {"x": 5}).scalar() == 5)
    return CLAIM, old and new


def g006():
    CLAIM = "Session.execute also rejects a raw SQL string in 2.0; text() works"
    engine = sa.create_engine("sqlite://")
    with Session(engine) as s:
        old = raises(lambda: s.execute("select 1"), exc.ArgumentError)
        new = s.execute(text("select 1")).scalar() == 1
    return CLAIM, old and new


def g008():
    CLAIM = "select([cols]) is rejected in 2.0; select(col, col) positionally works"
    _, User, _, _ = models()
    old = raises(lambda: sa.select([User.id, User.name]), exc.ArgumentError, TypeError)
    return CLAIM, old and "users.name" in str(sa.select(User.id, User.name))


def g013():
    CLAIM = "subqueryload('addresses') with a string is rejected; subqueryload(User.addresses) works"
    _, User, _, _ = models()
    old = raises(lambda: sa.select(User).options(orm.subqueryload("addresses")), exc.ArgumentError)
    return CLAIM, old and bool(str(sa.select(User).options(orm.subqueryload(User.addresses))))


def g015():
    CLAIM = "row['id'] fails in 2.0; row._mapping['id'], result.mappings() and row.id work"
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        row = c.execute(text("select 7 as id")).first()
        old = raises(lambda: row["id"], TypeError, KeyError, IndexError)
        new = (row._mapping["id"] == 7 and row.id == 7
               and c.execute(text("select 7 as id")).mappings().first()["id"] == 7)
    return CLAIM, old and new


def g017():
    CLAIM = ("in 2.0, select(User).options(joinedload(User.addresses)) through session.execute "
             "raises unless .unique() is called; with .unique() the parents are not duplicated")
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(name="u", addresses=[Address(email="a"), Address(email="b")]))
        s.commit()
    stmt = sa.select(User).options(orm.joinedload(User.addresses))
    with Session(engine) as s:
        old = raises(lambda: s.execute(stmt).scalars().all(), exc.InvalidRequestError)
    with Session(engine) as s:
        new = len(s.execute(stmt).unique().scalars().all()) == 1
    return CLAIM, old and new


def g018():
    CLAIM = "Session(autocommit=True) is rejected in 2.0; Session + begin() + commit() persists"
    _, User, _, engine = models()
    old = raises(lambda: Session(engine, autocommit=True), TypeError, exc.ArgumentError)
    sess = Session(engine)
    sess.begin()
    sess.add(User(name="a"))
    sess.commit()
    sess.close()
    with Session(engine) as s:
        new = s.scalar(sa.select(sa.func.count()).select_from(User)) == 1
    return CLAIM, old and new


def g019():
    CLAIM = ("session.begin(subtransactions=True) is rejected in 2.0; the in_transaction() context-manager "
             "recipe nests without error and the outer block commits once")
    _, User, _, engine = models()

    @contextlib.contextmanager
    def transaction(session):
        if not session.in_transaction():
            with session.begin():
                yield
        else:
            yield

    with Session(engine) as s:
        old = raises(lambda: s.begin(subtransactions=True), TypeError)
    with Session(engine) as s:
        with transaction(s):
            with transaction(s):
                s.add(User(name="a"))
    with Session(engine) as s:
        new = s.scalar(sa.select(sa.func.count()).select_from(User)) == 1
    return CLAIM, old and new


def g021():
    CLAIM = "relationship(backref=...) still works in 2.0 (legacy); back_populates works"
    class Base(DeclarativeBase):
        pass

    class P(Base):
        __tablename__ = "p"
        id = mapped_column(sa.Integer, primary_key=True)
        kids = relationship("K", backref="parent")

    class K(Base):
        __tablename__ = "k"
        id = mapped_column(sa.Integer, primary_key=True)
        p_id = mapped_column(sa.ForeignKey("p.id"))

    orm.configure_mappers()
    _, User, Address, _ = models()
    return CLAIM, hasattr(K, "parent") and hasattr(Address, "user") and hasattr(User, "addresses")


def g024():
    CLAIM = "session.get(User, 5) is the replacement; Query.get() still exists as legacy (LegacyAPIWarning)"
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add(User(id=5, name="a"))
        s.commit()
        new = s.get(User, 5).name == "a"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            legacy = s.query(User).get(5).name == "a"
        warned = any(issubclass(x.category, exc.LegacyAPIWarning) for x in w)
    return CLAIM, new and legacy and warned


def g025():
    CLAIM = ("in 2.0 future= on create_engine is optional: future=True is accepted, future=False is "
             "rejected, and omitting it gives the same Engine")
    ok_true = isinstance(sa.create_engine("sqlite://", future=True), sa.Engine)
    rejected = raises(lambda: sa.create_engine("sqlite://", future=False), exc.ArgumentError)
    same = type(sa.create_engine("sqlite://")) is type(sa.create_engine("sqlite://", future=True))
    return CLAIM, ok_true and rejected and same


def g026():
    CLAIM = ("on 1.4, Session(future=True) removes subtransactions (begin(subtransactions=True) raises); "
             "in 2.0 future=True is accepted and future=False rejected")
    code = (
        "import sqlalchemy as sa\nfrom sqlalchemy.orm import Session\n"
        "e = sa.create_engine('sqlite://')\n"
        "s = Session(e, future=True)\n"
        "try:\n    s.begin(subtransactions=True)\n    print('no-raise')\n"
        "except Exception as x:\n    print(type(x).__name__)\n"
    )
    on14 = on_14(code, warn20=False)
    engine = sa.create_engine("sqlite://")
    in20 = (raises(lambda: Session(engine, future=False), exc.ArgumentError)
            and isinstance(Session(engine, future=True), Session))
    return CLAIM + f"   [1.4.52 said: {on14}]", on14 not in ("no-raise", "") and in20


def g027():
    CLAIM = "on 1.4, SQLALCHEMY_WARN_20=1 turns on RemovedIn20Warning (engine.execute warns only with it set)"
    with_var, without = on_14(SPECIFIC_REMOVED_IN_20_COUNT, True), on_14(SPECIFIC_REMOVED_IN_20_COUNT, False)
    return CLAIM + f"   [counts: with {with_var}, without {without}]", with_var not in ("", "0") and without == "0"


def g029():
    CLAIM = ("insert(t, values=...) and t.delete(whereclause) are rejected; insert().values().inline(), "
             ".returning(), delete().where(), update().ordered_values() work")
    t = table()
    old = (raises(lambda: sa.insert(t, values={"x": 10}), TypeError, exc.ArgumentError)
           and raises(lambda: t.delete(t.c.x > 15), TypeError, exc.ArgumentError))
    new = all(str(s) for s in (
        sa.insert(t).values(x=10, y=15).inline(),
        sa.insert(t).values({"x": 10, "y": 15}).returning(t.c.x),
        t.delete().where(t.c.x > 15),
        t.update().where(t.c.x < 15).ordered_values((t.c.y, 20), (t.c.x, t.c.y + 10)),
    ))
    return CLAIM, old and new


def g030():
    CLAIM = ("from sqlalchemy.orm import declarative_base works; the sqlalchemy.ext.declarative import "
             "still works but warns it moved; DeclarativeBase works")
    base = orm.declarative_base()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from sqlalchemy.ext.declarative import declarative_base as old_db
        old_db()
    moved = any(issubclass(x.category, exc.MovedIn20Warning) for x in w)

    class B(DeclarativeBase):
        pass
    return CLAIM, moved and base is not None and hasattr(B, "metadata")


def g031():
    CLAIM = "sqlalchemy.orm.mapper() is gone in 2.0; registry().map_imperatively() maps a class"
    # CORRECTED AFTER THE FIRST RUN: the first version tested whether
    # `from sqlalchemy.orm import mapper` fails. On 2.0.51 the name still imports, as a stub that
    # raises when CALLED ("The 'sqlalchemy.orm.mapper()' function is removed as of SQLAlchemy 2.0.
    # Use ... map_imperatively()"). The claim is that the function is replaced, so the check calls it.
    from sqlalchemy.orm import mapper

    class Old:
        pass
    old = raises(lambda: mapper(Old, sa.Table("old", sa.MetaData(), sa.Column("id", sa.Integer, primary_key=True))),
                 exc.InvalidRequestError)

    class Thing:
        pass
    reg = orm.registry()
    t = sa.Table("thing", reg.metadata, sa.Column("id", sa.Integer, primary_key=True))
    reg.map_imperatively(Thing, t)
    return CLAIM, old and sa.inspect(Thing).local_table is t


def g032():
    CLAIM = "query(User).join('orders', 'items') chained strings are rejected; individual join() calls work"
    class Base(DeclarativeBase):
        pass

    class U(Base):
        __tablename__ = "u"
        id: Mapped[int] = mapped_column(primary_key=True)
        orders: Mapped[list["O"]] = relationship()

    class O(Base):
        __tablename__ = "o"
        id: Mapped[int] = mapped_column(primary_key=True)
        u_id: Mapped[int] = mapped_column(sa.ForeignKey("u.id"))
        items: Mapped[list["I"]] = relationship()

    class I(Base):
        __tablename__ = "i"
        id: Mapped[int] = mapped_column(primary_key=True)
        o_id: Mapped[int] = mapped_column(sa.ForeignKey("o.id"))

    engine = sa.create_engine("sqlite://")
    with Session(engine) as s:
        old = raises(lambda: str(s.query(U).join("orders", "items")), exc.ArgumentError, TypeError)
        new = "JOIN i" in str(s.query(U).join(U.orders).join(O.items))
    return CLAIM, old and new


def g033():
    CLAIM = ("select(User, Address.email).join().distinct().order_by(Address.email) then "
             "session.execute(stmt).columns(User).all() returns only User per row")
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(name="u", addresses=[Address(email="a"), Address(email="b")]))
        s.commit()
        stmt = sa.select(User, Address.email).join(User.addresses).distinct().order_by(Address.email)
        rows = s.execute(stmt).columns(User).all()
        return CLAIM, len(rows) == 2 and all(len(r) == 1 and isinstance(r[0], User) for r in rows)


def g034():
    CLAIM = "select_entity_from is gone; aliased(User, select(User).where(...).subquery()) selects from it"
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add_all([User(name="somename1"), User(name="other")])
        s.commit()
        old = not hasattr(s.query(User), "select_entity_from")
        subq = sa.select(User).where(User.name.like("%somename%")).subquery()
        ua = orm.aliased(User, subq)
        u = s.execute(sa.select(ua).order_by(ua.id).limit(1)).scalars().first()
        return CLAIM, old and isinstance(u, User) and u.name == "somename1"


def g035():
    CLAIM = "statement caching is built in and automatic in 2.0: the second run of the same select is a cache hit"
    engine = sa.create_engine("sqlite://")
    t = table()
    t.metadata.create_all(engine)
    with engine.connect() as c:
        c.execute(sa.select(t).where(t.c.x == 1))
        r = c.execute(sa.select(t).where(t.c.x == 2))
        from sqlalchemy.engine import default   # CACHE_HIT is module-level (looked up before the first run)
        return CLAIM, r.context.cache_hit is default.CACHE_HIT


def g038():
    CLAIM = "session.execute(select(User)).scalars().all() and session.scalars(select(User)).all() both give User objects"
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add_all([User(name="a"), User(name="b")])
        s.commit()
        a = s.execute(sa.select(User)).scalars().all()
        b = s.scalars(sa.select(User)).all()
        return CLAIM, len(a) == len(b) == 2 and all(isinstance(u, User) for u in a + b)


def g041():
    CLAIM = "backref still works in 2.0; back_populates on both sides of a many-to-many works"
    class Base(DeclarativeBase):
        pass

    assoc = sa.Table("assoc", Base.metadata, sa.Column("p", sa.ForeignKey("parent.id")),
                     sa.Column("c", sa.ForeignKey("child.id")))

    class Parent(Base):
        __tablename__ = "parent"
        id = mapped_column(sa.Integer, primary_key=True)
        children = relationship("Child", secondary=assoc, back_populates="parents")

    class Child(Base):
        __tablename__ = "child"
        id = mapped_column(sa.Integer, primary_key=True)
        parents = relationship("Parent", secondary=assoc, back_populates="children")

    orm.configure_mappers()
    p, c = Parent(), Child()
    p.children.append(c)
    _, legacy = g021()
    return CLAIM, c.parents == [p] and legacy


def g043():
    CLAIM = "select(..., select_from=, order_by=) keyword arguments are rejected; .select_from().order_by() works"
    t = table()
    old = (raises(lambda: sa.select([1], select_from=t, order_by=t.c.id), exc.ArgumentError, TypeError)
           and raises(lambda: sa.select(t.c.x, order_by=t.c.id), TypeError, exc.ArgumentError))
    new = "ORDER BY t.id" in str(sa.select(1).select_from(t).order_by(t.c.id))
    return CLAIM, old and new


def g044():
    CLAIM = "Table(autoload=True) without an engine is gone; autoload_with=engine / connection and reflect(engine) work"
    engine = sa.create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table t (a integer, b text)")
    old = raises(lambda: sa.Table("t", sa.MetaData(), autoload=True), TypeError, exc.ArgumentError)
    with engine.connect() as c:
        via_conn = [col.name for col in sa.Table("t", sa.MetaData(), autoload_with=c).columns] == ["a", "b"]
    md = sa.MetaData()
    md.reflect(engine)
    new = ([col.name for col in sa.Table("t", sa.MetaData(), autoload_with=engine).columns] == ["a", "b"]
           and via_conn and "t" in md.tables)
    return CLAIM, old and new


def g045():
    CLAIM = "t.select().execute() is gone (a Select has no execute); connection.execute(t.select()) runs it"
    engine = sa.create_engine("sqlite://")
    t = table()
    t.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(t.insert().values(x=1, y=2))
    with engine.connect() as c:
        new = c.execute(t.select()).all() == [(1, 1, 2)]
    return CLAIM, (not hasattr(t.select(), "execute")) and new


def g046():
    CLAIM = ("Session(autocommit=True) is rejected; a Session autobegins on first database access; "
             "with session.begin(): commits")
    _, User, _, engine = models()
    old = raises(lambda: Session(engine, autocommit=True), TypeError, exc.ArgumentError)
    with Session(engine) as s:
        before = s.in_transaction()
        s.execute(text("select 1"))
        auto = (not before) and s.in_transaction()
    with Session(engine) as s:
        with s.begin():
            s.add(User(name="a"))
    with Session(engine) as s:
        committed = s.scalar(sa.select(sa.func.count()).select_from(User)) == 1
    return CLAIM, old and auto and committed


def g047():
    CLAIM = ("subtransactions are gone; the in_transaction() recipe nests; begin_nested() is a SAVEPOINT: "
             "rolling it back discards u3 and keeps u1, u2, which commit at the end of sessionmaker.begin()")
    engine = savepoint_engine()
    Base, User, _, _ = models()
    Base.metadata.create_all(engine)
    maker = orm.sessionmaker(engine)
    with Session(engine) as s:
        old = raises(lambda: s.begin(subtransactions=True), TypeError)
    with maker.begin() as session:
        session.add(User(name="u1"))
        session.add(User(name="u2"))
        nested = session.begin_nested()
        session.add(User(name="u3"))
        nested.rollback()
    with Session(engine) as s:
        names = sorted(s.scalars(sa.select(User.name)).all())
    return CLAIM, old and names == ["u1", "u2"]


def g048():
    CLAIM = "joinedload('addresses') with a string is removed; joinedload(User.addresses) works"
    _, User, _, _ = models()
    old = raises(lambda: sa.select(User).options(orm.joinedload("addresses")), exc.ArgumentError)
    return CLAIM, old and bool(str(sa.select(User).options(orm.joinedload(User.addresses))))


def g049():
    CLAIM = ("case() no longer accepts a list of WHENs in 2.0; case((cond, val), ...) positionally works. "
             "SECONDARY SLIP, not the verdict: the answer says the list form 'emits a deprecation warning', "
             "which is 1.4's behaviour; on 2.0 it is rejected")
    t = table()
    old = raises(lambda: sa.case([(t.c.x == 5, "five")], else_="n"), exc.ArgumentError, TypeError)
    return CLAIM, old and "CASE" in str(sa.case((t.c.x == 5, "five"), (t.c.x == 7, "seven"), else_="n"))


def g050():
    CLAIM = "Engine has no execute(), a Select has no execute(); with engine.connect() as conn: conn.execute(stmt) works"
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        new = c.execute(sa.select(sa.literal(1))).scalar() == 1
    return CLAIM, (not hasattr(engine, "execute")) and (not hasattr(sa.select(1), "execute")) and new


def g051():
    CLAIM = ("execute(select(User)).scalars().all() gives User objects; execute(select(User.name, User.id)).all() "
             "gives Row tuples; session.scalars() returns a ScalarResult")
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add_all([User(name="a"), User(name="b")])
        s.commit()
        scal = s.execute(sa.select(User)).scalars().all()
        rows = s.execute(sa.select(User.name, User.id)).all()
        return CLAIM, (all(isinstance(u, User) for u in scal)
                       and all(isinstance(r, sa.Row) and len(r) == 2 for r in rows)
                       and isinstance(s.scalars(sa.select(User)), sa.ScalarResult))


def g055():
    CLAIM = "on 1.4, SQLALCHEMY_WARN_20=1 enables RemovedIn20Warning"
    with_var, without = on_14(SPECIFIC_REMOVED_IN_20_COUNT, True), on_14(SPECIFIC_REMOVED_IN_20_COUNT, False)
    return CLAIM + f"   [counts: with {with_var}, without {without}]", with_var not in ("", "0") and without == "0"


def g062():
    CLAIM = ("Mapped[Literal[...]] with type_annotation_map {Literal: Enum(enum.Enum)} gives an Enum column "
             "with the literal's values; mapped_column(Enum(..., name='status_enum')) works explicitly. "
             "SECONDARY SLIP, not the verdict: approach 1's code uses enum.Enum without importing enum")
    Status = typing.Literal["pending", "received", "completed"]

    class Base1(DeclarativeBase):
        type_annotation_map = {typing.Literal: sa.Enum(enum.Enum)}

    class A(Base1):
        __tablename__ = "a"
        id: Mapped[int] = mapped_column(primary_key=True)
        status: Mapped[Status]

    class Base2(DeclarativeBase):
        pass

    class B(Base2):
        __tablename__ = "b"
        id: Mapped[int] = mapped_column(primary_key=True)
        status: Mapped[Status] = mapped_column(sa.Enum("pending", "received", "completed", name="status_enum"))

    ta, tb = A.__table__.c.status.type, B.__table__.c.status.type
    return CLAIM, (isinstance(ta, sa.Enum) and list(ta.enums) == ["pending", "received", "completed"]
                   and isinstance(tb, sa.Enum) and tb.name == "status_enum")


def g078():
    CLAIM = "on 1.4, RemovedIn20Warning is emitted only when SQLALCHEMY_WARN_20 is set, so leaving it unset suppresses them"
    with_var, without = on_14(REMOVED_IN_20_COUNT, True), on_14(REMOVED_IN_20_COUNT, False)
    return CLAIM + f"   [counts: with {with_var}, without {without}]", with_var not in ("", "0") and without == "0"


def g079():
    return ("the answer's point is that the sources do not cover options with Session.get; "
            "a claim that is only 'the sources do not cover X' is not executable"), NOT_CHECKABLE


def g080():
    CLAIM = ("select(Book).options(load_only(Book.title, Book.summary)) selects id, title, summary only; "
             "one load_only per entity; selectinload(User.books).load_only(Book.title) and defaultload(...) compile")
    class Base(DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "user_account"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]
        fullname: Mapped[str]
        books: Mapped[list["Book"]] = relationship()

    class Book(Base):
        __tablename__ = "book"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(sa.ForeignKey("user_account.id"))
        title: Mapped[str]
        summary: Mapped[str]
        cover: Mapped[str]

    one = str(sa.select(Book).options(orm.load_only(Book.title, Book.summary)))
    two = str(sa.select(User, Book).join_from(User, Book)
              .options(orm.load_only(User.name), orm.load_only(Book.title)))
    single = ("book.title" in one and "book.summary" in one and "book.id" in one and "cover" not in one)
    multi = "fullname" not in two and "summary" not in two
    loaders = all(str(sa.select(User).options(o)) for o in (
        orm.selectinload(User.books).load_only(Book.title), orm.defaultload(User.books).load_only(Book.title)))
    return CLAIM, single and multi and loaders


def g081():
    CLAIM = "Session(autobegin=False) refuses database work until begin() is called; with begin() it works"
    _, User, _, engine = models()
    with Session(engine, autobegin=False) as s:
        old = raises(lambda: s.execute(text("select 1")), exc.InvalidRequestError)
        s.begin()
        s.add(User(name="u1"))
        s.commit()
    with Session(engine) as s:
        new = s.scalar(sa.select(sa.func.count()).select_from(User)) == 1
    return CLAIM, old and new


def g083():
    CLAIM = ("there is no engine.execute() in 2.0; engine.begin() commits on exit, and "
             "engine.connect() + conn.commit() commits")
    engine = sa.create_engine("sqlite://")
    t = table()
    t.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(t.insert().values(x=1))
    with engine.connect() as c:
        c.execute(t.insert().values(x=2))
        c.commit()
    with engine.connect() as c:
        n = c.execute(sa.select(sa.func.count()).select_from(t)).scalar()
    return CLAIM, (not hasattr(engine, "execute")) and n == 2


def g087():
    CLAIM = ("a server_default column is NOT in __dict__ right after flush by default (expired, loaded on access); "
             "eager_defaults=True makes it present after flush")
    class Base(DeclarativeBase):
        pass

    class W(Base):
        __tablename__ = "w"
        id: Mapped[int] = mapped_column(primary_key=True)
        created: Mapped[str] = mapped_column(server_default=text("'now'"))

    class W2(Base):
        __tablename__ = "w2"
        id: Mapped[int] = mapped_column(primary_key=True)
        created: Mapped[str] = mapped_column(server_default=text("'now'"))
        __mapper_args__ = {"eager_defaults": True}

    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        w, w2 = W(), W2()
        s.add_all([w, w2])
        s.flush()
        expired = "created" not in w.__dict__
        present = "created" in w2.__dict__
        loads = w.created == "now"
        return CLAIM, expired and present and loads


def g088():
    CLAIM = ("Session(bind=connection, join_transaction_mode='create_savepoint') inside connection.begin(): "
             "session.commit() and session.rollback() touch only savepoints, and the outer rollback removes everything")
    engine = savepoint_engine()
    Base, User, _, _ = models()
    Base.metadata.create_all(engine)
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    session.add(User(name="bar"))
    session.flush()
    session.rollback()
    session.add(User(name="foo"))
    session.commit()
    inside = sorted(session.scalars(sa.select(User.name)).all()) == ["foo"]
    session.close()
    trans.rollback()
    connection.close()
    with Session(engine) as s:
        after = s.scalar(sa.select(sa.func.count()).select_from(User)) == 0
    return CLAIM, inside and after


def g090():
    return ("a typing question (load_only attrs typing on 2.0.0b4): not executable here"), NOT_CHECKABLE


def g095():
    CLAIM = ("populate_existing fully refreshes loaded instances, erasing pending changes; "
             "with selectinload it replaces the loaded collection")
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(id=1, name="a", addresses=[Address(email="x")]))
        s.commit()
        u = s.get(User, 1)
        _ = list(u.addresses)
        u.name = "changed"
        with engine.begin() as c:
            c.execute(sa.insert(Address.__table__).values(email="y", user_id=1))
        s.execute(sa.select(User).options(orm.selectinload(User.addresses))
                  .execution_options(populate_existing=True, autoflush=False)).scalars().all()
        return CLAIM, u.name == "a" and sorted(a.email for a in u.addresses) == ["x", "y"]


def g098():
    CLAIM = ("in 2.0 the backref cascade is gone: with u1 persistent, a1.user = u1 does not put a1 in the "
             "session, so it must be added explicitly; relationship(cascade_backrefs=False) is still accepted. "
             "NOTE: one bullet reads the direction backwards ('assigning a parent to a child in a session -> "
             "parent not added'); the forward many-to-one cascade does add it. Not the central claim")
    _, User, Address, engine = models()
    with Session(engine) as s:
        u1 = User(name="u1")
        s.add(u1)
        s.commit()
        a1 = Address(email="a")
        a1.user = u1
        not_added = a1 not in s

    class Base(DeclarativeBase):
        pass

    class P(Base):
        __tablename__ = "p"
        id = mapped_column(sa.Integer, primary_key=True)
        kids = relationship("K", back_populates="parent", cascade_backrefs=False)

    class K(Base):
        __tablename__ = "k"
        id = mapped_column(sa.Integer, primary_key=True)
        p_id = mapped_column(sa.ForeignKey("p.id"))
        parent = relationship("P", back_populates="kids")

    orm.configure_mappers()
    return CLAIM, not_added


def g099():
    CLAIM = ("under MappedAsDataclass: default= must be a constant (a callable is rejected); default_factory= "
             "supplies callables; default= and insert_default= are mutually exclusive")

    def define(**kw):
        class Base(orm.MappedAsDataclass, DeclarativeBase):
            pass

        class D(Base):
            __tablename__ = "d"
            id: Mapped[int] = mapped_column(primary_key=True, init=False)
            v: Mapped[int] = mapped_column(**kw)
        return D

    callable_rejected = raises(lambda: define(default=lambda: 1), exc.ArgumentError, TypeError, ValueError)
    factory_works = define(default_factory=lambda: 5)().v == 5
    exclusive = raises(lambda: define(default=1, insert_default=2), exc.ArgumentError, TypeError, ValueError)
    return CLAIM, callable_rejected and factory_works and exclusive


def g100():
    CLAIM = "AsyncSession.run_sync can run synchronous bulk_save_objects inside async code"
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    # CORRECTED AFTER THE FIRST RUN: the first version discarded the Address
    # class (`Base, User, _, _ = models()`). Alone it passed; in the full run it crashed with
    # "expression 'Address' failed to locate a name" -- the unreferenced class can be garbage-
    # collected before User's relationship("Address") is configured. Keeping the reference is the fix.
    Base, User, Address, _ = models()

    async def main():
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine) as s:
            await s.run_sync(lambda sync: sync.bulk_save_objects([User(name="a"), User(name="b")]))
            await s.commit()
            n = (await s.execute(sa.select(sa.func.count()).select_from(User))).scalar()
        await engine.dispose()
        return n == 2
    return CLAIM, asyncio.run(main())


def g106():
    CLAIM = ("joinedload on a relationship to a polymorphic base does not load subclass-table columns; "
             "joinedload(Owner.pets.of_type(with_polymorphic(Pet, [Dog], flat=True))) does")
    class Base(DeclarativeBase):
        pass

    class Owner(Base):
        __tablename__ = "owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        pets: Mapped[list["Pet"]] = relationship()

    class Pet(Base):
        __tablename__ = "pet"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(sa.ForeignKey("owner.id"))
        kind: Mapped[str]
        __mapper_args__ = {"polymorphic_on": "kind", "polymorphic_identity": "pet"}

    class Dog(Pet):
        __tablename__ = "dog"
        id: Mapped[int] = mapped_column(sa.ForeignKey("pet.id"), primary_key=True)
        bark: Mapped[str] = mapped_column(default="woof")
        __mapper_args__ = {"polymorphic_identity": "dog"}

    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Owner(id=1, pets=[Dog()]))
        s.commit()
    with Session(engine) as s:
        o = s.execute(sa.select(Owner).options(orm.joinedload(Owner.pets))).unique().scalars().one()
        plain = "bark" in sa.inspect(o.pets[0]).unloaded
    with Session(engine) as s:
        wp = orm.with_polymorphic(Pet, [Dog], flat=True)
        o = s.execute(sa.select(Owner).options(orm.joinedload(Owner.pets.of_type(wp)))).unique().scalars().one()
        loaded = "bark" not in sa.inspect(o.pets[0]).unloaded
    return CLAIM, plain and loaded


def g109():
    CLAIM = "yield_per together with unique() raises when ORM rows are fetched"
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(name="u", addresses=[Address(email="a")]))
        s.commit()
        stmt = sa.select(User).execution_options(yield_per=10)
        return CLAIM, raises(lambda: s.execute(stmt).unique().scalars().all(), exc.InvalidRequestError)


def g110():
    CLAIM = ("in 2.0 create_engine's future= must be True if given (False is rejected); the Connection has "
             "commit()/rollback(); strings need text(); the Engine has no execute()")
    engine = sa.create_engine("sqlite://", future=True)
    with engine.connect() as c:
        conn_api = hasattr(c, "commit") and hasattr(c, "rollback")
        strings = raises(lambda: c.execute("select 1"), exc.ObjectNotExecutableError)
    return CLAIM, (raises(lambda: sa.create_engine("sqlite://", future=False), exc.ArgumentError)
                   and conn_api and strings and not hasattr(engine, "execute"))


def g111():
    CLAIM = ("with engine.connect() does not commit by itself (work is rolled back at close); "
             "engine.begin(), conn.begin() and conn.commit() all commit")
    engine = sa.create_engine("sqlite:///file:g111?mode=memory&cache=shared&uri=true")
    t = table()
    t.metadata.create_all(engine)

    def count():
        with engine.connect() as c:
            return c.execute(sa.select(sa.func.count()).select_from(t)).scalar()

    with engine.connect() as c:
        c.execute(t.insert().values(x=1))
    not_committed = count() == 0
    with engine.begin() as c:
        c.execute(t.insert().values(x=2))
    with engine.connect() as c:
        with c.begin():
            c.execute(t.insert().values(x=3))
    with engine.connect() as c:
        c.execute(t.insert().values(x=4))
        c.commit()
    return CLAIM, not_committed and count() == 3


def g115():
    CLAIM = ("2.0 connections: a plain string is rejected and text() works; engine.begin() commits; "
             "engine.connect() needs an explicit commit(); parameters go as a dict, not **kwargs")
    engine = sa.create_engine("sqlite:///file:g115?mode=memory&cache=shared&uri=true")
    with engine.begin() as c:
        c.execute(text("create table t (x integer)"))
        c.execute(text("insert into t values (1)"))
    with engine.connect() as c:
        c.execute(text("insert into t values (:x)"), {"x": 2})
    with engine.connect() as c:
        c.execute(text("insert into t values (:x)"), {"x": 3})
        c.commit()
    with engine.connect() as c:
        values = sorted(c.execute(text("select x from t")).scalars().all())
        strings = raises(lambda: c.execute("select 1"), exc.ObjectNotExecutableError)
        kwargs = raises(lambda: c.execute(text("select :x"), x=1), TypeError)
    return CLAIM, values == [1, 3] and strings and kwargs


def g118():
    CLAIM = "two aliased(Address) with User.addresses.of_type(alias) join the same table twice under two aliases"
    _, User, Address, engine = models()
    a1, a2 = orm.aliased(Address), orm.aliased(Address)
    with Session(engine) as s:
        s.add(User(name="jack", addresses=[Address(email="jack@google.com"), Address(email="j25@yahoo.com")]))
        s.commit()
        q = (s.query(User.name, a1.email, a2.email)
             .join(User.addresses.of_type(a1)).join(User.addresses.of_type(a2))
             .filter(a1.email == "jack@google.com").filter(a2.email == "j25@yahoo.com"))
        sql = str(q)
        return CLAIM, "addresses_1" in sql and "addresses_2" in sql and q.all() == [("jack", "jack@google.com", "j25@yahoo.com")]


def g121():
    CLAIM = ("2.0 rows: execute(select(User)).scalars().all() gives objects; Row supports row[0], row.name and "
             "row._mapping['name']; result.mappings() keys ORM entities by class name. SECONDARY SLIP, not the "
             "verdict: it calls row['name'] 'deprecated'; on 2.0 it fails")
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(name="ed", addresses=[Address(email="e")]))
        s.commit()
        users = s.execute(sa.select(User).filter_by(name="ed")).scalars().all()
        row = s.execute(sa.select(User.name, User.id)).first()
        m = s.execute(sa.select(User, Address).join(User.addresses)).mappings().first()
        return CLAIM, (isinstance(users[0], User) and row[0] == "ed" and row.name == "ed"
                       and row._mapping["name"] == "ed" and isinstance(m["User"], User)
                       and isinstance(m["Address"], Address))


CHECKS = {name: fn for name, fn in globals().items() if name.startswith("g") and name[1:].isdigit()}


def delivered() -> list[str]:
    return json.loads((ROOT / "deliverables/nemotron-all-delivered.json").read_text())["ids"]


def main() -> None:
    if sa.__version__ != PIN:
        sys.exit(f"these checks are about {PIN}; this environment has {sa.__version__}")
    warnings.simplefilter("ignore")
    ids = delivered()
    print(f"NEMOTRON'S {len(ids)} DELIVERED ANSWERS, CENTRAL CLAIMS EXECUTED — sqlalchemy {sa.__version__}")
    print()
    tally = {"PASS": [], "FAIL": [], NOT_CHECKABLE: [], "ERROR": []}
    for i in ids:
        if i not in CHECKS:
            tally["ERROR"].append(i)
            print(f"  {i}  ERROR          no check written")
            continue
        try:
            claim, ok = CHECKS[i]()
            verdict = NOT_CHECKABLE if ok == NOT_CHECKABLE else ("PASS" if ok else "FAIL")
        except Exception as e:      # a bug in the check, not a verdict on the answer
            claim, verdict = f"{type(e).__name__}: {str(e)[:90]}", "ERROR"
        tally[verdict].append(i)
        print(f"  {i}  {verdict:<14} {claim}")
    extra = sorted(set(CHECKS) - set(ids))
    checkable = len(tally["PASS"]) + len(tally["FAIL"])
    rate = len(tally["PASS"]) / checkable if checkable else 0
    print(f"\n  PASS {len(tally['PASS'])}  FAIL {len(tally['FAIL'])}  NOT_CHECKABLE {len(tally[NOT_CHECKABLE])}  "
          f"ERROR {len(tally['ERROR'])}   pass rate {rate:.0%} of checkable")
    for k in ("FAIL", "ERROR", NOT_CHECKABLE):
        if tally[k]:
            print(f"  {k:<14} {' '.join(tally[k])}")
    if extra:
        print(f"  checks for ids not in the delivered list: {' '.join(extra)}")
    if tally["ERROR"]:
        print("\nrule: no verdict while any check is ERROR (a bug in a check is not a verdict on an answer)")
    elif checkable:
        print(f"\nrule (>= {BAR:.0%} of checkable pass): {rate:.0%} -> "
              + ("the 0.58 stands as 'delivered and, where checkable, correct'" if rate >= BAR
                 else "the 0.58 is overstated; quote the executed-correct count beside it"))


if __name__ == "__main__":
    main()
