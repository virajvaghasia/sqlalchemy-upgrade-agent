"""Phase 6, Step 3e — are the escalated answers CORRECT? Each one's central claim, executed.

    uv run --no-project --with 'sqlalchemy==2.0.51' --with aiosqlite --with greenlet python tools/check_escalated.py

WHY THIS EXISTS

An earlier step measured escalated answers against the human-verified page, which is a
judge model's opinion. Correctness was *executed* for two answers only (`g016`,
`g007`), and one of those showed the judge calling a wrong answer SUPPORTED.
This file runs every escalated answer's central claim on the real library.

HOW EACH CHECK WAS WRITTEN (Phase 6 Step 3e, rules written first)

- Claude read each answer and wrote down its central checkable claim, as the
  `CLAIM` string beside each check, before this file was ever run. The file was
  committed before its first run, so the history shows the checks predate the
  results.
- **A check tests the old behaviour the answer says is gone AND the new
  behaviour it recommends.** A check that only asserted "this raises" could pass
  on a typo in the check itself.
- Exceptions are narrow (`TypeError`, `ArgumentError`, ...), for the same reason.
- `NOT_CHECKABLE` means the claim cannot be made executable here (typing, advice).
  It is never counted as correct.
- An unexpected crash inside a check is `ERROR`: a bug in the check, reported
  apart, never silently counted as the answer being wrong.
- **Claude wrote these checks. This is not a human verdict.** Every claim
  is in the file, so anyone can read exactly what was tested and dispute it.

Reads only JSON from `deliverables/`, so it runs in a bare environment with
nothing but the pinned SQLAlchemy, like `verify_2_0.py`.
"""

import asyncio
import json
import pathlib
import subprocess
import sys
import warnings

import sqlalchemy as sa
from sqlalchemy import exc, orm, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

ROOT = pathlib.Path(__file__).resolve().parent.parent
PIN = "2.0.51"
NOT_CHECKABLE = "NOT_CHECKABLE"
BAR = 0.80   # Phase 6 Step 3e: >= 80% of checkable 3b answers pass


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
    md = sa.MetaData()
    return sa.Table("t", md, sa.Column("x", sa.Integer), sa.Column("y", sa.Integer))


# --- 3b: the page-present escalations ----------------------------------------

def g006():
    CLAIM = "Connection.execute() rejects a plain SQL string; text() and exec_driver_sql() work"
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        old = raises(lambda: c.execute("select 1"), exc.ObjectNotExecutableError)
        new = c.execute(text("select 1")).scalar() == 1 and c.exec_driver_sql("select 1").scalar() == 1
    return CLAIM, old and new


def g008():
    CLAIM = "select([cols]) is rejected in 2.0; select(col, col) positionally works"
    _, User, _, _ = models()
    old = raises(lambda: sa.select([User.id, User.name]), exc.ArgumentError, TypeError)
    new = "users.id" in str(sa.select(User.id, User.name))
    return CLAIM, old and new


def g013():
    CLAIM = "a string attribute name in subqueryload is rejected; subqueryload(User.addresses) works"
    _, User, _, _ = models()
    old = raises(lambda: sa.select(User).options(orm.subqueryload("addresses")), exc.ArgumentError)
    new = bool(str(sa.select(User).options(orm.subqueryload(User.addresses))))
    return CLAIM, old and new


def g021():
    CLAIM = "relationship(backref=...) is legacy but still works in 2.0; back_populates works"
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


def g029():
    CLAIM = ("insert(t, values=...) and t.delete(whereclause) are rejected; "
             "insert(t).values().inline(), delete().where(), update().ordered_values() work")
    t = table()
    old = (raises(lambda: sa.insert(t, values={"x": 10}), TypeError, exc.ArgumentError)
           and raises(lambda: t.delete(t.c.x > 15), TypeError, exc.ArgumentError))
    new = all(str(s) for s in (
        sa.insert(t).values(x=10, y=15).inline(),
        t.delete().where(t.c.x > 15),
        t.update().where(t.c.x < 15).ordered_values((t.c.y, 20), (t.c.x, t.c.y + 10)),
    ))
    return CLAIM, old and new


def g044():
    CLAIM = "Table(autoload=True) without an engine is gone; Table(..., autoload_with=engine) reflects"
    engine = sa.create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table t (a integer, b text)")
    old = raises(lambda: sa.Table("t", sa.MetaData(), autoload=True), TypeError, exc.ArgumentError)
    new = [col.name for col in sa.Table("t", sa.MetaData(), autoload_with=engine).columns] == ["a", "b"]
    return CLAIM, old and new


def g048():
    CLAIM = "joinedload('addresses') with a string is removed; joinedload(User.addresses) works"
    _, User, _, _ = models()
    old = raises(lambda: sa.select(User).options(orm.joinedload("addresses")), exc.ArgumentError)
    new = bool(str(sa.select(User).options(orm.joinedload(User.addresses))))
    return CLAIM, old and new


def g049():
    CLAIM = "case([ (cond, val) ]) with a list is rejected in 2.0; case((cond, val), ...) positionally works"
    t = table()
    old = raises(lambda: sa.case([(t.c.x == 5, "five")], else_="n"), exc.ArgumentError, TypeError)
    new = "CASE" in str(sa.case((t.c.x == 5, "five"), (t.c.x == 7, "seven"), else_="n"))
    return CLAIM, old and new


def g050():
    CLAIM = "Engine has no execute(); with engine.connect() as conn: conn.execute(stmt) works"
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        new = c.execute(sa.select(sa.literal(1))).scalar() == 1
    return CLAIM, (not hasattr(engine, "execute")) and new


def g051():
    CLAIM = ("execute(select(User)).scalars().all() gives User objects; .all() gives Row tuples; "
             "session.scalars(...).first() gives a User")
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add_all([User(name="a"), User(name="b")])
        s.commit()
        scal = s.execute(sa.select(User)).scalars().all()
        rows = s.execute(sa.select(User)).all()
        first = s.scalars(sa.select(User)).first()
        return CLAIM, (all(isinstance(u, User) for u in scal) and len(scal) == 2
                       and all(isinstance(r, sa.Row) and len(r) == 1 for r in rows)
                       and isinstance(first, User))


def g087():
    CLAIM = ("a server_default column is NOT in __dict__ right after flush by default (expired); "
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
        return CLAIM, ("created" not in w.__dict__) and ("created" in w2.__dict__)


def g090():
    return ("the answer's point is that the sources do not cover load_only's typing: "
            "a typing question is not executable here"), NOT_CHECKABLE


def g095():
    CLAIM = "populate_existing=True refreshes loaded objects, erasing pending unflushed changes"
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add(User(id=1, name="a"))
        s.commit()
        u = s.get(User, 1)
        u.name = "changed"
        s.execute(sa.select(User).execution_options(populate_existing=True, autoflush=False)).scalars().all()
        return CLAIM, u.name == "a"


def g099():
    CLAIM = ("under MappedAsDataclass: default= must be a constant (a callable is not allowed); "
             "default_factory= supplies callables; default= and insert_default= are mutually exclusive")

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
    CLAIM = "AsyncSession.run_sync lets synchronous bulk_save_objects run inside async code"
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    Base, User, _, _ = models()

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
    CLAIM = ("joinedload on a relationship to a polymorphic base does not load subclass-table "
             "columns unless with_polymorphic is used")
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
        d = o.pets[0]
        return CLAIM, isinstance(d, Dog) and "bark" in sa.inspect(d).unloaded


# --- 3c: the page-absent escalations ------------------------------------------

def g007():
    CLAIM = "MetaData(bind=engine) raises TypeError in 2.0; MetaData() then create_all(engine) works"
    engine = sa.create_engine("sqlite://")
    old = raises(lambda: sa.MetaData(bind=engine), TypeError)
    md = sa.MetaData()
    sa.Table("t", md, sa.Column("x", sa.Integer))
    md.create_all(engine)
    return CLAIM, old and sa.inspect(engine).has_table("t")


def g011():
    CLAIM = ("Query.join(..., aliased=True) is gone; join(User.addresses.of_type(a1)) and "
             "join(a1, User.addresses) work")
    _, User, Address, engine = models()
    a1 = orm.aliased(Address)
    with Session(engine) as s:
        old = raises(lambda: s.query(User).join(User.addresses, aliased=True), TypeError)
    new = (bool(str(sa.select(User).join(User.addresses.of_type(a1)).where(a1.email == "x")))
           and bool(str(sa.select(User).join(a1, User.addresses))))
    return CLAIM, old and new


def g016():
    CLAIM = "row.keys() exists on Row in SQLAlchemy 2.0"
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        row = c.execute(text("select 1 as x")).first()
    return CLAIM, hasattr(row, "keys")


def g020():
    CLAIM = ("the cascade_backrefs behaviour is gone: assigning address.user = user (user in the "
             "session) does not add the address, so it is not INSERTed unless added explicitly")
    _, User, Address, engine = models()
    with Session(engine) as s:
        u = User(name="u")
        s.add(u)
        a = Address(email="e")
        a.user = u
        not_enrolled = a not in s
        s.commit()
    with Session(engine) as s:
        n = s.scalar(sa.select(sa.func.count()).select_from(Address))
    return CLAIM, not_enrolled and n == 0


def g022():
    CLAIM = "Engine.scalar() no longer exists in 2.0"
    return CLAIM, not hasattr(sa.create_engine("sqlite://"), "scalar")


def g028():
    CLAIM = ("driver-level autocommit works via execution_options(isolation_level='AUTOCOMMIT'), "
             "and Connection.execution_options() modifies the connection in place, returning it")
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        same = c.execution_options(isolation_level="AUTOCOMMIT") is c
        # CORRECTED AFTER THE FIRST RUN, and disclosed in Phase 6 Step 3e: the
        # first version compared c.get_isolation_level() to "AUTOCOMMIT". On
        # SQLite that method reports the database's level ("SERIALIZABLE") even
        # in autocommit mode, so the check failed a correct answer. The driver
        # is the ground truth: sqlite3 is in autocommit when isolation_level is
        # None (it is '' before the option is set).
        autocommit = c.connection.dbapi_connection.isolation_level is None
    return CLAIM, same and autocommit


def g036():
    CLAIM = "MetaData(bind=...) raises TypeError in 2.0; sessionmaker(engine) is where the engine goes"
    engine = sa.create_engine("sqlite://")
    old = raises(lambda: sa.MetaData(bind=engine), TypeError)
    with orm.sessionmaker(engine)() as s:
        new = s.execute(text("select 1")).scalar() == 1
    return CLAIM, old and new


def g037():
    CLAIM = "a plain string passed to conn.execute fails; wrapping it in text() works"
    engine = sa.create_engine("sqlite://")
    with engine.connect() as c:
        old = raises(lambda: c.execute("select 1"), exc.ObjectNotExecutableError)
        new = c.execute(text("select 1")).scalar() == 1
    return CLAIM, old and new


def g039():
    CLAIM = "session.execute(select(User)).all() returns Row tuples; .scalars().all() returns User objects"
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add(User(name="a"))
        s.commit()
        rows = s.execute(sa.select(User)).all()
        users = s.execute(sa.select(User)).scalars().all()
        return CLAIM, (isinstance(rows[0], sa.Row) and isinstance(rows[0][0], User)
                       and isinstance(users[0], User))


def g040():
    CLAIM = "legacy Query de-duplicates parents automatically when joinedload-ing a collection"
    _, User, Address, engine = models()
    with Session(engine) as s:
        s.add(User(name="u", addresses=[Address(email="a"), Address(email="b")]))
        s.commit()
    with Session(engine) as s:
        users = s.query(User).options(orm.joinedload(User.addresses)).all()
        return CLAIM, len(users) == 1 and len(users[0].addresses) == 2


def g058():
    CLAIM = ("on 1.4 with 2.0 warnings on, conn.execute('insert ...') on engine.connect() emits "
             "RemovedIn20Warning for implicit autocommit and for passing a string")
    code = (
        "import warnings, sqlalchemy as sa\n"
        "e = sa.create_engine('sqlite://')\n"
        "c = e.connect()\n"
        "c.exec_driver_sql('create table t (x integer)')\n"
        "with warnings.catch_warnings(record=True) as w:\n"
        "    warnings.simplefilter('always')\n"
        "    c.execute('insert into t values (1)')\n"
        "m = ' | '.join(str(x.message) for x in w if x.category.__name__ == 'RemovedIn20Warning')\n"
        "print(('autocommit' in m) and ('string' in m.lower()))\n"
    )
    out = subprocess.run(
        ["uv", "run", "--no-project", "--with", "sqlalchemy==1.4.52", "python", "-c", code],
        capture_output=True, text=True, env={**__import__("os").environ, "SQLALCHEMY_WARN_20": "1"},
    )
    return CLAIM, out.stdout.strip() == "True"


def g085():
    CLAIM = "calling session.begin() while a transaction is already in progress raises in 2.0"
    engine = sa.create_engine("sqlite://")
    with Session(engine) as s:
        s.execute(text("select 1"))       # autobegin
        return CLAIM, raises(s.begin, exc.InvalidRequestError)


def g094():
    CLAIM = "objects added without an explicit begin() are not discarded: commit() persists them"
    _, User, _, engine = models()
    with Session(engine) as s:
        s.add(User(name="z"))
        s.commit()
    with Session(engine) as s:
        return CLAIM, s.scalar(sa.select(sa.func.count()).select_from(User)) == 1


CHECKS = {name: fn for name, fn in globals().items() if name.startswith("g") and name[1:].isdigit()}


def escalated() -> dict[str, list[str]]:
    """The answered escalations, derived from the saved rows -- never typed."""
    golden = {i["id"]: i for i in json.loads((ROOT / "deliverables/golden.json").read_text())["items"]}
    out = {}
    for label, path in (("3b page present", "escalate-phase6.json"), ("3c page absent", "escalate-rest-phase6.json")):
        rows = json.loads((ROOT / "deliverables" / path).read_text())["rows"]
        out[label] = sorted(r["id"] for r in rows
                            if not r["refused"] and not r.get("empty") and golden[r["id"]].get("answerable"))
    return out


def main() -> None:
    if sa.__version__ != PIN:
        sys.exit(f"these checks are about {PIN}; this environment has {sa.__version__}")
    warnings.simplefilter("ignore")
    print(f"ESCALATED ANSWERS, CENTRAL CLAIMS EXECUTED — sqlalchemy {sa.__version__}")
    summary = {}
    for label, ids in escalated().items():
        print(f"\n{label}")
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
                claim, verdict = f"{type(e).__name__}: {str(e)[:70]}", "ERROR"
            tally[verdict].append(i)
            print(f"  {i}  {verdict:<14} {claim}")
        summary[label] = tally
        checkable = len(tally["PASS"]) + len(tally["FAIL"])
        rate = len(tally["PASS"]) / checkable if checkable else 0
        print(f"  -> PASS {len(tally['PASS'])}  FAIL {len(tally['FAIL'])}  NOT_CHECKABLE "
              f"{len(tally[NOT_CHECKABLE])}  ERROR {len(tally['ERROR'])}   pass rate {rate:.0%} of checkable")
    b = summary["3b page present"]
    checkable = len(b["PASS"]) + len(b["FAIL"])
    if checkable:
        rate = len(b["PASS"]) / checkable
        print(f"\nrule (3b, >= {BAR:.0%} of checkable pass): {rate:.0%} -> "
              + ("the 0.53 upper bound stands as stated" if rate >= BAR
                 else "overstated; recompute the upper bound from executed passes"))


if __name__ == "__main__":
    main()
