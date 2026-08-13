# Postgres — study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). Third in the set:

| file | subject |
|---|---|
| [`04-DOCKER.md`](04-DOCKER.md) | **§1–§3** — one container: images, layers, the Dockerfile |
| [`05-COMPOSE.md`](05-COMPOSE.md) | **§4** — several containers: networking, volumes, healthchecks |
| this file | **§5** — the database inside one of them |

Numbering continues across all three, so `§2.5`, `§4.1` and `§5.3` are unambiguous.

Same rules: every number is measured against this repo, and the command that produces it is
given. The stack must be up for most of these — `docker compose up --build` first.

---

## The short version

- **You do not need a published port to use the database.** `docker compose exec` runs psql
  *inside* the running container (§5.1)
- **A fresh server has three databases**, and two are machinery you never touch (§5.3)
- **`postgres` is the maintenance database**, not yours — application tables belong in one of
  your own (§5.3)
- **The same `models.py` produces different DDL** on Postgres and SQLite. Postgres uses a real
  sequence for the primary key and stores timestamps without a timezone (§5.4)
- **`POSTGRES_USER` creates a superuser**, whatever you name it (§5.5)

---

## §5 — the database

### 5.1 Getting a shell without opening a port

`docker-compose.yml` deliberately publishes no ports (§4.1). You still get a full session:

```
# runnable: docker compose exec db psql -U app -d issues
psql (16.14)
Type "help" for help.

issues=#
```

`exec` runs a new process **inside the already-running container**, so it never touches the
network. Two commands that look similar and are not:

| | |
|---|---|
| `docker compose exec db …` | run this in the **existing** container — the live database |
| `docker compose run db …` | start a **new** container from the image — a different, empty one |

That distinction is §1.1 again: a new container gets its own writable layer. `run` is how
people accidentally query an empty database and conclude their data vanished.

For one-off queries, skip the interactive shell entirely:

```bash
docker compose exec db psql -U app -d issues -c  "select count(*) from issues;"   # with headers
docker compose exec db psql -U app -d issues -tAc "select count(*) from issues;"  # bare value
```

`-t` drops headers, `-A` drops column alignment. `-tAc` is what you want inside scripts.

### 5.2 The psql survival kit

Backslash commands are psql's own, not SQL. They do not end in a semicolon.

| | |
|---|---|
| `\dt` | list tables |
| `\d issues` | describe one table — columns, indexes, foreign keys |
| `\d+ issues` | the same plus storage and size |
| `\l` | list databases |
| `\du` | list roles |
| `\conninfo` | which database and role am I actually on |
| `\x` | toggle expanded output — for rows too wide to read |
| `\q` | quit |

`\conninfo` is the one to reach for first when something is confusing:

```
# runnable: docker compose exec db psql -U app -d issues -c "\conninfo"
You are connected to database "issues" as user "app" via socket in "/var/run/postgresql" at port "5432".
```

It answers "am I even where I think I am" before you start doubting your query.

### 5.3 Three databases, two of which are machinery

```
# runnable: docker compose exec db psql -U app -d issues -tAc \
#             "select datname from pg_database order by datname;"
issues
postgres
template0
template1
```

`issues` is ours. The other three ship with every Postgres server:

| database | what it is |
|---|---|
| `postgres` | the **maintenance database**. It exists so a superuser always has somewhere to connect. Not for your tables |
| `template1` | the mould. `CREATE DATABASE x` means *"copy template1"*. Install an extension here and every future database inherits it |
| `template0` | a pristine, **locked** copy of template1 |

Why two templates? Because `template1` is *meant* to be modified, and once you allow that you
need an untouched original. The catalog shows the difference:

```
# runnable: docker compose exec db psql -U app -d issues -c \
#             "select datname, datistemplate, datallowconn from pg_database order by datname;"
  datname  | datistemplate | datallowconn
-----------+---------------+--------------
 issues    | f             | t
 postgres  | f             | t
 template0 | t             | f
 template1 | t             | t
```

**`template0` has `datallowconn = f` — you cannot connect to it at all.** That guarantee is
what makes it useful for the two jobs it has: rebuilding a broken `template1`, and creating a
database with a *different encoding or collation*, which `template1` cannot do because it may
already contain text invalid in the new encoding.

**Application tables in `postgres` is the smell to avoid.** One line fixes it — `POSTGRES_DB`
(§4.6) — and it is why this project's tables live in `issues`.

### 5.4 The same models, two different schemas

`models.py` never mentions Postgres or SQLite. `create_all()` asks the dialect what to emit,
and the two answers differ in ways worth knowing.

**Postgres:**

```
# runnable: docker compose exec db psql -U app -d issues -c "\d issues"
   Column    |            Type             | Nullable |              Default
-------------+-----------------------------+----------+------------------------------------
 id          | integer                     | not null | nextval('issues_id_seq'::regclass)
 title       | character varying           |          |
 description | character varying           |          |
 status      | character varying           |          |
 created_at  | timestamp without time zone |          |
 project_id  | integer                     |          |
Indexes:
    "issues_pkey" PRIMARY KEY, btree (id)
Foreign-key constraints:
    "issues_project_id_fkey" FOREIGN KEY (project_id) REFERENCES projects(id)
Referenced by:
    TABLE "comments" CONSTRAINT "comments_issue_id_fkey" FOREIGN KEY (issue_id) REFERENCES issues(id)
```

**SQLite, same model:**

```
# runnable: uv run python -c "
#   import sqlite3
#   print(sqlite3.connect('issues.db').execute(
#     \"select sql from sqlite_master where name='issues'\").fetchone()[0])"
CREATE TABLE issues (
	id INTEGER NOT NULL,
	title VARCHAR,
	description VARCHAR,
	status VARCHAR,
	created_at DATETIME,
	project_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES projects (id)
)
```

Four differences that matter:

**The primary key is a real object in Postgres.** `nextval('issues_id_seq')` is a **sequence** —
a separate database object handing out numbers. SQLite's `INTEGER PRIMARY KEY` is an alias for
its internal rowid and has no such object. The sequence has state you can read:

```
# runnable: docker compose exec db psql -U app -d issues -tAc "select last_value from issues_id_seq;"
200
```

That matters the first time you load rows with explicit ids: the sequence does not advance, and
the next insert collides with a row that already exists. SQLite never presents that problem, so
it is a genuine "worked locally, broke on Postgres" bug.

**`timestamp without time zone`.** SQLAlchemy's `DateTime` maps to the naive type by default —
Postgres stores what you gave it and remembers nothing about the offset. `DateTime(timezone=True)`
gets you `timestamptz`. SQLite's `DATETIME` is a string with no opinion at all, so this
distinction is invisible until you move.

**Postgres shows you the reverse direction.** `Referenced by:` lists every table pointing *at*
this one — the incoming half of the foreign-key graph. SQLite has no equivalent, and it is
genuinely useful for "what breaks if I drop this".

**Types are checked.** `character varying` with no length is unbounded here, but Postgres
enforces types on write; SQLite applies type *affinity* and will cheerfully store a string in an
INTEGER column. Code that passed on SQLite can fail on Postgres for that reason alone.

### 5.5 Roles, and the privilege that was not separated

```
# runnable: docker compose exec db psql -U app -d issues -c "\du"
 Role name |                         Attributes
-----------+------------------------------------------------------------
 app       | Superuser, Create role, Create DB, Replication, Bypass RLS
```

One role, and it is a **superuser**. `POSTGRES_USER` renamed the superuser rather than creating
a restricted account (§4.6). So the app can drop any database on this server, which is fine for
a disposable local stack and is not what you would ship.

What real separation needs, since it is more than an env var:

- a second role created by a script in `/docker-entrypoint-initdb.d/`, which Postgres runs on
  first initialisation
- `GRANT CONNECT` on the database and `GRANT USAGE, CREATE` on the schema — **since PG15 the
  `public` schema no longer grants `CREATE` to everyone**, so `create_all()` fails without it
- `ALTER DEFAULT PRIVILEGES` for tables that do not exist yet, because a plain `GRANT` only
  covers what is there when it runs

Deliberately not done here. Worth knowing the gap is open rather than assuming an env var
closed it.

### 5.6 What changes when SQLite becomes Postgres

Everything measured in Part A survives the move — the N+1, the warning sweep, every pattern in
[`BREAKAGES.md`](../BREAKAGES.md) — which is why Postgres was the right prop for Day 6 (§4.3). The
differences that do bite are these:

| | SQLite | Postgres |
|---|---|---|
| **concurrency** | one writer, whole-file lock | many writers, row-level locks |
| **types** | affinity — a string fits an INTEGER column | enforced |
| **primary keys** | rowid alias | a sequence with its own state (§5.4) |
| **identifier case** | insensitive | folded to lower-case unless `"quoted"` |
| **`ALTER TABLE`** | very limited | full |
| **runs as** | a file, no server | a server you must reach over a network (§4.1) |

The last row is the one that changed this project's shape: a file needs no hostname, no port,
no readiness check and no password. Everything in `05-COMPOSE.md` §4.1 and §4.2 exists
because a database stopped being a file.

**Identifier case is the sharpest trap.** `CREATE TABLE Issues` produces a table called
`issues`; `CREATE TABLE "Issues"` produces one that must be quoted forever afterwards. It is
also why this project's Postgres role is `app` rather than the project name — a hyphen forces
quoting in every statement that mentions it.

---

## Drills

Cold, no notes.

1. *"You have no published port. How do you get a psql prompt, and why does it work?"*
2. *"What is `template0` for, and why can't you connect to it?"*
3. *"Your app's tables are in the `postgres` database. Why is that wrong?"*
4. *"You loaded rows with explicit ids and the next insert fails on a duplicate key. Why does
   this never happen on SQLite?"*
5. *"`POSTGRES_USER=app` — is `app` a limited account? Prove it."*
6. *"Same `models.py`, two databases. Name three ways the generated schema differs."*

## The docs — read these

- psql reference — https://www.postgresql.org/docs/current/app-psql.html
- Template databases — https://www.postgresql.org/docs/current/manage-ag-templatedbs.html
- `GRANT` and privileges — https://www.postgresql.org/docs/current/sql-grant.html
- Sequences — https://www.postgresql.org/docs/current/sql-createsequence.html
- Date/time types — https://www.postgresql.org/docs/current/datatype-datetime.html
- The official image — https://hub.docker.com/_/postgres
- SQLAlchemy's Postgres dialect — https://docs.sqlalchemy.org/en/14/dialects/postgresql.html
