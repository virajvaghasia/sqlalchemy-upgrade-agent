# Breakages — SQLAlchemy 1.4.52 → 2.0.51

The Phase 0 Part A deliverable, and the seed of the Phase 2 golden dataset. Part of
[`sqlalchemy-upgrade-agent`](README.md); the mechanics behind each entry are explained
in [`MIGRATION-2.0.md`](MIGRATION-2.0.md) §16–§22.

Measured on 2.0.51, against `models.py` in this repo. Each entry is 1.4 code
that ran clean on 1.4.52 and fails on 2.0.

**Status: DRAFT — verified to run, not verified to be right.**

| field | where it comes from |
|---|---|
| 1.4 code | `patterns.py` |
| 2.0 error | this run, on 2.0.51 |
| Fix | `patterns.py` — **executed on 2.0 here**, so it provably runs |
| Tier | `candidates.py`, measured on 1.4, passed via `tiers.json` |

A draft fix runs. That is not the same as it being the *right* fix: several entries
have more than one defensible answer, and choosing is the part worth doing yourself.
Edit them into your own words as you work through the upgrade.

> **Do not regenerate over this file once you have edited it.** The generator
> prints fresh drafts; redirecting it onto `BREAKAGES.md` would erase every word
> you wrote over them. Diff instead:
>
> ```bash
> uv run --no-project --with 'sqlalchemy>=2.0' \
>     python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0 --stubs > /tmp/breakages.new
> diff /tmp/breakages.new BREAKAGES.md
> ```
>
> Re-run that after any change to `models.py` or `patterns.py`: if a measured
> error message moved, the diff shows it and you edit that entry by hand.

---

## Raw SQL / connectionless

### 1. engine.execute(string)

```python
# 1.4 — worked
engine.execute("SELECT 1")
```

**2.0 error** — `AttributeError`

```
'Engine' object has no attribute 'execute'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
```

Connectionless execution is gone. The connection — and therefore the transaction boundary — becomes visible in the source.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **NotImplementedError**  
_both tools agree_ (measured on 1.4 by `candidates.py`)

### 2. engine.scalar(string)

```python
# 1.4 — worked
engine.scalar("SELECT 1")
```

**2.0 error** — `AttributeError`

```
'Engine' object has no attribute 'scalar'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
with engine.connect() as conn:
    conn.scalar(text("SELECT 1"))
```

Same removal as engine.execute(); .scalar() still exists on Connection.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **NotImplementedError**  
_both tools agree_ (measured on 1.4 by `candidates.py`)

### 3. conn.execute(bare string)

```python
# 1.4 — worked
engine.connect().execute("SELECT 1")
```

**2.0 error** — `ObjectNotExecutableError`

```
Not an executable object: 'SELECT 1'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
conn.execute(text("SELECT 1"))
```

A bare string is no longer coerced. text() makes 'this is raw SQL, I mean it' explicit — and greppable during an audit.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ObjectNotExecutableError**  
_both tools agree_ (measured on 1.4 by `candidates.py`)

### 4. session.execute(bare string)

```python
# 1.4 — worked
session.execute("SELECT 1")
```

**2.0 error** — `ArgumentError`

```
Textual SQL expression 'SELECT 1' should be explicitly declared as text('SELECT 1')
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
session.execute(text("SELECT 1"))
```

Same rule on the Session as on the Connection.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Schema / reflection helpers

### 5. engine.table_names()

```python
# 1.4 — worked
engine.table_names()
```

**2.0 error** — `AttributeError`

```
'Engine' object has no attribute 'table_names'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
inspect(engine).get_table_names()
```

Reflection helpers moved off Engine and onto the Inspector, which is where the rest of them already lived.

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **NotImplementedError**  
_SILENT to the sweep_ (measured on 1.4 by `candidates.py`)

### 6. engine.has_table()

```python
# 1.4 — worked
engine.has_table("issues")
```

**2.0 error** — `AttributeError`

```
'Engine' object has no attribute 'has_table'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
inspect(engine).has_table("issues")
```

Same move to the Inspector.

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **NotImplementedError**  
_SILENT to the sweep_ (measured on 1.4 by `candidates.py`)

### 7. MetaData(bind=engine)

```python
# 1.4 — worked
MetaData(bind=engine)
```

**2.0 error** — `TypeError`

```
MetaData.__init__() got an unexpected keyword argument 'bind'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
MetaData()   # then pass the engine explicitly:
metadata.create_all(engine)
```

Implicit binding is gone everywhere. The engine is passed at the point of use, so you can read which database a statement goes to.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Statement construction

### 8. select([...]) list form

```python
# 1.4 — worked
select([Issue.id])
```

**2.0 error** — `ArgumentError`

```
Column expression, FROM clause, or other columns clause element expected, got
[<sqlalchemy.orm.attributes.InstrumentedAttribute object at 0x...>]. Did you mean to say
select(<sqlalchemy.orm.attributes.InstrumentedAttribute object at 0x...>)?
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
select(Issue.id)
```

Columns are positional now, not a list. 2.0's own error suggests this fix.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

### 9. case([...]) list form

```python
# 1.4 — worked
case([(Issue.id == 1, "a")], else_="b")
```

**2.0 error** — `ArgumentError`

```
The "whens" argument to case(), when referring to a sequence of items, is now passed as
a series of positional elements, rather than as a list.
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
case((Issue.id == 1, "a"), else_="b")
```

The whens became positional, matching select().

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

### 10. orm.relation() alias

```python
# 1.4 — worked
sqlalchemy.orm.relation(Comment)
```

**2.0 error** — `AttributeError`

```
module 'sqlalchemy.orm' has no attribute 'relation'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
sqlalchemy.orm.relationship(Comment)
```

relation() was an alias for relationship() kept since 0.x. Only the long name survives.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Query API

### 11. Query.filter(raw string)

```python
# 1.4 — worked
query(Issue).filter("status='open'")
```

**2.0 error** — `ArgumentError`

```
Textual SQL expression "status='open'" should be explicitly declared as
text("status='open'")
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
query(Issue).filter(Issue.status == "open")
# or, if it really must be SQL:  .filter(text("status='open'"))
```

The column expression is better than text() here: it is checked, and it composes. text() is the escape hatch, not the fix.

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **ArgumentError**  
_SILENT to the sweep_ (measured on 1.4 by `candidates.py`)

### 12. Query.from_self()

```python
# 1.4 — worked
query(Issue).from_self()
```

**2.0 error** — `AttributeError`

```
'Query' object has no attribute 'from_self'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
subq = select(Issue).subquery()
inner = aliased(Issue, subq)
session.execute(select(inner)).scalars().all()
```

from_self() was removed as too implicit. You now name the subquery and alias the entity onto it, which is what it was doing invisibly.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

### 13. Query.join(aliased=True)

```python
# 1.4 — worked
query(Issue).join(Comment, aliased=True)
```

**2.0 error** — `TypeError`

```
Query.join() got an unexpected keyword argument 'aliased'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
target = aliased(Comment)
query(Issue).join(target, Issue.comments)
```

The implicit aliasing flag is gone; you create the alias and join to it.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Loader options as strings

### 14. joinedload(string)

```python
# 1.4 — worked
query(Issue).options(joinedload("comments"))
```

**2.0 error** — `ArgumentError`

```
Strings are not accepted for attribute names in loader options; please use class-bound
attributes directly.
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
query(Issue).options(joinedload(Issue.comments))
```

Strings are not accepted for attribute names in loader options. The class-bound attribute is checked at construction instead of at query time.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

### 15. subqueryload(string)

```python
# 1.4 — worked
query(Issue).options(subqueryload("comments"))
```

**2.0 error** — `ArgumentError`

```
Strings are not accepted for attribute names in loader options; please use class-bound
attributes directly.
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
query(Issue).options(subqueryload(Issue.comments))
```

Same rule for every loader option.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Results and rows

### 16. Row attr access, no .scalars()

```python
# 1.4 — worked
session.execute(select(Issue)).all()[0].title
```

**2.0 error** — `AttributeError`

```
title
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
session.execute(select(Issue)).scalars().all()[0].title
```

execute() returns Rows; .scalars() projects to the first column. Only add it when you selected ONE thing — on a wider select it silently discards the rest.

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **AttributeError**  
_SILENT to the sweep_ (measured on 1.4 by `candidates.py`)

### 17. row['colname'] mapping access

```python
# 1.4 — worked
conn.execute(text("SELECT id FROM issues")).fetchone()["id"]
```

**2.0 error** — `TypeError`

```
tuple indices must be integers or slices, not str
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
row._mapping["id"]
```

Row is a named tuple in 2.0. The dict-like view moved to ._mapping, so the two access styles stopped overlapping.

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **ok**  
_not a breakage (works in 2.0)_ (measured on 1.4 by `candidates.py`)

### 18. row.keys()

```python
# 1.4 — worked
conn.execute(text("SELECT id FROM issues")).fetchone().keys()
```

**2.0 error** — `AttributeError`

```
Could not locate column in row for column 'keys'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
row._mapping.keys()
```

Same move. On 2.0 a bare .keys() is read as a COLUMN lookup, which is why the error says 'Could not locate column'.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

### 19. joinedload(coll), no .unique()

```python
# 1.4 — worked
execute(select(Issue).options(joinedload(Issue.comments))).all()
```

**2.0 error** — `InvalidRequestError`

```
The unique() method must be invoked on this Result, as it contains results that include
joined eager loads against collections
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
session.execute(stmt).unique().scalars().all()
```

Only for joined eager loads against a COLLECTION. On entities .unique() dedupes by primary key, so it can only remove copies the JOIN invented.

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **InvalidRequestError**  
_SILENT to the sweep_ (measured on 1.4 by `candidates.py`)

---

## Session lifecycle

### 20. Session(autocommit=True)

```python
# 1.4 — worked
sessionmaker(bind=engine, autocommit=True)()
```

**2.0 error** — `ArgumentError`

```
autocommit=True is no longer supported
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
Session(bind=engine)      # autobegin: the transaction opens on first use
...
session.commit()          # and you end it explicitly
```

Library-level autocommit is removed outright — there is no replacement flag. The transaction now begins on first use and ends where you say.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

### 21. session.begin(subtransactions)

```python
# 1.4 — worked
session.begin(subtransactions=True)
```

**2.0 error** — `TypeError`

```
Session.begin() got an unexpected keyword argument 'subtransactions'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
session.begin_nested()    # a real SAVEPOINT
```

Subtransactions were a bookkeeping fiction that emitted no SQL. begin_nested() issues an actual SAVEPOINT.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **NotImplementedError**  
_both tools agree_ (measured on 1.4 by `candidates.py`)

### 22. session.transaction attribute

```python
# 1.4 — worked
session.transaction
```

**2.0 error** — `AttributeError`

```
'Session' object has no attribute 'transaction'
```

**Fix** — _draft, verified to run on 2.0.51: `fix OK`_

```python
# 2.0
session.get_transaction()        # or session.in_transaction()
```

The attribute became a method, so 'is there a transaction?' is a question you ask rather than an object you poke at.

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## The one that raises nothing

### 23. cascade_backrefs — object attached by the many-to-one side

```python
# 1.4 — worked: the backref cascade enrolled `issue` with no session.add()
project = Project(name='apollo'); session.add(project)
issue = Issue(title='...'); issue.project = project
session.flush()
```

**2.0 error** — _none. That is the entry._

```
attached with project.issues.append(...)  -> in database: True
attached with issue.project = project     -> in database: False
```

Measured by counting rows, not by catching an exception — no exception exists.
A passing test suite does not see this unless it asserts on row counts.

**Fix** — _draft. Say what you meant:_

```python
# 2.0
issue = Issue(title='...')
issue.project = project
session.add(issue)          # <- the line 1.4 let you leave out
```

Writing the COLLECTION side (`project.issues.append(issue)`) also works and needs no
`session.add()` — the save-update cascade proper survives 2.0. `cascade_backrefs=False`
on the relationship adopts the 2.0 behaviour while still on 1.4, which is how you find
every site before upgrading.

**Tier:** `RemovedIn20Warning` — but only in modules that WRITE data; `app.py`'s sweep
misses it entirely. See `MIGRATION-2.0.md` §17 and `sweep.py`.
