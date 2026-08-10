# Docker — study notes

Part of [`sqlalchemy-upgrade-agent`](README.md); see [`PHASE-0.md`](PHASE-0.md) for where this
sits in the plan.

Reading material for Phase 0 Part C (Days 4–7). **Mobile-friendly: read it away from the
keyboard.** Every number in here was measured on this repo, and the command that produces it
is given — so you can check it rather than believe it.

## How this doc is split, and why

**Part 1–3 cover what you have already built.** They use your own `Dockerfile`, your own build
output, and your own image as the worked example. Nothing here is a snippet to copy — it's a
walkthrough of a file you wrote from an empty buffer on 2026-08-09.

**Part 4 covers what you have not built yet** — Compose, container networking, volumes, GPU.
Those are concepts only. **There is deliberately no `docker-compose.yml` in this file.** You
write that one from blank too, on Day 6. Reading a Compose file and writing one are different
skills and only the second survives an interview.

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

You watched this happen:

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

Injected failure, diagnosed 2026-08-10. A single line was added to `.dockerignore`:

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

You found this by looking, not by being told:

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

## Part 2 — The instructions, walked through your own file

This is what you wrote:

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

#### Your personal trap (not about ENTRYPOINT)

```dockerfile
CMD ["python", "-m", "app.py"]    # wrong: -m wants a module path, not a filename
```

Built green three times. Failed only at `docker run`. `CMD` is metadata — build never runs it.
Green build ≠ works. Same shape as a passing 1.4 suite saying nothing about 2.0.

Correct line (what you fixed to):

```dockerfile
CMD ["python", "-m", "experiments.sqlalchemy_1_4_vs_2_0.app"]
```

#### Footnote — PID 1, and a correction. Skip until you run a server.

**Not needed for Days 4–5.** `app.py` is a batch script: it runs, prints, exits, and nothing
ever asks it to stop. This becomes real in Phase 1, with a long-lived server that has open
connections when a deploy tells it to shut down. It is here because the common explanation of
it — including the one given in this session — is wrong.

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
otherwise. pip warned you during the build and you scrolled past it.

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

The most instructive bug of the session, and nobody injected it.

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

---

## Part 4 — Not built yet (Days 6–7)

Concepts only. **You write the Compose file from blank**, same rule as the Dockerfile.

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

---

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
