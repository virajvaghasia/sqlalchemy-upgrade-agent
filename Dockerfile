FROM python:3.11-slim

WORKDIR /app

# Create the unprivileged user BEFORE anything is copied, so COPY --chown can
# name it. This layer never changes, so it caches forever.
#   --system      no password ageing, no home-dir clutter; it is not a person
#   --uid 10001   a fixed, high uid. Fixed so bind-mount ownership is predictable
#                 across machines; high so it cannot collide with a host user.
RUN useradd --system --uid 10001 --create-home app \
 && chown app:app /app

# That `chown app:app /app` is not redundant with the `COPY --chown` below.
# --chown sets the owner of the files COPIED IN; it does nothing to the
# DIRECTORY they land in, which WORKDIR created as root. Writing a NEW file
# needs write permission on the directory itself — so without this line the
# SQLite default fails with "unable to open database file", while every file
# already in /app is readable and correctly owned. Confusing, and measurable.

# Least-changed first (see the layer-cache rule): the dependency list moves about
# once a month, the source moves every commit.
COPY requirements.txt .

# --no-cache-dir: pip keeps every downloaded wheel under ~/.cache, and that lands
# INSIDE the image layer. It was 9.1MB here and is never read again — pip has
# already unpacked those wheels into site-packages. Deleting it in a later layer
# would not help; layers are additive, so the bytes stay in the layer that made
# them. It has to not be created in the first place.
RUN pip install --no-cache-dir -r requirements.txt

# --chown at copy time rather than a later `chown -R`, which would duplicate every
# file into a second layer just to change its owner.
COPY --chown=app:app . .

# Copied again, after the wide COPY, purely so nothing overwrites the mode. A
# later COPY of the same path wins, and `COPY` carries the SOURCE file's mode —
# on macOS that is 644, which would make the entrypoint unexecutable.
COPY --chmod=755 --chown=app:app entrypoint.sh .

# Everything below this line runs as `app`, not root. Verify with:
#   docker run --rm --entrypoint id sqlagent
USER app

ENTRYPOINT ["./entrypoint.sh"]

CMD ["python", "-m", "experiments.sqlalchemy_1_4_vs_2_0.app"]
