# Compose — multi-container study notes

Part of [`sqlalchemy-upgrade-agent`](README.md). The companion to
[`DOCKER-STUDY.md`](DOCKER-STUDY.md), which covers a **single** container: images, layers, the
build cache, and the Dockerfile. This file starts where that one stops — **more than one
container, and how they find each other.**

Section numbering continues from `DOCKER-STUDY.md`: that file is §1–§3, this one is §4. So a
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

Fixes: a **healthcheck** plus `depends_on: condition: service_healthy` — or, the answer a senior
engineer gives, **make the app retry on startup**, because in production the database can also
vanish *after* boot and a start-order guarantee does nothing for you then.

### 4.3 Why Postgres for the exercise

Deliberate. Databases are your genuine strength — so the *new* thing you're learning on Day 6
is Docker networking, not the database. If the exercise used something unfamiliar you'd be
debugging two things at once and learning neither.

### 4.4 Volumes and persistence

**A container's writable layer dies with the container** (§1.1).

- **Named volumes** — Docker manages the storage. What you want for Postgres data.
- **Bind mounts** — a host directory mapped in. Great for live-editing source in development;
  a portability liability in production.

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
