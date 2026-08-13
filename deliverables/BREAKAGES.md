# Breakages — SQLAlchemy 1.4.52 → 2.0.51

The Phase 0 Part A deliverable, and the seed of the Phase 2 golden dataset. Part of
[`sqlalchemy-upgrade-agent`](../README.md); the mechanics behind each entry are explained
in [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16–§22.

Measured on 2.0.51, against `models.py` in this repo. Each entry is 1.4 code
that ran clean on 1.4.52 and fails on 2.0.

**Status: DRAFT — verified to run, not verified to be right.**

| field | where it comes from |
|---|---|
| 1.4 code | `patterns.py` |
| 2.0 error | this run, on 2.0.51 |
| Fix | `patterns.py` — **executed on 2.0 here**, so it provably runs |
| Docs | in-repo section refs, **checked against the files at generation time**, plus 1.4's own deprecation text |
| Tier | `candidates.py`, measured on 1.4, passed via `tiers.json` |

A draft fix runs. That is not the same as it being the *right* fix. 6 entries carry
an **Also defensible** block listing the other answers that work — because presenting
one option where several exist hides the decision instead of making it. Every option
shown is executed here too, so the choice is between things that all provably run.
Choosing is the judgement `phases/PHASE-0.md` asks for; edit them into your own words.

> **Do not regenerate over this file once you have edited it.** The generator
> prints fresh drafts; redirecting it onto `deliverables/BREAKAGES.md` would erase every word
> you wrote over them. Diff instead:
>
> ```bash
> uv run --no-project --with 'sqlalchemy==2.0.51' \
>     python -m experiments.sqlalchemy_1_4_vs_2_0.verify_2_0 --stubs > /tmp/breakages.new
> diff /tmp/breakages.new deliverables/BREAKAGES.md
> ```
>
> Re-run that after any change to `models.py` or `patterns.py`: if a measured
> error message moved, the diff shows it and you edit that entry by hand.

---

## How to read an entry

Eight groups (A–H). One idea per group. Each entry: measured **1.4 code**, the **2.0 error**
(or silence), a **fix that runs on 2.0.51**, then **What 1.4 did / What 2.0 does / Fix** so
this file is still readable when you come back cold.

**Tier** was measured on 1.4 by `candidates.py`, before any upgrade:

| What the tier line says | Meaning |
|---|---|
| _both tools agree_ | `SQLALCHEMY_WARN_20` warns **and** `future=True` already fails. Easy to find. |
| _sweep only – flag misses it_ | A warning exists; `future=True` still runs. A green future session is not "ready to upgrade." |
| _SILENT to the sweep_ | No warning. Only `future=True` or real 2.0 blows up. |
| _not a breakage (works in 2.0)_ | The 1.4 tools called it safe. Check the **2.0 error** anyway — #17 is the counter-example: tools said safe, 2.0.51 still failed. |

`SQLALCHEMY_WARN_20=1` answers "does 1.4 warn?" `future=True` answers "does 1.4 already fail
under 2.0 rules?" Neither replaces running real 2.0.

---

## Group A — Raw SQL (#1–4)

**One idea:** 2.0 stops treating Engine / Session as "just run this string." You must show
*who* executes (a Connection or Session) and *what* the string is (`text(...)`).

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

**What 1.4 did:** Engine secretly opened a connection, ran the string, closed it. You never
saw the connection or the transaction.

```
you → engine.execute("SELECT 1") → (hidden conn) → DB
```

**What 2.0 does:** Engine has no `.execute`. Crash: `AttributeError`.

**Fix flow:**

```
you → engine.connect() → conn → conn.execute(text("SELECT 1")) → DB
         ↑
    you now SEE the connection (and can commit/close it)
```

`text()` = "this string is SQL, not a Python object." Connectionless execution is gone;
the transaction boundary becomes visible.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §19
- what 1.4 itself says, verbatim:
  > The Engine.execute() method is considered legacy as of the 1.x series of SQLAlchemy
  > and will be removed in 2.0. All statement execution in SQLAlchemy 2.0 is performed
  > by the Connection.execute() method of Connection, or in the ORM by the
  > Session.execute() method of Session. (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

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

**Same as #1, different return.** `.execute` → a result set. `.scalar` → **one value**
(first column of first row, e.g. `SELECT 1` → `1`).

2.0: Engine lost `.scalar` too. Connection still has it — don't look for a new Engine
method; move to Connection:

```python
with engine.connect() as conn:
    n = conn.scalar(text("SELECT COUNT(*) FROM issues"))
```


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- what 1.4 itself says, verbatim:
  > The Engine.scalar() method is considered legacy as of the 1.x series of SQLAlchemy
  > and will be removed in 2.0. All statement execution in SQLAlchemy 2.0 is performed
  > by the Connection.execute() method of Connection, or in the ORM by the
  > Session.execute() method of Session; the Result.scalar() method can then be used to
  > return a scalar result. (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

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

**Different error, same theme.** You *have* a connection. 1.4 still accepted `"SELECT 1"`.
2.0: a string is not executable.

```
conn.execute("SELECT 1")       → ObjectNotExecutableError
conn.execute(text("SELECT 1")) → OK
```

**Why `text()`:** audits can grep `text(` and find every raw SQL site. Silent string
coercion in 1.4 hid them.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §19
- what 1.4 itself says, verbatim:
  > Passing a string to Connection.execute() is deprecated and will be removed in
  > version 2.0. Use the text() construct, or the Connection.exec_driver_sql() method to
  > invoke a driver-level SQL string. (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

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

**Same rule on Session.**

```python
session.execute("SELECT 1")           # 2.0 ArgumentError
session.execute(text("SELECT 1"))     # OK
```

The error text even tells you the fix. **Tier note:** `future=True` on 1.4 still says
**ok** — the warning sweep sees it, the future engine does not. Don't use only
`future=True` as your gate.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- what 1.4 itself says, verbatim:
  > Using plain strings to indicate SQL statements without using the text() construct is
  > deprecated and will be removed in version 2.0. Ensure plain SQL statements are
  > passed using the text() construct. (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Group B — Schema helpers (#5–7)

**One idea:** "What's in the database?" is **inspection**, not "Engine convenience."
MetaData no longer secretly owns an engine.

**Inspection** = asking the DB about its catalog: what tables exist, does `issues` exist,
what columns, FKs. Engine's real job is **how to connect** (URL, pooling) — not "list my
tables." 1.4 hung those helpers on Engine anyway (`table_names()`, `has_table()`). 2.0
moves them to **Inspector**: `inspect(engine)` = "give me the catalog-asker for this
engine."

**MetaData** = Python's picture of your tables (`users`, `issues`, …), used for
`create_all` / reflection. 1.4 let you `MetaData(bind=engine)` so MetaData remembered the
engine and later `create_all()` used that hidden bind. 2.0: no `bind=`; pass the engine at
the call site. Same smell as #1 — stop hiding the engine inside another object.

```
Engine     → how to talk to the DB (connect, pool)
Inspector  → "what tables/columns exist?"     ← #5 #6 moved here
MetaData   → your table definitions in Python ← #7 no longer stores Engine
```

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

**What 1.4 did:** Engine pretended to know the catalog — a convenience copy of Inspector.

**What 2.0 does:** catalog questions go through Inspector only. Engine copies were deleted.

```python
from sqlalchemy import inspect
inspect(engine).get_table_names()   # ["users", "issues", ...]
```

Those are **not two errors for the same run**. Same call, three environments:

| Where you run it | What happens |
|---|---|
| 1.4, no flags | works (and **no warning** — that's "SILENT to the sweep") |
| 1.4 + `future=True` | `NotImplementedError` — method still exists, refuses to run |
| real 2.0.51 | `AttributeError` — method is gone (the **2.0 error** box above) |

The **Tier** line below is measured on **1.4 only** (`candidates.py`). The **2.0 error** box
is measured on **real 2.0**. Easy to miss if you only run `SQLALCHEMY_WARN_20`.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16

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

**Identical move to #5** ("does this table exist?" instead of "list all tables").
Same split: 1.4 silent → `future=True` `NotImplementedError` → real 2.0 `AttributeError`.
WARN_20 alone will not find this.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16

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

**What 1.4 did:** MetaData remembered the engine. Later `create_all()` used that hidden bind.

```
MetaData(bind=engine) → metadata secretly knows the DB
create_all()          → uses the secret engine
```

**What 2.0 does:** `bind=` is not a valid argument (`TypeError`).

```python
metadata = MetaData()           # no engine
metadata.create_all(engine)     # engine at the call site
```

**Why:** you can read which DB a call hits. Implicit bind was the same "hidden connection"
smell as #1: MetaData no longer secretly owns an engine.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §18
- what 1.4 itself says, verbatim:
  > The MetaData.bind argument is deprecated and will be removed in SQLAlchemy 2.0.
  > (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Group C — Statement construction (#8–10)

**One idea:** old "pass a list" / short aliases die. Arguments are positional; names are
the long ones. You are not changing what SQL you *mean* — only how you *write* the Python
that builds the statement.

- `#8` `select([col])` → `select(col)`
- `#9` `case([(cond, val)], ...)` → `case((cond, val), ...)`  (same list → args change)
- `#10` `relation()` → `relationship()`  (old nickname deleted)

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

**What 1.4 did:** one list. **What 2.0 does:** the column itself as an argument. 2.0's error
literally says "Did you mean `select(<that column>)`?"

```python
select([Issue.id])                 # 1.4: one list
select(Issue.id)                   # 2.0: the column itself
select(Issue.id, Issue.title)      # more columns = more arguments, not a bigger list
```


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- what 1.4 itself says, verbatim:
  > The legacy calling style of select() is deprecated and will be removed in SQLAlchemy
  > 2.0. Please use the new calling style described at select(). (Background on
  > SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)

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

**Same list → positional change as #8.** SQL `CASE WHEN issue.id = 1 THEN 'a' ELSE 'b' END`.
Drop the outer list; each `(condition, result)` is an argument:

```python
case([(Issue.id == 1, "a")], else_="b")     # 1.4
case((Issue.id == 1, "a"), else_="b")       # 2.0
case(
    (Issue.status == "open", "OPEN"),
    (Issue.status == "closed", "DONE"),
    else_="OTHER",
)
```


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- what 1.4 itself says, verbatim:
  > The "whens" argument to case(), when referring to a sequence of items, is now passed
  > as a series of positional elements, rather than as a list. (Background on SQLAlchemy
  > 2.0 at: https://sqlalche.me/e/b8d9)

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

`relation` was a 0.x nickname. Deleted. This repo's `models.py` already uses
`relationship` — this breakage is for old tutorials / codebases that still import
`relation`.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §6
- what 1.4 itself says, verbatim:
  > The relation construct is considered legacy as of the 1.x series of SQLAlchemy and
  > will be removed in 2.0. Please use relationship(). (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Group D — Query leftovers (#11–13)

`Query` still exists in 2.0, but string filters and magic kwargs are gone.

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

**What 1.4 did:** string dumped into WHERE. **What 2.0 prefers:** a Python expression
(typo-checked). Escape hatch: still raw SQL, but marked with `text()`.

```python
query(Issue).filter(Issue.status == "open")           # preferred — typo-checked
query(Issue).filter(text("status='open'"))            # still raw SQL, but marked
```

**Also defensible is real:** if the WHERE is assembled elsewhere or uses dialect SQL,
`text()` is correct. If you just mean "status is open," use the column. That is the
judgement this entry wants you to pick.

**Tier:** SILENT to WARN_20; `future=True` already `ArgumentError`.


**Also defensible** — _each verified to run on 2.0.51. Pick deliberately; this is the judgement, not the typing._

```python
query(Issue).filter(text("status='open'"))
```

when the SQL genuinely has to stay SQL — a dialect feature, or a WHERE clause assembled elsewhere. You keep raw SQL, and text() makes it greppable. You lose the checking the column expression gives you.  
_(runs OK)_

**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16

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

**What it meant:** "Take this query, wrap it as a subquery, query *that*." Used for
DISTINCT-then-LIMIT, window-ish patterns, etc.

```
1.4:  query(Issue).filter(...).from_self()
         → SELECT * FROM (SELECT issues ... WHERE ...) AS anon

2.0:  you write that wrapping yourself
         subq  = select(Issue).subquery()      # the inner SELECT
         inner = aliased(Issue, subq)          # "treat subquery rows as Issue"
         session.execute(select(inner)).scalars().all()
```

`aliased(Issue, subq)` = "these subquery rows should still look like Issue objects."
`from_self()` did that invisibly; 2.0 makes you name it.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- what 1.4 itself says, verbatim:
  > The Query.from_self() method is considered legacy as of the 1.x series of SQLAlchemy
  > and will be removed in 2.0. The new approach is to use the orm.aliased() construct
  > in conjunction with a subquery. See the section "Selecting from the query itself as
  > a subquery" in the 2.0 migration notes for an example. (Background on SQLAlchemy 2.0
  > at: https://sqlalche.me/e/b8d9)

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

**Problem:** joining a table to itself (or joining Comment twice) needs an **alias** so SQL
can say `comments AS c1` vs `comments AS c2`.

```python
# 1.4 — Query invented the alias
query(Issue).join(Comment, aliased=True)

# 2.0 — you create it
target = aliased(Comment)
query(Issue).join(target, Issue.comments)
```

`Issue.comments` tells SQLAlchemy *how* to join (the FK). `target` is the extra name for
Comment in that query.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §16
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §9
- what 1.4 itself says, verbatim:
  > The ``aliased`` and ``from_joinpoint`` keyword arguments to Query.join() are
  > deprecated and will be removed in SQLAlchemy 2.0. (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Group E — Loader strings (#14–15)

**One idea:** `"comments"` is a string. A typo (`"commnets"`) fails at query time.
`Issue.comments` fails when you *build* the option.

#14 and #15 are the **same rule** on two loaders (`joinedload` = JOIN in one query;
`subqueryload` = second query). `selectinload` would break the same way with a string.

This is **not** the N+1 fix itself — only "how you spell the option." N+1 is not a
BREAKAGES entry.

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

```python
# 1.4
.query(Issue).options(joinedload("comments"))

# 2.0
.query(Issue).options(joinedload(Issue.comments))
```

A typo `"commnets"` now fails when you build the option, not later at query time.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §15
- what 1.4 itself says, verbatim:
  > Using strings to indicate column or relationship paths in loader options is
  > deprecated and will be removed in SQLAlchemy 2.0. Please use the class-bound
  > attribute directly. (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)

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

Same rule as #14 on `subqueryload` (second query for the collection instead of a JOIN).

```python
.query(Issue).options(subqueryload(Issue.comments))
```


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §15
- what 1.4 itself says, verbatim:
  > Using strings to indicate column or relationship paths in loader options is
  > deprecated and will be removed in SQLAlchemy 2.0. Please use the class-bound
  > attribute directly. (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Group F — Rows / Result (#16–19)

`session.execute(select(...))` returns a **Result of Rows**, not ORM objects. Extra steps
unwrap (`.scalars()`) or dedupe (`.unique()`). These two methods are not substitutes —
they act on different axes.

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

**Forgot `.scalars()`.** `execute()` returns Rows, not Issues.

```
select(Issue) → execute → [ Row(Issue,), Row(Issue,), ... ]
                              ↑
                         a 1-tuple wrapper, not an Issue

row.title        → AttributeError   (Row has no .title)
row[0].title     → OK               (unwrap by index)
.scalars() → [Issue, Issue, ...]
issue.title      → OK
```

**Trap:** `.scalars()` on `select(Issue.id, Issue.title)` keeps **only column 0**, drops
`title`, often silently. Rule: `.scalars()` when you selected **one** thing.


**Also defensible** — _each verified to run on 2.0.51. Pick deliberately; this is the judgement, not the typing._

```python
session.execute(select(Issue)).all()[0][0].title
```

when you selected several columns and still want the Row — index into it instead of projecting. .scalars() would throw the other columns away, silently.  
_(runs OK)_

**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17

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

**The tier lie.** 2.0 Row is a named tuple. `row["id"]` looks like dict access; tuples only
take integer indices → `TypeError`.

```python
row = conn.execute(text("SELECT id FROM issues")).fetchone()
row["id"]            # 1.4 OK; 2.0 TypeError
row._mapping["id"]   # dict view
row.id               # namedtuple, if the name is a valid identifier
```

**Why `_mapping`:** the dict-like view moved off the Row itself.

**Tier contradiction:** 1.4 tools called this **safe / not a breakage**. Real 2.0.51 still
failed. Flags are not a substitute for running 2.0.


**Also defensible** — _each verified to run on 2.0.51. Pick deliberately; this is the judgement, not the typing._

```python
row.id
```

when the column name is a valid Python identifier — Row is a named tuple in 2.0, so attribute access is the natural spelling. ._mapping is for names that are not identifiers, or when you need the whole dict.  
_(runs OK)_

**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17

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

On 2.0, `row.keys` is treated as "give me the column named `keys`," not "dict `.keys()`."
Hence: `Could not locate column in row for column 'keys'`.

```python
row._mapping.keys()   # dict-like names
row._fields           # namedtuple field names
```


**Also defensible** — _each verified to run on 2.0.51. Pick deliberately; this is the judgement, not the typing._

```python
row._fields
```

the named-tuple field names, without building the mapping view. Same information; ._mapping.keys() is the closer analogue if you were treating the row as a dict.  
_(runs OK)_

**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17
- what 1.4 itself says, verbatim:
  > The Row.keys() method is considered legacy as of the 1.x series of SQLAlchemy and
  > will be removed in 2.0. Use the namedtuple standard accessor Row._fields, or for
  > full mapping behavior use row._mapping.keys() (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

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

**`joinedload` on a collection without `.unique()`.** A JOIN multiplies SQL rows
(one issue × N comments). 1.4 `Query` silently collapsed them; 2.0 `select()` refuses
until `.unique()`.

```
JOIN issues ⨯ comments → extra SQL rows
Issue1+c1, Issue1+c2, Issue2+c3, ...   (more SQL rows than Issues)

1.4 Query: silently collapse to unique Issues
2.0 select(): InvalidRequestError until .unique()
```

```python
session.execute(stmt).all()                      # raises
session.execute(stmt).scalars().all()            # still raises — .unique() is on Result
session.execute(stmt).unique().scalars().all()   # OK

# often better: no JOIN multiplication
select(Issue).options(selectinload(Issue.comments))
```

`.unique()` dedupes **entities by PK** (JOIN copies). Don't blindly unique a column-only
select — that dedupes by **value** and can delete real rows.

**Also defensible** — _each verified to run on 2.0.51. Pick deliberately; this is the judgement, not the typing._

```python
session.execute(select(Issue).options(selectinload(Issue.comments))).scalars().all()
```

the better answer in most cases: selectinload does not JOIN, so it never multiplies rows, so .unique() is not needed at all. Prefer this unless you specifically want one round trip — see study/01-CONCEPTS.md §15 for the tradeoff.  
_(runs OK)_

**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §15

**Tier** — `SQLALCHEMY_WARN_20` says **—**; `future=True` says **InvalidRequestError**  
_SILENT to the sweep_ (measured on 1.4 by `candidates.py`)

---

## Group G — Session lifecycle (#20–22)

Transactions are explicit. Fake "autocommit / subtransactions" are gone; "is there a
transaction?" becomes a question you ask.

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

**No replacement flag.** 1.4 `autocommit=True` ≈ Session tries not to hold a transaction.
2.0: **autobegin** instead.

```
Session created     → no transaction yet
first SELECT/INSERT → transaction starts automatically
you commit/rollback → you end it
```

```python
Session(bind=engine)   # no autocommit=True
...
session.commit()       # even for read-only: end the txn (vacuum / expiry)
```

Same story as "read-only session still needs commit": on Postgres a long-open read blocks
vacuum (table bloat); `expire_on_commit` only fires at commit, so cached attributes never
refresh. See `study/02-MIGRATION-2.0.md` §18 and `study/01-CONCEPTS.md` §14–§15.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §18
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §14
- what 1.4 itself says, verbatim:
  > The Session.autocommit parameter is deprecated and will be removed in SQLAlchemy
  > version 2.0. The Session now features "autobegin" behavior such that the
  > Session.begin() method may be called if a transaction has not yet been started yet.
  > See the section session_explicit_begin for background. (Background on SQLAlchemy 2.0
  > at: https://sqlalche.me/e/b8d9)

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

**Subtransaction (1.4):** fake nesting in Python. **No SQL.** Outer rollback still undoes
everything; inner "commit" was bookkeeping.

**`begin_nested()`:** real DB `SAVEPOINT`. Inner rollback undoes only work after that
savepoint.

```python
session.begin_nested()  # SAVEPOINT foo
# ... risky work ...
# rollback → back to savepoint, outer txn still open
```

If you only wanted "nested begin() so I can commit inner without ending the session," the
2.0 answer is usually: don't fake it — one transaction + `flush()`, or a real savepoint if
you need partial undo.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §18
- what 1.4 itself says, verbatim:
  > The Session.begin.subtransactions flag is deprecated and will be removed in
  > SQLAlchemy version 2.0. See the documentation at session_subtransactions for
  > background on a compatible alternative pattern. (Background on SQLAlchemy 2.0 at:
  > https://sqlalche.me/e/b8d9)

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

```python
session.transaction          # gone
session.get_transaction()    # the txn object, or None
session.in_transaction()     # True/False
```

2.0: "is there a txn?" is a **question** (`in_transaction()`), not an attribute you poke.
Pairs with autobegin (#20): right after `Session()`, there may be no transaction yet.


**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §18
- what 1.4 itself says, verbatim:
  > The Session.transaction attribute is considered legacy as of the 1.x series of
  > SQLAlchemy and will be removed in 2.0. For context manager use, use Session.begin().
  > To access the current root transaction, use Session.get_transaction(). (Background
  > on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)

**Tier** — `SQLALCHEMY_WARN_20` says **RemovedIn20**; `future=True` says **ok**  
_sweep only - flag misses it_ (measured on 1.4 by `candidates.py`)

---

## Group H — #23 cascade_backrefs (silent)

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

The one line 1.4 let you omit. Explicit, local, and works on both versions.

```
project in session

project.issues.append(issue)   → 2.0 still INSERTs
issue.project = project        → 2.0: no add, no INSERT, no error
```

**Fixes:** `session.add(issue)` / append on the collection / `cascade_backrefs=False` on
1.4 to find sites early.

This repo's `seed.py` used `comment.issue = issue` → comments/assignments can vanish on
2.0 while the script still "succeeds." A passing test suite does not see this unless it
asserts on row counts.

**Also defensible** — _all three work; they differ in what they cost you._

```python
project.issues.append(issue)     # write the COLLECTION side instead
```

The save-update cascade proper survives 2.0, so this needs no `session.add()` at all.
Prefer it when you are already building the parent's collection — but note it reads
as identical to the broken form on 1.4, so it does not help you FIND the other sites.

```python
# in models.py, while still on 1.4
issues = relationship('Issue', backref=backref('project', cascade_backrefs=False))
```

Adopts the 2.0 behaviour before upgrading, which turns a silent 2.0 data loss into a
loud 1.4 failure you can chase down. The most useful of the three if you have a large
codebase and no idea how many sites rely on the cascade — and the least useful if you
already know, because it changes runtime behaviour to find them.

**Docs**

- [`../study/02-MIGRATION-2.0.md`](../study/02-MIGRATION-2.0.md) §17 — the mechanism, and what it does to seed.py
- [`../study/01-CONCEPTS.md`](../study/01-CONCEPTS.md) §14 — the save-update cascade this is half of
- what 1.4 itself says, verbatim:
  > "X" object is being merged into a Session along the backref cascade path for
  > relationship "X"; in SQLAlchemy 2.0, this reverse cascade will not take place.
  > Set cascade_backrefs to False in either the relationship() or backref() function
  > for the 2.0 behavior; or to set globally for the whole Session, set the
  > future=True flag

**Tier** — `RemovedIn20Warning`, but only in modules that WRITE data; `app.py`'s
sweep misses it entirely. See `sweep.py`.
