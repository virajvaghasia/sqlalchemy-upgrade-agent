# Compose — multi-container study notes

Part of [`sqlalchemy-upgrade-agent`](../README.md). The companion to
[`04-DOCKER.md`](04-DOCKER.md), which covers a **single** container: images, layers, the
build cache, and the Dockerfile. This file starts where that one stops — **more than one
container, and how they find each other.**

Section numbering continues from `04-DOCKER.md`: that file is §1–§3, this one is §4. So a
reference to "§2.5" or "§4.1" is unambiguous across both. §4.5 (GPU) rides along here to keep
the numbering continuous, even though it concerns a single container.

Same rule as its companion: every number is measured against this repo, and the command that
produces it is given.

---

§4.0–§4.4 and §4.6 describe the stack in this repo's `docker-compose.yml`, measured. §4.5 is
Day 7 and still concepts-only, because the lab machine isn't reachable.

## The short version

- **Compose runs several containers; the Dockerfile builds one image.** Compose *calls* the
  Dockerfile, it doesn't replace it (§4.0)
- **It adds no new primitives** — network, image, name, environment. The same four you can type
  by hand (§4.0)
- **Every container already has networking.** A user-defined network adds two things: **DNS**,
  so you can use a stable name instead of an IP that changes, and **isolation** — containers on
  different networks cannot reach each other at all, even by IP (§4.1)
- **`localhost` inside a container means that container**, not your Mac (§4.1)
- **`ports:` is only for traffic from outside** — two containers on one network need none (§4.1)
- **`depends_on` waits for *started*, not *ready*.** A healthcheck closes the gap (§4.2)
- **A volume is data that outlives the container.** `down` keeps it, `down -v` deletes it (§4.4)
- **`POSTGRES_USER` renames the superuser** — it does not create a limited account (§4.6)
- **Anything you don't name, Compose names for you** — usually after the folder. Pin the
  project and the built image, or they drift (§4.7)

---

## §4 — more than one container

### 4.0 Compose does not replace the Dockerfile

The most common misunderstanding, so first:

| | answers |
|---|---|
| **Dockerfile** | how to build **one image** |
| **Compose** | how to run **several containers together** |

They compose (hence the name). `docker-compose.yml` says `build: .` for the app service —
that *is* the Dockerfile, invoked. The `db` service has no Dockerfile only because it uses a
prebuilt image from a registry.

#### Compose is not magic — the same thing by hand

Everything Compose did can be done with plain `docker` commands. Proof, run against this
repo's image:

```
# runnable, in order:
docker network create demo-net
docker run -d --name demo-db --network demo-net -e POSTGRES_PASSWORD=devpassword postgres:16-alpine
docker run --rm --network demo-net \
  -e DATABASE_URL="postgresql+psycopg2://postgres:devpassword@demo-db:5432/postgres" sqlalchemy-upgrade-agent

   issues in table: 200
```

##### What each part is doing, and why

**1. `docker network create demo-net`** — makes a private virtual network. Nothing is on it
yet. It exists because containers on a network *you* create get **DNS by name**, and on
Docker's built-in default network they do not. This one line is the difference between
`@demo-db:5432` resolving and failing.

**2. `docker run -d --name demo-db --network demo-net -e POSTGRES_PASSWORD=… postgres:16-alpine`**

| piece | what it does |
|---|---|
| `docker run` | create a **new** container from an image, and start it |
| `-d` | **detached** — run in the background and hand the terminal back. Postgres never exits, so without this the terminal is stuck |
| `--name demo-db` | name the container. **That name is its hostname on the network** — the whole point of the exercise |
| `--network demo-net` | attach it to the network from step 1 |
| `-e POSTGRES_PASSWORD=…` | set an env var inside it. This image refuses to start without this one |
| `postgres:16-alpine` | which image. `16` = major version, pinned; `alpine` = the small base |

**3. `docker run --rm --network demo-net -e DATABASE_URL=… sqlalchemy-upgrade-agent`**

| piece | what it does |
|---|---|
| `--rm` | delete the container when it exits. The app runs, prints, finishes — no reason to keep it |
| `--network demo-net` | **the same network**, so `demo-db` resolves. Omit it and this fails |
| `-e DATABASE_URL=…` | tells the app where the database is; `seed.py` reads it with `os.getenv` |
| `sqlalchemy-upgrade-agent` | the image built from this repo's Dockerfile |

**Why `-d` on one and `--rm` on the other:** Postgres is a server that runs forever, so it goes
to the background. The app is a batch job that finishes, so it cleans up after itself.

##### The URL, decoded

```
postgresql+psycopg2 :// postgres : devpassword @ demo-db : 5432 / postgres
└─ dialect+driver ─┘     └user┘   └─password─┘   └─host─┘  └port┘ └─db name─┘
```

`postgresql` is the SQL dialect SQLAlchemy speaks; `psycopg2` is the library doing the talking.
**`demo-db` is the container name from step 2** — that is the join between the two commands.

##### The same thing, in Compose

| by hand | in `docker-compose.yml` |
|---|---|
| `docker network create demo-net` | automatic — one network per project |
| `--name demo-db` | the **key** under `services:` is the name |
| `--network demo-net` | automatic — every service joins it |
| `-e POSTGRES_PASSWORD=…` | `environment:` |
| `postgres:16-alpine` | `image:` |
| a prebuilt image | `build: .` — builds from the Dockerfile instead |
| `-d` / `--rm` | `docker compose up` / `down` |

**So Compose introduces nothing new.** It's the same four primitives — network, image, name,
environment — written down instead of typed. What you gain is one command instead of four,
`.env` substitution, volume management, dependency ordering, and a `down` that cleans up
everything it made.

#### The part that is NOT optional: a user-defined network

Do the same thing on the **default** bridge — omit `--network` — and it fails:

```
# runnable: docker run -d --name plain-db3 -e POSTGRES_PASSWORD=... postgres:16-alpine
#           docker run --rm -e DATABASE_URL="...@plain-db3:5432/postgres" sqlalchemy-upgrade-agent
psycopg2.OperationalError: could not translate host name "plain-db3" to address:
Name or service not known
```

**The default bridge has no DNS.** Name resolution between containers is a property of
*user-defined* networks, which is what Compose creates for you. This is the single fact
behind §4.1.

#### A trap that will waste an hour: the stale image

While measuring the above, the network test appeared to *succeed on the default bridge* —
which is impossible. The cause was not networking:

```
# runnable: docker inspect sqlalchemy-upgrade-agent --format '{{.Created}}'
image built:   2026-08-10T23:26
seed.py edited 2026-08-11T12:38
```

The image was **13 hours older than the code**. It still contained the pre-`DATABASE_URL`
version of `seed.py`, so the container ignored the env var entirely and quietly used SQLite —
producing plausible, familiar output while proving nothing about Postgres or networking.

**A container runs the code baked into its image, not the code in your editor.** When a result
makes no sense, check the image's age before you doubt the concept:

```
docker inspect <image> --format '{{.Created}}'
```

`docker compose up --build` rebuilds; `docker compose up` alone does not.

The deeper cause was a naming one, and it is now fixed. Compose used to build
`sqlalchemy-upgrade-agent-app` while `docker build -t sqlalchemy-upgrade-agent .` built `sqlalchemy-upgrade-agent` — **two
images from one Dockerfile, both current, drifting apart in silence.** Declaring `image:` next
to `build:` collapses them into one name. See §4.7.

### 4.1 Networking — why the container can't reach anything

The default mental error is thinking the container shares your machine's network. It doesn't.
It gets its **own network namespace**: own interfaces, own `localhost`.

**`localhost` inside a container means the container itself.** Your app connecting to
`localhost:5432` to find Postgres is looking for Postgres *inside its own container*, and there
isn't one. This is the single most common Docker networking bug; expect to hit it.

**Published ports (`-p 8000:8000`) are a hole punched from the host into the container.** They
are for traffic from *outside*. Containers talking to *each other* don't need them at all.

**On a user-defined network, containers find each other by service name via Docker's embedded
DNS.** Your app reaches the database at the hostname `db` — not an IP, not `localhost`.

Day 6's gate is being able to explain *how the app resolved the hostname*. If the answer isn't
"Docker's embedded DNS resolved the service name on the user-defined bridge network," you
haven't got it yet.

#### "So without creating a network there is no network?" — no, the opposite

Every container **always** has networking. Docker attaches it to a built-in network called
`bridge` whether you ask or not: it gets an IP, it can reach the internet, and other containers
can reach it. Creating a network does not switch networking on.

What the default network lacks is **name resolution**, and only that. Measured — one Postgres
container on the default network, reached two ways:

```
# runnable: docker inspect ip-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
172.17.0.2

# runnable: docker run --rm -e DATABASE_URL="...@172.17.0.2:5432/postgres" sqlalchemy-upgrade-agent
   issues in table: 200                            ← by IP: works

# runnable: docker run --rm -e DATABASE_URL="...@ip-db:5432/postgres" sqlalchemy-upgrade-agent
psycopg2.OperationalError: could not translate host name "ip-db" to address
```

**By IP it works. By name it doesn't.** So on the default network, DNS was the only thing
missing — not connectivity.

#### But `--network` is doing two jobs, not one

That last sentence is only true while both containers sit on the **same** network. Put them on
different ones and connectivity really is the missing piece — a container on the default bridge
cannot reach `172.18.0.2` on a user-defined network **even by IP**:

```
# runnable: docker run --rm --entrypoint python sqlalchemy-upgrade-agent -c \
#   "import socket; s=socket.socket(); s.settimeout(8); s.connect(('172.18.0.2', 5432))"
FAILED: TimeoutError timed out
```

Note *timed out*, not "refused" and not "unknown host". Nothing answered, because there is no
route between two bridge networks. Docker networks are isolation boundaries.

The full picture, all four cells measured:

| | same network | different networks |
|---|---|---|
| **by IP** | works | **times out** — no route |
| **by name** | works — embedded DNS | fails, and DNS wouldn't help anyway |

So `--network demo-net` buys you two separate things:

1. **Membership** — *which* containers you can reach at all. This is real connectivity, and
   containers on different networks have none.
2. **DNS** — on a user-defined network only, container names resolve to their current IPs.

The default bridge gives you membership with everything else on it, and no DNS. A user-defined
network gives you a smaller, deliberate membership *and* DNS. That second property is why
Compose puts every service of a project on one network of its own: the services can find each
other by name, and nothing outside the project is on it at all.

#### Then why not just use the IP?

Because you don't get to keep it. IPs are handed out in start order, so a container that came
up first yesterday can come up second today:

```
# runnable: docker inspect ip-db --format '...IPAddress...'
before:  172.17.0.2
after recreating it behind another container:  172.17.0.3
```

Nothing about your setup changed. A different container simply started first.

So an IP cannot go in `.env`, in a config file, or in anything you commit. **You need a stable
name, and a name that means anything requires DNS** — which is what a user-defined network adds
and the default one does not.

That is the entire reason for `docker network create`, and the entire reason Compose makes one
for every project without being asked:

| | default `bridge` | user-defined network |
|---|---|---|
| container gets an IP | yes | yes |
| can reach the internet | yes | yes |
| reachable **by IP** | yes | yes |
| reachable **by name** | **no** | **yes** |
| IP stable across restarts | no | no — but you no longer care |

### 4.2 `depends_on` does not mean "ready"

It controls **start order**. It waits for the container to be *started*, not for the process
inside to be *ready to accept connections*.

Postgres takes seconds to initialise. Your app starts immediately, connects, is refused, and
crashes. Compose did what you asked; you asked for the wrong thing.

#### What the failure actually looks like

Downgrade `depends_on` to its plain form and start on a fresh volume:

```yaml
depends_on:
  - db          # "start db first" — and nothing more
```

```
# runnable: docker compose -f docker-compose.yml -f no-healthcheck.yml up --build
psycopg2.OperationalError: connection to server at "db" (172.18.0.2), port 5432 failed:
Connection refused
```

**Read that error carefully — it says this is not a networking problem.** The name `db`
resolved, to `172.18.0.2`. The container was up and had an address. Postgres simply was not
listening on 5432 yet, because it was still initialising its data directory.

Three errors, three different causes (§4.1):

| error | meaning |
|---|---|
| `could not translate host name` | DNS — wrong network, or the name is wrong |
| **`connection refused`** | **reached the host, nothing listening yet — this one** |
| `timed out` | no route — the containers are on different networks |

#### Fix 1 — a healthcheck, so "started" becomes "ready"

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 2s      # run it every 2s
  timeout: 3s       # a run slower than this counts as a failure
  retries: 15       # this many consecutive failures before it is "unhealthy"
```

`test` is any command, and **exit code 0 means healthy**. `pg_isready` ships with Postgres and
does exactly this job. For an HTTP service it would be a `curl` of a health endpoint.

A container with a healthcheck has three states, and you can watch them move:

```
# runnable: docker inspect sqlalchemy-upgrade-agent-db-1 --format '{{.State.Health.Status}}'
t+1s: starting
t+2s: starting
t+3s: healthy
```

Then `depends_on` can wait for the *state* rather than the container:

```yaml
depends_on:
  db:
    condition: service_healthy
```

The conditions available:

| condition | waits until |
|---|---|
| `service_started` | the container is running — the near-useless default |
| `service_healthy` | its healthcheck passes |
| `service_completed_successfully` | it ran and exited 0 — for migration/init jobs |

#### `CMD-SHELL` is `/bin/sh`, and that broke a healthcheck for real

Added 2026-08-14, when the `qdrant` service arrived. The container ran perfectly, answered every
request, and reported `unhealthy` forever.

The Qdrant image has no `curl`, `wget` or `nc` — only `bash`. So the check used **bash's
`/dev/tcp`**, which opens a TCP socket as if it were a file:

```yaml
# BROKEN
healthcheck:
  test: ["CMD-SHELL", "exec 3<>/dev/tcp/127.0.0.1/6333 && ..."]
```

```
# runnable: docker inspect sqlalchemy-upgrade-agent-qdrant-1 --format '{{json .State.Health.Log}}'
exit: 2
out: '/bin/sh: 1: cannot create /dev/tcp/127.0.0.1/6333: Directory nonexistent'
```

**`/dev/tcp` is a bash builtin, not a real device.** Nothing is there on the filesystem — bash
intercepts the path and opens a socket instead. `CMD-SHELL` runs its string through `/bin/sh`,
which on Debian is **dash**, and dash has no such feature. It tries to create an actual file, in
a directory that does not exist, and fails on every probe.

The fix is to name the shell rather than assume it:

```yaml
# WORKS
healthcheck:
  test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/6333 && ..."]
```

**Two things worth taking from this beyond the specific bug.**

`CMD` versus `CMD-SHELL` is the same distinction as in the Dockerfile (§2.5): `CMD` is an argv
array executed directly, `CMD-SHELL` wraps the string in `/bin/sh -c`. Anywhere you rely on a
**bash** feature — `/dev/tcp`, `[[ ]]`, arrays, `${var,,}` — `CMD-SHELL` will not give it to you.

And this is the **worst failure shape a healthcheck has**: nothing crashed, nothing logged an
error, and the service was ready the whole time. A green service reporting `unhealthy` means
anything using `condition: service_healthy` waits forever on something that is fine — a hang
with no error anywhere to explain it. **A healthcheck that lies is worse than no healthcheck**,
because `depends_on` trusts it.

There is also `start_period:`, a grace window during which failures do not count toward
`retries`. Postgres does not need one; a JVM service will.

#### Fix 2 — make the app retry, which is the one that generalises

A healthcheck solves the race **once, at startup, and only inside Compose.** Three situations
it does nothing for:

- the database **restarts** at 3am while your app is running
- a failover moves it, or a network blip drops the connection
- the app runs somewhere Compose is not — Kubernetes, a VM, someone's laptop

A start-order guarantee is worth nothing in all three, because there is no "start" to order.

So `make_engine()` in `seed.py` now blocks until the database answers:

```python
def wait_for_db(engine, attempts=30, delay=1.0):
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            if attempt == attempts:
                raise RuntimeError(...) from exc
            time.sleep(delay)
```

Two details that matter:

- **`create_engine()` connects to nothing.** It is lazy — it builds a factory and stops. Asking
  "is the database there?" requires actually opening a connection, which is what
  `engine.connect()` plus a trivial `SELECT 1` does.
- **Catch `OperationalError` specifically**, not everything. A wrong password raises too, and
  retrying that thirty times only delays a failure that waiting cannot fix.

Proof — the *same* broken Compose file from above, with retry in place:

```
# runnable: docker compose -f docker-compose.yml -f no-healthcheck.yml up --build
database reachable after 2 attempts
database: postgresql+psycopg2://app:***@db:5432/issues
38 open issues
```

**No healthcheck, no `condition:`, and it works.** One retry, one second.

#### Use both, for different reasons

| | fixes | still fails when |
|---|---|---|
| healthcheck + `condition:` | the boot race, cleanly, with no code | the database restarts later; you are not on Compose |
| retry in the app | any unavailability, anywhere | never — but it costs code and needs a real give-up |

The healthcheck also earns its place as **documentation**: `docker compose ps` reports a service
as healthy or not, which is a far better first question than reading application logs.

**The answer to give when asked:** `depends_on` orders *starts*, and a start is not a readiness.
A healthcheck upgrades it to readiness. Neither survives the database going away afterwards —
for that the client has to retry, which is why retry is the property that actually matters and
the healthcheck is the convenience.

### 4.3 Why Postgres for the exercise

Deliberate: it keeps the number of new variables at one.

Postgres is well documented, behaves predictably, and — importantly — its own behaviour is not
what is under test here. The only new mechanism on Day 6 is **Docker networking**. Swap in an
unfamiliar datastore and any failure has two candidate causes, the network or the database, and
neither gets understood.

It also carries forward: `SQLALCHEMY_WARN_20`, the N+1, and every pattern in `deliverables/BREAKAGES.md`
behave the same against Postgres as against SQLite, so nothing measured in Part A has to be
re-established.

### 4.4 Volumes and persistence

**A container's writable layer dies with the container** (§1.1).

There are two ways to give a container storage that outlives it, and they are not
interchangeable.

#### Named volume — Docker owns the storage

```yaml
volumes:
  - pgdata:/var/lib/postgresql/data     # name : path inside the container
```

The left side is a *name*, not a path. Docker decides where the bytes actually live:

```
# runnable: docker volume inspect sqlalchemy-upgrade-agent_pgdata --format '{{.Mountpoint}}'
/var/lib/docker/volumes/sqlalchemy-upgrade-agent_pgdata/_data
```

Note that path does **not** exist on this Mac:

```
# runnable: ls /var/lib/docker/volumes
ls: /var/lib/docker/volumes: No such file or directory
```

It is inside the Linux VM that Docker Desktop runs (§2.1). That is the point of a named
volume — **you do not know or care where it is**, and you reach it only through Docker. It
survives `down`, dies with `down -v`, and moves with the project name (§4.7).

**This is what Postgres data wants.** Database files are Docker's problem, not yours.

#### Bind mount — you own the storage

```bash
docker run -v /some/host/dir:/data image      # left side is a real host PATH
```

A directory that already exists on your machine, mapped into the container. **The same files,
seen from two places** — not a copy, not a sync. Measured both directions:

```
# runnable: echo "written on the host" > /tmp/bindtest/from-host.txt
#           docker run --rm -v /tmp/bindtest:/data --entrypoint sh <image> \
#             -c 'ls -l /data; cat /data/from-host.txt'
-rw-r--r-- 1 app app 20 Aug 13 16:38 from-host.txt
written on the host
```

```
# runnable: docker run --rm -v /tmp/bindtest:/data --entrypoint sh <image> \
#             -c 'echo "written in the container" > /data/from-container.txt'
#           ls -l /tmp/bindtest
-rw-r--r--  1 virajvaghasia  wheel  25 Aug 13 09:38 from-container.txt
-rw-r--r--@ 1 virajvaghasia  wheel  20 Aug 13 09:38 from-host.txt
```

Instant, both ways, no rebuild. **That is what makes it good for development** — mount your
source in and edit with your normal editor while the container runs the changed file. It is
the standard answer to *"do I really rebuild the image for every one-character change?"*

#### The trap, and it is waiting at the lab

Look again at the ownership in those two blocks. Inside the container the host's file appeared
as owned by `app`; on the host, the container's file appeared as owned by `virajvaghasia`.
**Neither of those is a translation you should count on** — it is Docker Desktop's macOS file
sharing being helpful.

**On native Linux there is no translation.** A bind mount is the host's filesystem, directly,
and uids are numbers with no mapping layer. A container running as uid 10001 (§3.1) writes
files owned by uid 10001 on the host — a uid that may belong to nobody, or to somebody else.
The symptoms are `Permission denied` for a file you can see, or root-owned files appearing in
your working tree that your editor cannot save over.

*Not measured here — the lab machine is unreachable, and this Mac cannot reproduce native
Linux behaviour. Flagged rather than asserted, and worth re-testing on the PC.*

The usual fixes: run the container as your own uid (`--user "$(id -u):$(id -g)"`), or make the
container's uid match a real group on the host. **Named volumes sidestep the whole question**,
because Docker owns the files and nothing on the host is looking at them.

#### Choosing

| | named volume | bind mount |
|---|---|---|
| who picks the location | Docker | you |
| visible in your editor | no | yes |
| survives `down` | yes | yes — it was never Docker's |
| removed by `down -v` | yes | **no** |
| uid headaches on Linux | none | yes (see above) |
| good for | **databases, anything stateful** | **source during development** |

The short version: **named volumes for data you never want to look at, bind mounts for files
you are editing.** This project uses a named volume for Postgres and no bind mounts at all —
`COPY` puts the source in the image, because the container is run rather than developed in.

If Postgres data lives in the container's writable layer, `docker compose down` deletes your
database. Know which of the two you configured *before* learning this the other way.

### 4.5 GPU in a container (Day 7)

The container needs the host's NVIDIA driver surfaced into it — that's what the **NVIDIA
Container Toolkit** does, wiring device nodes and driver libraries through so `--gpus all`
gives real access to the 3060.

**The trap: your model loads, runs, produces correct output — entirely on CPU, at a tenth of
the speed, and nothing errors.** Silent CPU fallback is the norm. So the check is never "did it
work." It's `nvidia-smi` reporting the GPU *from inside the container*, and your framework
reporting CUDA is actually available.

That's why the Day 7 gate says *"`docker run --gpus all ...` reports the 3060 from inside a
container"* rather than "the model ran."

### 4.6 `POSTGRES_USER` does not give you a limited account

A fresh Postgres container has three databases:

```
# runnable: docker compose exec db psql -U app -d issues -tAc \
#             "select datname from pg_database order by datname;"
issues
postgres
template0
template1
```

`postgres` is the server's **maintenance database** — it exists so a superuser always has
somewhere to connect. Leaving application tables in it works and is a smell: no separation
between the server's own bookkeeping and your data.

`POSTGRES_DB` fixes that for one line. `POSTGRES_USER` looks like it fixes privileges too.
**It does not:**

```
# runnable: docker compose exec db psql -U app -d issues \
#             -c "select rolname, rolsuper from pg_roles where rolcanlogin;"
 rolname | rolsuper
---------+----------
 app     | t
```

`rolsuper = t`. `POSTGRES_USER` **renames the superuser**; it does not create a restricted
role. So this stack now has clean *data* separation and no *privilege* separation — the app
can still drop any database on the server.

Real least privilege needs more than env vars: a script in
`/docker-entrypoint-initdb.d/` (the Postgres image runs `.sql` and `.sh` files there on first
init) that creates a second, non-superuser role and grants it rights on the app database only.
Two wrinkles make it more than a one-liner — since **PG15** the `public` schema no longer grants
`CREATE` to everyone, so `create_all()` fails without an explicit grant; and the app role needs
privileges on *future* tables, which is `ALTER DEFAULT PRIVILEGES`, not a one-time `GRANT`.

**Deliberately not done here.** Worth knowing the gap exists rather than believing an env var
closed it.

#### The healthcheck that hangs forever

Setting `POSTGRES_USER` breaks this, silently:

```yaml
test: ["CMD-SHELL", "pg_isready -U postgres"]     # role no longer exists
```

`pg_isready` never succeeds, `db` never becomes healthy, and `app` waits on
`condition: service_healthy` — **which can now never be met.** No error is printed anywhere;
Compose simply hangs. The fix is to interpolate the same variable:

```yaml
test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
```

General rule: **a healthcheck that hardcodes a value configured elsewhere is a hang waiting to
happen**, because a failing healthcheck looks identical to a slow one.

---

### 4.7 Naming — declare it, or Compose invents it

Compose derives names when you don't supply them, and every derived name is a thing that can
change without you touching it.

| thing | if you say nothing | so it's pinned to |
|---|---|---|
| project | the **directory name** | `name: sqlalchemy-upgrade-agent` |
| network | `<project>_default` | (follows the project) |
| volume | `<project>_pgdata` | (follows the project) |
| container | `<project>-<service>-<n>` | (fine — predictable) |
| **image built by `build:`** | **`<project>-<service>`** | **`image: sqlalchemy-upgrade-agent:latest`** |

Two of those matter.

**The project name.** Inferred from the folder, so a clone into a differently named directory
gets a different network *and a different volume* — and quietly cannot find the database it
created yesterday. One `name:` line removes the whole class of problem.

**The image name.** This is the one that already caused real confusion (§4.0). With `build:`
and no `image:`, Compose builds `sqlalchemy-upgrade-agent-app` while `docker build -t sqlalchemy-upgrade-agent .`
builds `sqlalchemy-upgrade-agent`. **Two images, one Dockerfile, both current, drifting apart in silence** —
which is how a 13-hour-old `sqlalchemy-upgrade-agent` produced believable output and disproved nothing.

Adding `image:` next to `build:` means "build it, then tag it this," so both routes land on one
name:

```
# runnable: docker compose build app && docker images sqlalchemy-upgrade-agent --format '{{.Repository}}:{{.Tag}}  {{.ID}}'
sqlalchemy-upgrade-agent:latest  bdd2082b4345

# runnable: docker build -t sqlalchemy-upgrade-agent . && docker images sqlalchemy-upgrade-agent --format '{{.Repository}}:{{.Tag}}  {{.ID}}'
sqlalchemy-upgrade-agent:latest  a5cd24ba5385
```

**One tag, and whichever build ran last owns it.** The IDs differ because Compose stamps extra
labels into the image config —

```
# runnable: docker image inspect sqlalchemy-upgrade-agent:latest --format '{{json .Config.Labels}}'
com.docker.compose.project: sqlalchemy-upgrade-agent
com.docker.compose.service: app
```

— so the two routes are not byte-identical. That's harmless. What matters is that there is no
longer a *second image under a second name* silently going stale, which is what actually bit.

**The rule worth taking away:** in Compose, anything you don't name gets named for you, from
something you didn't think of as configuration — usually the folder. Name the things whose
identity you depend on.
