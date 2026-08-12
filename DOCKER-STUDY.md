# Docker — study notes

Part of [`sqlalchemy-upgrade-agent`](README.md); see [`PHASE-0.md`](PHASE-0.md) for where this
sits in the plan.

Reading material for Phase 0 Part C (Days 4–7). **Mobile-friendly: read it away from the
keyboard.** Every number in here was measured on this repo, and the command that produces it
is given — so you can check it rather than believe it.

## How this doc is split, and why

**This file is about ONE container** — §1–§3: images, layers, the build cache, and every line
of this repo's `Dockerfile`, with its real build output as the worked example.

**More than one container is a different subject and lives in
[`COMPOSE-STUDY.md`](COMPOSE-STUDY.md)** — §4: Compose, networking, volumes, healthchecks. The
numbering runs across both files, so a `§4.x` reference below points there and still resolves.

Everything here is measured against this repo, with the command that reproduces it. Where a
claim turned out to be wrong when measured, the correction is kept rather than quietly edited
out — §2.5 (`exec` does not fix signal handling), §4.0 (a stale image invalidating a result)
and §4.6 (`POSTGRES_USER` not creating a limited role) are all of that kind, and they are the
most useful paragraphs in the file.

---

## The short version — every idea, one line each

**Read this page first.** Plain language, no detail. The `§` tells you where the long version
and the measurement live, if you want them.

### The four words

| word | what it actually is |
|---|---|
| **image** | a frozen snapshot of a whole filesystem. Nothing is running. Like a class in code |
| **container** | one running copy of an image. Like an object. Anything it writes disappears when it stops (§1.1) |
| **Dockerfile** | the recipe that builds **one** image (Part 2) |
| **Compose** | a file that runs **several** containers together. It does not replace the Dockerfile — it calls it (§4.0) |

### Building the image

- **Layers** — every line in the Dockerfile saves its changes as one step, stacked. Same idea as git commits: each is a diff on the one before (§1.2)
- **The cache** — rebuild, and Docker reuses steps whose inputs didn't change. **The first changed step, and everything below it, is redone** (§1.3)
- **So order matters** — put lines that rarely change at the top, lines that change constantly at the bottom. That's why installing dependencies comes *before* copying your code (§1.3)
- **Deleting doesn't shrink** — remove a file in a later step and the bytes stay in the earlier one. That's why multi-stage builds exist (§1.2, §3.3)
- **Build context** — `docker build .` zips up the whole folder and ships it to Docker *before* anything runs (§1.4)
- **`.dockerignore`** — the list of things not to ship. It is not `.gitignore`; the matching rules differ (§1.4)

### What goes in the image

- **Base image** — `FROM` decided ~87% of your image size. `-slim` over the full image: 214MB vs 1.62GB (§2.1)
- **Wheels** — a Python package that's pre-compiled for your OS and CPU. If one exists, installing needs no compiler; if not, pip compiles from source and needs tools `-slim` doesn't have (§2.1)
- **Alpine is a trap for Python** — it uses a different C library, so most wheels don't fit it and pip falls back to compiling (§2.1)
- **Non-root user** — containers run as root unless you say otherwise. Root inside a container is a much better position for an attacker than an ordinary user (§3.1)
- **`pip --no-cache-dir`** — without it, pip's downloaded copies of every package are baked into the image and never read again. Was 9.1MB here (§3.2)

### Running it

- **`CMD`** — the default command. Anything you type after the image name replaces it (§2.5)
- **`ENTRYPOINT`** — always runs; `CMD` becomes its arguments. `--entrypoint` is the escape hatch (§2.5)
- **Array form, not string form** — `["python", "-m", "x"]`, because the string form wraps your program in a shell that swallows shutdown signals (§2.5)
- **A green build proves nothing** — `CMD` is never run at build time, so a broken one builds fine and fails on `docker run` (§2.5)

### More than one container

- **Networking** — each container has its own network, so `localhost` means *itself*, not your Mac (§4.1)
- **Names are hostnames** — on a Compose network, a service called `db` is reachable at `db`. This does **not** work on Docker's default network (§4.0, §4.1)
- **Ports** — `ports:` is only for traffic coming from outside. Two containers talking to each other need nothing (§4.1)
- **Volumes** — a container's own storage dies with it. A named volume survives `docker compose down`, and only `down -v` deletes it (§4.4)
- **`depends_on` ≠ ready** — it waits for the container to *start*, not for the program inside to accept connections. A healthcheck is what closes that gap (§4.2)
- **`.env`** — where the passwords and URLs live. Gitignored; `.env.example` is the committed template (§4.6)

### The three things that fooled us

- **A stale image** — a container runs the code baked into its image, not what's in your editor. An image 13 hours out of date produced believable output and proved nothing (§4.0)
- **`exec` doesn't fix shutdown** — making your program PID 1 delivers the signal; the program still has to handle it (§2.5)
- **`POSTGRES_USER` doesn't create a limited account** — it renames the superuser (§4.6)

---

## Part 1 — The mental model

Three ideas. Almost every confusing thing about Docker follows from them.

### 1.1 Image vs container

An **image** is a read-only filesystem template. Inert, like a class in code.

A **container** is a running instance of that image, with a thin writable layer on top. Like an
object.

```
image  (read-only, shared)     →     container 1  (its own writable layer)
                               →     container 2  (its own writable layer)
```

Consequences you will meet:

- **Ten containers from one image cost one copy of the image.** The read-only layers are shared.
- **The writable layer dies with the container.** `docker run --rm` deletes it on exit. Anything
  the process wrote is gone. This is a feature — it's what makes containers reproducible — and
  it's a catastrophe the first time it eats a database. (That's what volumes are for, §4.4.)
- **Rebuilding an image never changes a running container.** It's still running the old one.

#### The writable layer really is per-container — measured

Seed a database in one container, then run the app in another:

```
# runnable: docker run --rm sqlagent python -m experiments.sqlalchemy_1_4_vs_2_0.seed
  open            106
  in_progress      40
  closed           54
```

```
# runnable: docker run --rm sqlagent
sqlite3.OperationalError: no such table: issues
```

**The seed worked. The app still can't see it.** Container 1 wrote `issues.db` into *its own*
writable layer and `--rm` deleted the whole layer on exit. Container 2 started from the same
read-only image and got a fresh, empty writable layer of its own.

Do both in **one** container and it works:

```
# runnable: docker run --rm sqlagent sh -c 'python -m experiments...seed >/dev/null 2>&1 && python -m experiments...app'
38 open issues
```

This is the single most common source of *"but I already ran that command"* confusion. Each
`docker run` is a **new container**. Anything the previous one wrote is gone unless it went to
a volume or a real database elsewhere.

### 1.2 Layers — the idea everything hangs off

An image is not a folder. It's a **stack of read-only layers**, each one the filesystem diff
produced by a single build instruction.

**The analogy: it's git.** A commit isn't a copy of your whole repo — it's a diff from the
previous commit, chained to a parent, identified by a SHA. A layer is exactly that, for a
filesystem.

Here is the actual layer stack of `python:3.11-slim`, recovered from the image itself and read
bottom-up:

```
# runnable: docker history 90744cff8f32
SIZE      CREATED BY
109MB     # debian.sh --arch 'arm64' out/ 'trixie' ...     ← bare Debian
0B        ENV PATH=/usr/local/bin:/usr/local/sbin:...
0B        ENV LANG=C.UTF-8
4.99MB    RUN apt-get update; apt-get install ...
0B        ENV GPG_KEY=A035C8C19219BA821ECEA86B64E628F8...
0B        ENV PYTHON_VERSION=3.11.15
0B        ENV PYTHON_SHA256=272179ddd9a2e41a0fc8e42e33...
52.1MB    RUN ... download, compile and install Python
16.4kB    RUN ... symlinks for idle3, pydoc3, python3
0B        CMD ["python3"]
```

That is the Dockerfile someone else wrote, reconstructed from the image. **Every image you
ever pull can be read this way.**

Two things to notice:

**`ENV` and `CMD` produce 0B.** They change *metadata*, not files. That's why `docker image
inspect` reports 4 filesystem layers while `history` shows 10 entries — six of them touched no
files at all.

**Layers are additive.** Deleting a file in a *later* layer doesn't reclaim the space. The file
is still in the earlier layer, merely hidden by a whiteout marker. This is why *"I `rm`'d the
build tools, why is my image still 1.2GB?"* is a FAQ, and it's the entire reason multi-stage
builds exist (§3.3).

> **A quirk on your Docker version:** `docker history python:3.11-slim` fails with *"No such
> image"*. You have to pass the image **ID**: `docker history 90744cff8f32`. Get IDs from
> `docker images`.

### 1.3 The layer cache

On rebuild, Docker walks your instructions top to bottom asking, at each one, *did anything
about this step change?* While the answer is no it reuses the cached layer — instantly. **The
first time the answer is yes, that layer is rebuilt and every layer below it is rebuilt too,
unconditionally.**

Again it's git: amend a commit halfway through history and every commit after it gets a new
SHA, because each is defined in terms of its parent.

**The rule that falls out:** order instructions from *least*-frequently-changed to
*most*-frequently-changed.

Your own build proves it. After editing one source file:

```
# runnable: docker build -t sqlagent .
#7 [3/5] COPY requirements.txt .          CACHED
#8 [4/5] RUN pip install -r requirements  CACHED     ← the expensive step, untouched
#9 [5/5] COPY . .                         DONE 0.1s  ← rebuilt, because source changed
```

`pip install` survived because it sits **above** the source copy. Swap the two blocks and step
`#8` reads `4.3s` instead of `CACHED` — on every build, forever, for every one-character edit.

That's drill question 1, answered from measurement rather than memory.

### 1.4 Build context — the part nobody explains

When you run `docker build .`, the CLI **tarballs the directory you pointed at and ships the
whole thing to the Docker daemon** before a single instruction runs. That directory is the
*build context*.

Measured on this repo:

```
# runnable: docker build -t sqlagent .
#5 [internal] load build context
#5 transferring context: 13.51MB          ← before .dockerignore existed
```

```
#5 transferring context: 1.53kB           ← after
```

13.51MB was `.venv` (12M) + `.git` (1.5M) + everything else. This explains three things:

- **A build can be slow before it appears to start.** It's uploading your virtualenv.
- **You cannot `COPY` a file from outside the context.** As far as the daemon is concerned
  there is no outside — it only ever received the tarball.
- **`.dockerignore` is not cosmetic.** It's what keeps your virtualenv, your git history and
  your secrets out of the image and off the wire.

#### Two programs, not one — and why "not found" is literally true

Consider a single line added to `.dockerignore`:

```
*.txt
```

The build then failed at line 5 of the Dockerfile:

```
# runnable: docker build -t sqlagent .
#6 [3/5] COPY requirements.txt .
#6 ERROR: failed to calculate checksum of ref ...: "/requirements.txt": not found
```

The file was **right there on disk.** `ls` found it. Docker said it didn't exist. Resolving
that contradiction is the whole build-context model:

```
1. the docker CLI reads .dockerignore              ← on your Mac
2. the CLI walks your directory, SKIPS matches,
   and tars up whatever survives                   ← the filter happens HERE
3. the CLI ships that tarball to the daemon        ← "transferring context: 1.44kB"
4. the daemon runs your instructions, incl. COPY   ← inside the Linux VM
```

`COPY` executes at **step 4**, inside the daemon. `requirements.txt` was filtered out at step 2
and **never crossed**. The daemon isn't refusing to copy it — it has no idea the file exists.
So the correct mental model is not *"`.dockerignore` means don't copy this"*:

> **`.dockerignore` means this file does not exist, as far as the build is concerned.**

Same reason you can't `COPY ../something` from outside the context. There is no outside; the
daemon only ever received a tarball.

**Read the whole output, not the last line.** BuildKit said so explicitly, above the error,
where most people never look:

```
1 warning found:
 - CopyIgnoredFile: Attempting to Copy file "requirements.txt" that is excluded by
   .dockerignore (line 5)
```

Note also *where* it surfaced: at `COPY` on line 5, because that's the first instruction that
needed the file. Had it only been used by `pip install` on line 7, the error would have been
far stranger.

#### `.dockerignore` is not `.gitignore` — a trap you already hit

They look identical and they match differently:

| | slash-less pattern like `__pycache__` |
|---|---|
| `.gitignore` | matches **at any depth** — one line covers the whole tree |
| `.dockerignore` | matched against the **full path from the context root** — catches only a **top-level** one |

So `__pycache__/` in a `.dockerignore` silently misses
`experiments/sqlalchemy_1_4_vs_2_0/__pycache__`. You need the explicit glob:

```
**/__pycache__
```

Confirmed by looking inside the image:

```
# runnable: docker run --rm sqlagent ls -a /app/experiments/sqlalchemy_1_4_vs_2_0
__pycache__      ← still there, with the bare pattern
```

#### Why `.venv` mattered more than the megabytes

Your `.venv` holds files like:

```
# runnable: find .venv -name "*.so" -path "*sqlalchemy*"
.venv/lib/python3.11/site-packages/sqlalchemy/cprocessors.cpython-311-darwin.so
```

**`darwin` = macOS.** Compiled binaries for the wrong operating system entirely, placed
exactly where the container's Python looks first. Not wasted space — *actively broken files*.
Your container only works because `pip install` put correct Linux copies in `/usr/local/lib`.

And `.git` is the security one: git history contains **every file ever committed**, including
anything you committed and later deleted. Ship the history and any deleted credential ships
with it.

---

## Part 2 — The instructions, walked through this repo's Dockerfile

The file:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "experiments.sqlalchemy_1_4_vs_2_0.app"]
```

Six instructions. That's most of the vocabulary.

### 2.1 `FROM` — and why it was worth arguing about

Every image starts from another image. This one line decided **87% of your final image size**.

| | disk usage | download size |
|---|---|---|
| `python:3.11` | 1.62 GB | 416 MB |
| `python:3.11-slim` | **214 MB** | **48 MB** |

```
# runnable: docker images python
```

7.6× on disk, 8.7× on the wire — and the wire cost is paid on *every* CI run and every deploy,
forever.

**Two columns, two different costs.** *Content size* is the compressed layers crossing the
network. *Disk usage* is uncompressed, sitting on your 16GB Mac and the lab PC. You pay both.

#### The three candidates

| Base | Size | What you get |
|---|---|---|
| `python:3.11` | ~1.6GB | Debian + Python + gcc, make, git, headers |
| `python:3.11-slim` | ~214MB | Debian + Python. No compiler, no docs |
| `python:3.11-alpine` | ~50MB | Alpine Linux + Python. Smallest, and a trap |

The instinct *"take the big one, it has everything"* is the one to kill. Everything you don't
need isn't free: you pay in size, in pull time on every build, and in **attack surface** — a
full compiler toolchain in a production image is a set of tools an attacker gets for free if
they ever get a shell.

#### Wheels — the concept that decides this

Some Python packages are pure Python. Many aren't. SQLAlchemy isn't:

```
# runnable: find .venv -name "*.so" -path "*sqlalchemy*"
cimmutabledict.cpython-311-darwin.so
cprocessors.cpython-311-darwin.so
cresultproxy.cpython-311-darwin.so
```

`.so` = shared object = compiled C. Someone ran a **C compiler** to produce those. Not you —
your install took seconds. So where did the compile happen?

**Two ways a Python package ships:**

- **sdist** (`.tar.gz`) — raw source. pip must compile the C parts *on your machine, at install
  time*. Needs gcc, make, and Python headers. Slow, and fails if any are missing.
- **wheel** (`.whl`) — **prebuilt**. The maintainers compiled it ahead of time and uploaded the
  result. Install = download, unzip, copy. No compiler.

Compiled code isn't portable across OS, CPU architecture, or Python version — so maintainers
build **one wheel per combination**:

```
# runnable: curl -s https://pypi.org/pypi/SQLAlchemy/1.4.52/json | python3 -c "
#   import json,sys
#   n=[u['filename'] for u in json.load(sys.stdin)['urls']]
#   print('total    ', len(n))
#   print('wheels   ', sum(x.endswith('.whl') for x in n))
#   print('sdists   ', sum(x.endswith('.tar.gz') for x in n))
#   print('musllinux', sum('musllinux' in x for x in n))"
total     46
wheels    45
sdists    1
musllinux 0
```

#### Reading a wheel filename

```
SQLAlchemy - 1.4.52 - cp311 - cp311 - manylinux_2_17_aarch64 . manylinux2014_aarch64 . whl
    │          │        │       │              │
  name     version   Python   C ABI      OS + CPU architecture
                      3.11
```

pip inspects your interpreter, OS and CPU and picks the wheel whose tags match. **No match →
falls back to the sdist → needs a compiler.**

#### Which is why Alpine is a trap

- **`manylinux`** means "built against **glibc**", the C library Debian/Ubuntu/RedHat use.
- **Alpine uses musl**, a different C library. No tag matches, pip falls back to source, and
  Alpine ships no gcc either. Your 50MB base costs you a build failure.
- **`python:3.11-slim` is Debian** → glibc → the wheel matches → no compiler needed.

**But coverage is a per-package fact, not a per-project one.** The count above says SQLAlchemy
1.4.52 publishes **`musllinux 0`** — not one musl wheel, for any Python version or CPU —
while `greenlet`, SQLAlchemy's own dependency, *does* publish musllinux wheels (visible in
`uv.lock`). Every dependency independently decides which platforms it builds for, and **one
holdout puts you back on compile-from-source.** Adding a package in Phase 1 can silently break
an Alpine build that worked yesterday. That's why "smallest base image" is a bad default —
you're betting on the platform coverage of every package you will ever add.

#### The build confirmed all of it

```
# runnable: docker build -t sqlagent .
Downloading SQLAlchemy-1.4.52-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
Downloading greenlet-3.5.3-cp311-cp311-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl
Successfully installed greenlet-3.5.3 sqlalchemy-1.4.52
#8 DONE 4.3s
```

The exact wheel predicted from PyPI. No compiler ran. 4.3 seconds.

#### One more thing `FROM` decides

Your Docker Desktop runs a Linux VM on arm64:

```
# runnable: docker info
os=linux  arch=aarch64
```

The lab PC is **amd64**. Your images are genuinely Linux, but the wrong architecture for the
lab. The concepts transfer intact; the built image does not. Expect to rebuild there.

### 2.2 `WORKDIR`

Two jobs: it's **`cd` for every instruction below it**, and it **creates the directory** if it
doesn't exist — no `mkdir -p` needed.

Without it you're in `/`, scattering your app among `/bin`, `/etc`, `/usr`. It also persists at
runtime: `docker exec` into a running container and that's where you land.

`/app` is convention. Nothing magic about the name.

### 2.3 `COPY` — and why `COPY` and not `ADD`

Both instructions use the same shape: **source → destination**.

```dockerfile
COPY <src> <dest>
ADD  <src> <dest>
```

For `COPY`, sources are relative to the build context; destinations relative to `WORKDIR`.
So in your file, the second `.` in `COPY . .` means `/app/`.

**`ADD` can do two extra things. That is the whole difference.**

| Extra | Example | What actually happens | Why it bites |
|---|---|---|---|
| Tar auto-extraction | `ADD app.tar.gz /app/` | unpacks into `/app/` instead of leaving a `.tar.gz` file | same instruction, different result depending on the filename — easy to miss |
| URL fetch | `ADD https://example.com/x.whl /tmp/` | downloads during **build** | build silently needs the network; the URL can change; not a file you control in the context |

Local file vs URL still look like `src dest` — the src just happens to be a URL:

```dockerfile
COPY requirements.txt .                      # src in context → dest in image
ADD  https://example.com/thing.whl /tmp/     # src is a URL → Docker fetches it
```

What each allows:

| | `COPY` | `ADD` |
|---|---|---|
| Local path in the build context | yes | yes |
| `http://` / `https://` URL | **no** | yes (downloads) |
| Local `.tar` / `.tar.gz` | copies as a file | may **extract** into dest |

**Use `COPY` unless you specifically want tar auto-extraction.** Almost never want URL fetch
via `ADD` — download in an explicit `RUN`, or put the file in the context. If asked the
difference and you say "basically the same," you've said you've only ever copied Dockerfiles
off Stack Overflow.

**The two-stage copy in your file is the whole cache lesson** — two `COPY` instructions, not
a multi-stage build (§3.3). Order least-changed first:

```dockerfile
COPY requirements.txt .            # changes ~monthly
RUN pip install -r requirements.txt
COPY . .                           # changes every commit
```

One fat `COPY . .` *before* `pip install` would bust the install layer on every source edit.

#### The last layer to touch a path wins — measured

`COPY` **preserves the source file's mode**, and layers apply in order. Put those two facts
together and this Dockerfile is broken in a way that looks impossible:

```dockerfile
COPY entrypoint.sh .        # /app/entrypoint.sh, mode 644 (as it is on macOS)
RUN chmod +x entrypoint.sh  # now 755  ✓
COPY . .                    # copies entrypoint.sh AGAIN from the host — back to 644  ✗
```

```
# runnable: docker run --rm --entrypoint ls sqlagent -l /app/entrypoint.sh
-rw-r--r-- 1 root root 102 /app/entrypoint.sh      ← the chmod ran, then was overwritten
```

The container would have died at startup with `permission denied` while a `chmod +x` sat
plainly in the Dockerfile two lines above. **A later `COPY` silently reverted an earlier
`RUN`.**

Four ways out, all defensible:

1. `chmod +x` on the host and drop the `RUN` — git records the executable bit, so a clone on
   the lab machine gets it too
2. move the `chmod` *after* the wide `COPY . .`
3. `COPY --chmod=755 entrypoint.sh .` placed after `COPY . .` — one instruction instead of two
4. keep the dedicated copy, but ensure nothing later overwrites the path

Option 3, verified:

```
# runnable: docker run --rm --entrypoint ls sqlagent -l /app/entrypoint.sh
-rwxr-xr-x 1 root root 102 /app/entrypoint.sh
```

**The general rule:** when a file appears in more than one `COPY`, only the last one matters.
Any `RUN` that modified it in between is discarded without a word.

### 2.4 `RUN`

Executes a command *at build time*, in a new layer; whatever changed on disk is kept.

**Each `RUN` is a separate layer** — which is why cleanup must happen in the *same* `RUN` as
the thing it cleans (§3.2). Split them and, by §1.2, the bytes stay in the first layer and your
cleanup provably did nothing.

### 2.5 `CMD` vs `ENTRYPOINT`

You only need your own image for this section. Ignore other products until the footnote
at the end.

Both answer: **when the container starts, what process starts?**

The difference is only what happens when you type something *after* the image name:

```bash
docker run --rm sqlagent ls -a /app
#                         ^^^^^^^^^^ extra args
```

| | Plain English | Extra args do this |
|---|---|---|
| **`CMD`** | Default: run this if nobody says otherwise | **Replace** the whole command |
| **`ENTRYPOINT`** | Always run this program | **Append** as arguments to that program |

Your image uses **only `CMD`** (no `ENTRYPOINT`). Measured:

```
# runnable: docker run --rm sqlagent echo "this replaced the CMD"
this replaced the CMD
```

Python never ran. Extra args became the command. Same reason `ls -a /app` worked.

Your config is just:

```
Entrypoint: []
Cmd: [python, -m, experiments.sqlalchemy_1_4_vs_2_0.app]
```

So: no fixed program. Whatever you put after `sqlagent` *is* the program.

If you later add an entrypoint, the usual good shape is:

```dockerfile
ENTRYPOINT ["python", "-m", "experiments.sqlalchemy_1_4_vs_2_0.app"]
CMD []
```

Then extra args cannot accidentally replace the app — they become args *to* Python. To get a
shell you'd need the escape hatch: `docker run --entrypoint bash sqlagent`.

#### Where it bites (with only `CMD`, like yours)

Someone passes an argument in production → your app never starts → silent replace. You already
saw that locally with `echo` and `ls`.

#### Shell form vs exec form — "PID 1"

**PID** = process ID. **PID 1** = first process in the container. `docker stop` signals **only
PID 1**.

```dockerfile
CMD ["python", "-m", "myapp"]     # exec form — use this (you already do)
CMD python -m myapp               # shell form — avoid
```

Exec form:

```
PID 1  python …     ← hears "please stop"
```

Shell form (Docker wraps in `/bin/sh -c`):

```
PID 1  sh           ← hears "please stop"
PID 2  python …     ← often never hears it → ~10s then force kill
```

Use the JSON array so your app *is* PID 1.

#### A related trap (not about ENTRYPOINT)

```dockerfile
CMD ["python", "-m", "app.py"]    # wrong: -m wants a module path, not a filename
```

Built green three times. Failed only at `docker run`. `CMD` is metadata — build never runs it.
Green build ≠ works. Same shape as a passing 1.4 suite saying nothing about 2.0.

Correct line:

```dockerfile
CMD ["python", "-m", "experiments.sqlalchemy_1_4_vs_2_0.app"]
```

#### Footnote — PID 1, and a correction. Skip until you run a server.

**Not needed for Days 4–5.** `app.py` is a batch script: it runs, prints, exits, and nothing
ever asks it to stop. This becomes real in Phase 1, with a long-lived server that has open
connections when a deploy tells it to shut down. It is here because the usual one-line
explanation of it is wrong.

The common claim is *"use `exec` so your process becomes PID 1 and receives the stop signal."*
Measured on this image, `docker stop`:

| case | PID 1 | stop took | exit code |
|---|---|---|---|
| `sh` stays PID 1, python is its child | `sh` | 1.13s | **137** (SIGKILL) |
| `exec` → python is PID 1, no handler | `python` | 1.13s | **137** (SIGKILL) |
| python is PID 1 **and handles SIGTERM** | `python` | 0.12s | **0** (clean) |

**`exec` changed nothing.** Rows 1 and 2 are identical. Only installing a handler helped.

**Why:** the kernel special-cases PID 1. Any other process receiving a signal it hasn't handled
gets the *default* action — SIGTERM terminates it. **PID 1 gets no default actions**; an
unhandled signal is discarded. So a process at PID 1 that never installed a SIGTERM handler
ignores the polite request, and Docker kills it when the grace period runs out.

Check the PIDs yourself:

```
# runnable: docker run --rm sqlagent python -c "import os; print(os.getpid())"
1
# runnable: docker run --rm sqlagent sh -c 'echo "sh pid = $$"; python -c "import os; print(os.getpid())"'
sh pid = 1
python pid = 7
```

The famous "ten second hang" is the grace period expiring. It didn't reproduce here at first
because **this Docker sets the grace period to 1 second, not the documented 10**:

```
# runnable: docker inspect -f '{{.Config.StopTimeout}}' <container>
1
# runnable: docker stop --timeout 10 <container>
stop took 10.14s, exit=137
```

**This is what `tini` is for.** Product images — n8n on this machine sets
`ENTRYPOINT ["tini","--","/docker-entrypoint.sh"]` — put a ~10KB init at PID 1 whose only jobs
are to **forward signals** to the real process and to **reap zombies** (when a child exits,
something must collect its exit status or it lingers as a defunct entry; normally the system's
init does this, and a container has no init). Rather than demand every app implement signal
handling correctly, they put one small program in front that already does. Docker ships this:
**`docker run --init`**.

So the honest version of the `exec` rule: **`exec` gets the shell out of the way** so it isn't a
useless middleman holding PID 1. Whether shutdown is *graceful* then depends on your app
handling SIGTERM, or on an init like tini doing it for you.

---

## Part 3 — What your image still gets wrong

Three real problems, deliberately left in so you fix them knowing why.

### 3.1 Everything runs as root

```
# runnable: docker run --rm sqlagent id
uid=0(root) gid=0(root) groups=0(root)
```

**Nobody chose that.** No instruction asked for root — it's the default when you don't say
otherwise. pip says so during the build, in a warning that is easy to scroll past.

Why it matters: a container is **not** a security boundary the way a VM is — processes inside
share the host kernel. If an attacker gets code execution in your app, uid 0 turns several
container-escape techniques from "impossible" into "worth trying." And root inside means
root-owned files anywhere you've bind-mounted a host directory.

The fix is two ideas: **create an unprivileged user, then switch to it** with `USER`. Three
things bite people:

- **Order matters.** Files copied *before* the switch are owned by root. If the app must write
  to them, it can't.
- **Ports below 1024 need root** to bind. Nothing here does, but a web server on port 80 will
  surprise you. Listen high, map it.
- **Bind mounts don't care about your container's user.** Host files keep host ownership, so
  the uid inside must line up with the uid outside or you get permission errors that look
  insane.

**Verify with `docker run --rm sqlagent id` that the switch actually took effect** — don't
assume the instruction worked.

#### Done — and the part that bites

```
# runnable: docker run --rm --entrypoint id sqlagent
uid=10001(app) gid=999(app) groups=999(app)
```

A fixed, high uid (10001) rather than whatever `useradd` picks: fixed so bind-mount ownership
is predictable across machines, high so it cannot collide with a real host user.

**`COPY --chown` was not enough.** It sets the owner of the files copied in and does nothing to
the *directory* they land in, which `WORKDIR` created as root. Reading worked. Creating a new
file did not:

```
# runnable: docker run --rm sqlagent          (before the extra chown)
sqlite3.OperationalError: unable to open database file
```

Every file in `/app` was correctly owned and readable, and the app still could not write —
because writing a *new* file needs permission on the **directory**, not on the files. One extra
`chown app:app /app` fixes it.

Worth generalising: **file ownership and directory ownership are different questions**, and
container permission bugs are usually the second one.

### 3.2 Caches you never asked to ship

Package managers cache downloads, and the cache lands **inside the layer**. By §1.2, deleting
it later hides it without reclaiming a byte.

```
# runnable: docker run --rm sqlagent sh -c 'du -sh /root/.cache'
3.3M	/root/.cache
```

3.3MB of wheel archives that will never be read again — pip already unpacked them into
`site-packages`.

**Be honest about scale: 3.3MB of a 260MB image is ~1%.** Not worth your attention today. The
*mechanism* is the point:

- **pip** — `--no-cache-dir`, or the `PIP_NO_CACHE_DIR` env var
- **apt** — leaves package lists in `/var/lib/apt/lists/`, cleaned **in the same `RUN`**,
  because a separate `RUN` is a separate layer and the bytes stay in the first one

Phase 1 is where it stops being academic: torch and sentence-transformers wheels run to
gigabytes, and that cache would ship in every image and cross the wire on every CI pull.

#### Done

`pip install --no-cache-dir`. By the time it was applied, adding `psycopg2-binary` had already
grown the cache from 3.3MB to 9.1MB:

```
# runnable: docker run --rm --entrypoint sh sqlagent -c 'du -sh /root/.cache'
(nothing listed — the directory is never created)

# runnable: docker images sqlagent --format '{{.Size}}'
295MB  ->  276MB
```

Note the flag *prevents the cache being written* rather than deleting it afterwards. Deleting
it in a later layer would shrink nothing — layers are additive (§1.2), so the bytes stay in the
layer that created them.

### 3.3 No multi-stage build

§1.2 said deleting a file in a later layer doesn't shrink the image. So if you need gcc at build
time you ship it forever — which is the honest argument for grabbing the fat base image.

**Multi-stage builds dissolve that tradeoff.** A Dockerfile may contain more than one `FROM`.
Each starts a fresh stage with its own layer stack. **Only the final stage ships**; everything
else is scaffolding, discarded.

The shape: **build in a fat stage, copy the finished artifacts into a slim stage.** `COPY` can
pull from a named earlier stage instead of from your machine — that's the hinge. The compiler,
headers and source tarballs all exist during the build and none reach the final image, because
they were never in the *final stage's* layers.

You didn't need it today — SQLAlchemy shipped a wheel. You'll need it the first time a
dependency doesn't, and then the choice isn't "slim or safe," it's both.

**Ask of any Dockerfile:** *which of these files does the running process actually need?*
Usually the installed packages and your source, nothing else. Every byte beyond that is
scaffolding someone forgot to leave behind.

### 3.4 The image is not self-sufficient — and the first "working" one was a fluke

The most instructive failure in this build, and nothing was deliberately broken to produce it.

```
# runnable: docker run --rm sqlagent
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: issues
```

`app.py` never creates its own tables — it says so in its own docstring (*"seed it first"*).
`seed.py` is a separate entry point that does `drop_all` + `create_all` + populate.

So compare the two builds:

| build | `issues.db` | result |
|---|---|---|
| before `.dockerignore` existed | copied in from the Mac | **"worked"** — on a stale database that happened to be lying around |
| after `*.db` was excluded | absent | `no such table: issues` |

**Excluding `*.db` was correct.** A database file has no business being baked into an image:
it's data, not code; it goes stale the moment anyone writes to it; and it makes the image
change every time you re-seed. What the exclusion did was *expose* that the image had never
been self-sufficient — it had been silently depending on a build artifact from the host.

**And it went unnoticed for a full build cycle**, because after adding `.dockerignore` the only
thing anyone ran was `ls`. The image was declared working on the strength of a green build and
a directory listing. That is the same trap as §2.5's `CMD` typo and the same trap as
`MIGRATION-2.0.md`'s green 1.4 test suite. Three times, one lesson:

> **Verify the thing you actually care about, not the thing that's easy to check.**

The fix is a real design decision, not a typo:

- **Ship the seeded `.db` in the image** — works immediately, bakes data into code, and dies
  the moment the database moves to Postgres on Day 6.
- **Seed at container start** — the image holds only code, data is created fresh at runtime.
  Survives Day 6, because "start the app" becomes "connect, ensure schema, go" either way.

Only one of those is still a valid design when the database lives in another container.

#### The seductive third option, and why it is the first one wearing a hat

There is an obvious-looking middle road: seed at **build** time with a `RUN`.

```dockerfile
RUN python -m experiments.sqlalchemy_1_4_vs_2_0.seed   # tested, works
```

It works. The app runs, 38 open issues, no error. And it is option A, because `RUN` keeps its
filesystem changes as a layer:

```
# runnable: docker run --rm sqlagent-opt3 ls -l /app/issues.db
-rw-r--r-- 1 root root 167936 /app/issues.db     ← the database is IN the image
```

Which produces a thing that behaves like a database and is actually a **fixture**:

```
# every container starts from the same frozen snapshot
container 1 sees 200 issues
container 2 sees 200 issues

# container A inserts a row
after insert, this container sees 201
# container B, moments later
a new container sees 200
```

**The write vanished.** It landed in container A's writable layer, which `--rm` deleted (§1.1).
Nothing raised an error. Data silently fails to persist — the kind of thing found in production
rather than in testing.

#### What was actually built (option B)

An `ENTRYPOINT` script that seeds, then hands off:

```sh
#!/bin/sh
set -e
python -m experiments.sqlalchemy_1_4_vs_2_0.seed
exec "$@"
```

`set -e` stops the script if the seed fails, rather than launching an app at a half-built
database. `exec "$@"` replaces the shell with whatever `CMD` supplied — so `CMD` keeps working
as an overridable default instead of being hardcoded away.

Verified four ways. Same image, four different "who is in charge" answers:

```
# runnable: docker run --rm sqlagent
38 open issues

# runnable: docker run --rm sqlagent ls /app          ← CMD overridden, proves exec "$@"
README.md  entrypoint.sh  experiments  issues.db  ...

# runnable: docker run --rm --entrypoint sh sqlagent -c 'ls /app/issues.db'
ls: cannot access '/app/issues.db': No such file or directory     ← NOT in the image

# runnable: docker run --rm sqlagent sh -c 'ls -l /app/issues.db'
-rw-r--r-- 1 root root 167936 /app/issues.db                      ← created at runtime
```

Your wiring:

```
ENTRYPOINT  ./entrypoint.sh          # always starts (unless --entrypoint)
CMD         python -m …app           # default → becomes "$@"
```

**1. `docker run --rm sqlagent`** — nothing after the image name, so Docker uses `CMD`.

```
entrypoint.sh runs
  → seed (creates issues.db in THIS container)
  → exec python -m …app
→ 38 open issues
```

**2. `docker run --rm sqlagent ls /app`** — the override test.

Args after `sqlagent` **replace `CMD`**, not the entrypoint. So `"$@"` is `ls /app`, not Python:

```
entrypoint.sh still runs
  → seed still runs
  → exec ls /app          ← NOT the app
→ file listing
```

If the script had hardcoded `python -m …app` instead of `exec "$@"`, this would still print
"38 open issues." The listing is the proof that handoff works.

**3 and 4 are about where `issues.db` lives** — not about override.

**3. `docker run --rm --entrypoint sh sqlagent -c 'ls /app/issues.db'`**

`--entrypoint sh` **skips your script entirely**. No seed. Just a shell looking at image layers:

```
no entrypoint.sh → no seed → issues.db missing
→ "No such file or directory"
```

So the DB is **not baked into the image** (`.dockerignore` kept the host copy out; nothing
seeded at build). That is the option-B property.

**4. `docker run --rm sqlagent sh -c 'ls -l /app/issues.db'`**

No `--entrypoint` → your script runs. `CMD` is replaced by `sh -c '…'`:

```
entrypoint.sh runs
  → seed creates issues.db
  → exec sh -c 'ls -l …'
→ file exists (167936 bytes)
```

Created **at runtime**, in that container’s writable layer. `--rm` deletes the container → that
copy dies. Next `docker run` seeds again.

One table for the four:

| Command | Runs `entrypoint.sh`? | Seeds? | Final process |
|---|---|---|---|
| `sqlagent` | yes | yes | app |
| `sqlagent ls /app` | yes | yes | `ls` |
| `--entrypoint sh …` | **no** | **no** | `sh` (image only) |
| `sqlagent sh -c 'ls …db'` | yes | yes | `sh` listing the new db |

**2** proves: entrypoint stays, `CMD` is swappable via `exec "$@"`.  
**3 vs 4** prove: DB is created when the script runs, not shipped in the image.

The last two are the point of the whole exercise: **the image contains code, the container
contains data.** That property is what survives Day 6, when the database moves to Postgres and
"seed at startup" becomes "connect, ensure schema, go."

Two consequences worth knowing:

- **Every `docker run` now seeds**, including `docker run sqlagent ls`. Harmless here — fast,
  and the data is disposable — but production entrypoints usually guard it with "only seed if
  the schema is missing."
- **`--entrypoint` is the escape hatch.** `docker run --entrypoint ls sqlagent /app` skips the
  script entirely. Needing it is the tell that you understand `ENTRYPOINT` (§2.5).

---

## Part 4 — more than one container

Moved to **[`COMPOSE-STUDY.md`](COMPOSE-STUDY.md)** — this file had reached ~1350 lines, and
running two containers is a different subject from building one image.

That file keeps the §4 numbering, so every `§4.x` reference below still resolves:

| | |
|---|---|
| §4.0 | Compose does not replace the Dockerfile — and the same thing done by hand |
| §4.1 | Networking: why `localhost` is the container itself, and why names beat IPs |
| §4.2 | `depends_on` does not mean "ready" |
| §4.3 | Why Postgres for the exercise |
| §4.4 | Volumes and persistence |
| §4.5 | GPU in a container (Day 7) |
| §4.6 | `POSTGRES_USER` does not give you a limited account |

## Everything measured on this project

| Measurement | Value | Command |
|---|---|---|
| Full vs slim base, disk | 1.62GB vs **214MB** | `docker images python` |
| Full vs slim base, download | 416MB vs **48MB** | `docker images python` |
| Your image | 260MB disk / 58.1MB content | `docker images sqlagent` |
| Build context, no `.dockerignore` | **13.51MB** | `docker build` → `transferring context` |
| Build context, with it | **1.53kB** | same line, after the file existed |
| pip cache shipped in the image | 3.3MB | `docker run --rm sqlagent sh -c 'du -sh /root/.cache'` |
| Process user | uid=0 (root) | `docker run --rm sqlagent id` |
| SQLAlchemy 1.4.52 wheels / sdists | 45 / 1 | the PyPI one-liner in §2.1 |
| …of those, `musllinux` | **0** | same one-liner |
| Dependency install, no compiler | 4.3s | `docker build` → step `[4/5]` |
| Docker Desktop VM | linux / aarch64 | `docker info` |

Layer sizes in your own image, read bottom-up:

```
# runnable: docker history <image-id>
109MB     Debian base
 52.1MB   Python 3.11.15, compiled by the image maintainers
  4.99MB  apt libraries
 34.6MB   RUN pip install -r requirements.txt     ← yours
 12.3kB   COPY requirements.txt .                 ← yours
541kB     COPY . .                                ← yours
      0B  CMD [...]                               ← metadata only
```

**Your three instructions account for ~35MB of a 260MB image.** `FROM` decided the other 87%.
That is why it was worth twenty minutes of argument.

---

## The drill list

Answer cold, no notes, or the phase isn't done. Questions 1–5 are from
[`PHASE-0.md`](PHASE-0.md); 6–11 came out of building the thing.

1. *"I moved `COPY . .` above `COPY requirements.txt`. Your build got slow. Why?"*
2. *"Your container can't reach Postgres. Walk me through how you'd diagnose it."*
3. *"What's the difference between `CMD` and `ENTRYPOINT`, and when does it bite you?"*
4. *"`depends_on` says Postgres starts first, but your app still crashes on startup. Why?"*
5. *"How do you know your model is on the GPU and not silently running on CPU?"*
6. *"Why is `.dockerignore` not just a tidiness thing?"* — two answers, and the megabytes are
   the weaker one.
7. *"You deleted a 500MB file in a later layer. Why is the image still huge?"*
8. *"Your build succeeded and the container crashes instantly. How is that possible?"*
9. *"Why is Alpine not automatically the right choice for a Python image?"*
10. *"Your `.dockerignore` has `__pycache__/` and they're still in the image. Why?"*
11. *"Who is your container running as, and why should you care?"*
12. *"`COPY requirements.txt .` says the file isn't found. `ls` says it's there. Explain."*
13. *"You ran the seed command in a container. The next container says the table doesn't exist.
    Why?"*
14. *"Your container worked last week and the only thing you changed was adding a
    `.dockerignore`. What kind of dependency did you just discover?"*

**Every one is a "why," not a "how."** Deliberate — anyone can `docker run`. These are built so
that copied knowledge fails them.

---

## The official docs — read these, not blog posts

Blog posts teach you to copy. The docs teach you the model.

- Dockerfile reference — https://docs.docker.com/reference/dockerfile/
- Build cache — https://docs.docker.com/build/cache/
- `.dockerignore` — https://docs.docker.com/build/concepts/context/#dockerignore-files
- Multi-stage builds — https://docs.docker.com/build/building/multi-stage/
- Networking overview — https://docs.docker.com/network/
- Volumes — https://docs.docker.com/storage/volumes/
- Compose file reference — https://docs.docker.com/reference/compose-file/
- NVIDIA Container Toolkit — https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/
- Python packaging: wheels — https://packaging.python.org/en/latest/discussions/package-formats/
- manylinux — https://github.com/pypa/manylinux

**Read the Dockerfile reference top to bottom once.** Shorter than you think, and the single
highest-leverage hour in Part C.
