# Docker — study notes

Part of [`sqlalchemy-upgrade-agent`](README.md); see [`PHASE-0.md`](PHASE-0.md) for where
this sits in the plan.

Reading material for Phase 0 Part C (Days 4–7). **Mobile-friendly: read it away from the
keyboard.**

## What this doc deliberately does not contain

**There is no Dockerfile in here. There is no `docker-compose.yml` in here. There is no
snippet you can copy.** That is on purpose.

Reading a Dockerfile and writing one from an empty file are different skills, and only the
second one survives an interview. Your résumé already claims the second one. If a working
Dockerfile appears in this repo that you didn't write, Days 4–5 produce a container and
teach you nothing — which is exactly how the gap opened in the first place.

So: concepts here, plus the questions you must be able to answer cold. The file itself, you
write from blank, at the machine.

---

## 1. The one idea everything else hangs off: layers

A Docker image is not a folder. It's a **stack of read-only layers**, each one the
filesystem diff produced by a single build instruction. Stack them and you get the final
filesystem the container sees.

Two consequences, and they explain most of Docker's weirdness:

**Layers are cached.** On rebuild, Docker walks your instructions top to bottom and reuses
the cached layer for each one — until it hits a step whose inputs changed. From that point
down, **every remaining layer is rebuilt**, cache discarded.

**Layers are additive.** Deleting a file in a later layer doesn't reclaim the space — the
file is still sitting in the earlier layer, just hidden. This is why "I `rm`'d the build
tools, why is my image still 1.2GB?" is a FAQ, and why multi-stage builds exist.

### The question this makes answerable

> *"I moved the line that copies my source code above the line that installs dependencies.
> My builds got slow. Why?"*

Because your source code changes on every single commit, and your dependency list changes
once a month. Whichever one you copy **first** determines when the cache breaks. Copy the
source first and every edit to any file invalidates the dependency-install layer — so you
reinstall every package, every build, forever.

Copying the dependency manifest first, installing, *then* copying the source is therefore
**not a style convention.** It's the difference between a 3-second rebuild and a 3-minute
one. Ordering instructions from least-frequently-changed to most-frequently-changed is the
whole game.

**Study it by:** predicting, before you run it, which layers will be cached on your next
build. Then run it and check whether you were right. Being wrong is the point.

---

## 2. Build context — the thing nobody explains

When you build, the Docker CLI **tarballs the directory you point it at and ships the whole
thing to the Docker daemon** before a single instruction runs. That directory is the *build
context*.

This is why:
- a build can be mysteriously slow before it appears to start (it's uploading your
  `.venv/`, your `.git/`, your 200MB of SQLite files)
- you cannot copy a file from *outside* the context — there is no "outside" as far as the
  daemon is concerned
- `.dockerignore` matters. It's not cosmetic; it's what keeps your secrets, your virtualenv
  and your `.git` history out of the image and off the wire.

For this project specifically: your `.venv/` and `*.db` files have no business in an image.

---

## 3. `COPY` vs `ADD`

`COPY` copies files in. That's all it does, and that predictability is a feature.

`ADD` also copies files — but it will additionally auto-extract tar archives and fetch
remote URLs. Both behaviours are surprising, and the URL fetch means your build can silently
depend on the network.

**Rule: use `COPY` unless you specifically want tar auto-extraction.** If an interviewer
asks the difference and you say "they're basically the same," you've told them you've only
ever copied Dockerfiles from Stack Overflow.

---

## 4. `CMD` vs `ENTRYPOINT`

Both say what runs when the container starts. The difference is **what happens when someone
appends arguments to `docker run`.**

- `CMD` is a **default that gets replaced.** `docker run myimage some-other-command` throws
  your `CMD` away entirely.
- `ENTRYPOINT` is a **command that gets appended to.** Args you pass on the command line
  become args *to* the entrypoint, not a replacement for it.

Use them together and you get "this image always runs *this program*, and `CMD` supplies its
default arguments" — which is how well-behaved images behave.

### Where it bites

The image runs fine locally and then does nothing in production, because someone passed an
argument and silently replaced your `CMD`. Or: you set an `ENTRYPOINT` and now
`docker run myimage bash` doesn't give you a shell — it passes the string `bash` as an
argument to your entrypoint. (`--entrypoint` is the escape hatch. Knowing you need one is
the tell that you actually understand this.)

There's also a **shell form vs exec form** trap: written as a bare string, your command runs
under `/bin/sh -c`, which means your process is PID 2 and **does not receive the shutdown
signal.** Your container then takes 10 seconds to die every time, because Docker eventually
gives up and kills it. Written as a JSON array, your process is PID 1 and gets the signal.
This is a real production bug that people live with for years without understanding.

---

## 5. Networking — why the container can't reach anything

The default mental error is thinking the container shares your machine's network. It does
not. It gets its **own network namespace**: its own interfaces, its own `localhost`.

Three things fall directly out of that:

**`localhost` inside a container means the container itself.** Your app connecting to
`localhost:5432` to find Postgres is looking for Postgres *inside its own container*, and
there isn't one. This is the single most common Docker networking bug and you should expect
to hit it.

**Published ports (`-p 8000:8000`) are a hole you punch from the host into the container.**
They are for traffic coming from *outside*. Containers talking to *each other* don't need
them at all.

**On a user-defined network, containers find each other by service name via Docker's
embedded DNS.** So your app reaches the database at the hostname `db` (or whatever you named
the service) — not at an IP, not at `localhost`. The DNS is doing the work.

That's your Day 6 exercise: an app and Postgres on a compose network, and being able to
explain *how the app resolved the hostname.* If the answer isn't "Docker's embedded DNS
resolved the service name on the user-defined bridge network," you haven't got it yet.

---

## 6. `depends_on` does not mean "ready"

`depends_on` controls **start order**. It waits for the container to be *started* — not for
the process inside it to be *ready to accept connections*.

Postgres takes a few seconds to initialise. Your app container starts immediately, connects
instantly, gets refused, and crashes. Compose did exactly what you asked; you asked for the
wrong thing.

The real fixes: a **healthcheck** plus `depends_on: condition: service_healthy`, or — better
and the answer a senior engineer gives — **make the app retry its connection on startup**,
because in the real world the database can also go away *after* boot and a start-order
guarantee does nothing for you then.

**"`depends_on` says Postgres starts first, but my app still crashes on startup. Why?"** is
on your Phase 0 drill list. It's there because it separates people who ran `docker compose
up` from people who understand what it did.

---

## 7. Volumes and persistence

**A container's writable layer dies with the container.** Everything written inside it is
gone on `docker rm`. This is a feature — it's what makes containers reproducible — and it's
a catastrophe the first time it eats your database.

- **Named volumes** — Docker manages the storage. This is what you want for Postgres data.
- **Bind mounts** — a host directory mapped into the container. Great for live-editing
  source during development; a portability liability in production.

If your Postgres data lives in the container's writable layer, `docker compose down` deletes
your database. Understand which of the two you've configured *before* you learn this the
other way.

---

## 8. GPU in a container (Day 7)

The container needs the host's NVIDIA driver surfaced into it. That's what the **NVIDIA
Container Toolkit** does — it wires the device nodes and driver libraries through, so
`--gpus all` gives the container real access to the 3060.

The trap you must be able to detect: **your model loads, runs, produces correct output —
entirely on the CPU, at a tenth of the speed, and nothing errors.** Silent CPU fallback is
the norm, not the exception. So the check is never "did it work." The check is `nvidia-smi`
reporting the GPU *from inside the container*, and then your framework reporting that CUDA
is actually available to it.

That's why the Day 7 gate is worded as *"`docker run --gpus all ...` reports the 3060 from
inside a container"* rather than "the model ran."

---

## The drill list

These are from `PHASE-0.md`. You must answer them cold, with no notes, or the phase isn't
done. Read them on your phone; they're the whole point of this doc.

1. *"I moved `COPY . .` above `COPY requirements.txt`. Your build got slow. Why?"*
2. *"Your container can't reach Postgres. Walk me through how you'd diagnose it."*
3. *"What's the difference between `CMD` and `ENTRYPOINT`, and when does it bite you?"*
4. *"`depends_on` says Postgres starts first, but your app still crashes on startup. Why?"*
5. *"How do you know your model is on the GPU and not silently running on CPU?"*
6. *"Why is `.dockerignore` not just a tidiness thing?"*
7. *"You deleted a 500MB file in a later layer. Why is the image still huge?"*

Notice that **every one of them is a "why," not a "how."** That's deliberate. Anyone can
`docker run`. The questions are designed so that copied knowledge fails them.

---

## The official docs — read these, not blog posts

Blog posts teach you to copy. The docs teach you the model.

- Dockerfile reference — https://docs.docker.com/reference/dockerfile/
- Build cache — https://docs.docker.com/build/cache/
- Networking overview — https://docs.docker.com/network/
- Volumes — https://docs.docker.com/storage/volumes/
- Compose file reference — https://docs.docker.com/reference/compose-file/
- NVIDIA Container Toolkit — https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/

**Read the Dockerfile reference top to bottom once.** It's shorter than you think, and it is
the single highest-leverage hour in Part C.
