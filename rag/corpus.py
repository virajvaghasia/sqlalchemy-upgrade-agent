"""
Phase 1, Step 1 — fetch the corpus, and record where every byte came from.

    uv run python -m rag.corpus            # fetch if absent, then report
    uv run python -m rag.corpus --force    # re-download and rewrite everything
    uv run python -m rag.corpus --check    # verify on-disk files against the manifest

WHAT THIS FETCHES, AND WHY THAT LIST

`phases/PHASE-1.md` Step 1 settles the corpus. This module is that decision as
code, so the two cannot drift:

    in    doc/build/{orm,core,tutorial,faq}/**.rst   from BOTH pinned versions
    in    doc/build/errors.rst, doc/build/glossary.rst   from BOTH
    in    doc/build/changelog/migration_20.rst       from 2.0 ONLY
    out   the rest of changelog/  — ~60% of the bytes, almost all of it
          per-release one-line bug entries, plus migration guides for 1.0-1.4
    out   dialects/  — Postgres/MySQL/SQLite specifics, not migration material
    out   index/contents/copyright/intro .rst — navigation and a licence
    out   deliverables/BREAKAGES.md — it seeds the Phase 2 golden dataset, and
          a corpus containing the answer key inflates every Phase 2 number

`migration_20.rst` lives inside `changelog/`, which is otherwise excluded. That
looks like a bug and is not: the file is named individually, its ~33 siblings
are not. The manifest says so in `selection`, so nobody has to guess.

WHY .rst SOURCE RATHER THAN THE RENDERED SITE

The tags below carry documentation as reStructuredText. Three consequences:

  - The version is the tag, so "which release does this page describe?" is
    answerable from a directory name rather than inferred. That matters more
    than it sounds: 1.4's tutorial teaches `create_engine(..., future=True)`
    and 2.0's does not, so an untagged chunk can produce a confident, well
    sourced, wrong answer. See PHASE-1.md Step 1.
  - Headings and code blocks are explicit markup, not HTML that has to be
    converted back into text. The Step 2 chunker needs both intact.
  - The API reference is NOT here. Those pages are generated at Sphinx build
    time from Python docstrings. The counts 660 (1.4 tree) and 743 (2.0 tree)
    are **stub lines** (`.. autoclass::` and friends), not unused files — one
    `.rst` we keep can contain many. Inside this fetch the same count is 514 /
    569. See study/10-RETRIEVAL.md R1.4. Docs source and API reference are two
    different corpora; this is the first one.

NOTHING HERE IS COMMITTED EXCEPT THE MANIFEST

`.gitignore` already excludes `corpus/raw/`. A script that rebuilds the corpus
is reproducible; a 3.8MB blob in git is not. `corpus/MANIFEST.json` IS
committed — it is the provenance record, and a diff on it means the corpus
actually moved.

The manifest deliberately carries no timestamp. A generated-at field would make
every regeneration a diff even when nothing changed, which trains you to ignore
the diff. As written, the manifest is a pure function of the two tags and the
selection rules, so `git diff` on it is signal.
"""

from __future__ import annotations

import hashlib
import io
import json
import pathlib
import re
import sys
import tarfile
import tomllib
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "corpus"
RAW_DIR = CORPUS_DIR / "raw"
MANIFEST_PATH = CORPUS_DIR / "MANIFEST.json"

TARBALL_URL = "https://github.com/sqlalchemy/sqlalchemy/archive/refs/tags/{tag}.tar.gz"
DOC_ROOT = "doc/build"

NARRATIVE_DIRS = ("orm", "core", "tutorial", "faq")
ROOT_FILES = ("errors.rst", "glossary.rst")
MIGRATION_GUIDE = "changelog/migration_20.rst"


# ---------------------------------------------------------------------------
# Which versions. Both are read from files that already pin them, never typed
# here, so the corpus cannot document a release the rest of the repo isn't on.
# ---------------------------------------------------------------------------

def pin_1_4() -> str:
    """The 1.4 version, from pyproject's own dependency pin."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    for dep in data["project"]["dependencies"]:
        match = re.fullmatch(r"sqlalchemy==(.+)", dep.strip(), re.IGNORECASE)
        if match:
            return match.group(1)
    raise SystemExit("no 'sqlalchemy==<version>' pin found in pyproject.toml dependencies")


def pin_2_0() -> str:
    """
    The 2.0 version, from verify_2_0.PIN — the single source of truth for which
    2.0 the BREAKAGES.md evidence was taken on.

    Read out of the source text rather than imported. verify_2_0 calls
    sys.exit() at import time when SQLAlchemy is older than 2.0, which is
    correct for that module and fatal for this one: this repo runs on 1.4.52.
    """
    source = (REPO_ROOT / "experiments" / "sqlalchemy_1_4_vs_2_0" / "verify_2_0.py").read_text()
    match = re.search(r'^PIN\s*=\s*"([^"]+)"', source, re.MULTILINE)
    if not match:
        raise SystemExit("could not read PIN from experiments/sqlalchemy_1_4_vs_2_0/verify_2_0.py")
    return match.group(1)


def tag_for(version: str) -> str:
    """1.4.52 -> rel_1_4_52, which is how SQLAlchemy names its release tags."""
    return "rel_" + version.replace(".", "_")


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def is_selected(rel_path: str, *, take_migration_guide: bool) -> bool:
    """
    `rel_path` is relative to doc/build/ — e.g. "orm/queryguide/select.rst".

    Kept as one predicate rather than a glob list so the exclusions above are
    checkable by reading twelve lines instead of trusting a pattern.
    """
    if not rel_path.endswith(".rst"):
        return False
    parts = rel_path.split("/")
    if len(parts) == 1:
        return rel_path in ROOT_FILES
    if parts[0] in NARRATIVE_DIRS:
        return True
    return take_migration_guide and rel_path == MIGRATION_GUIDE


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def download(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract(blob: bytes, version: str, *, take_migration_guide: bool) -> list[dict]:
    """
    Pull the selected .rst files out of a release tarball and write them under
    corpus/raw/<version>/, mirroring their doc/build layout.

    Output paths are built from the validated relative path rather than handed
    to tar.extract(), so a malicious archive cannot write outside RAW_DIR. The
    tarball comes from GitHub over TLS, but "the input was trustworthy" is not
    a property you want load-bearing in a script that unpacks archives.
    """
    prefix = f"sqlalchemy-{tag_for(version)}/{DOC_ROOT}/"
    dest_root = RAW_DIR / version
    entries: list[dict] = []

    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            rel_path = member.name[len(prefix):]
            if not is_selected(rel_path, take_migration_guide=take_migration_guide):
                continue

            handle = archive.extractfile(member)
            if handle is None:                      # pragma: no cover - defensive
                continue
            content = handle.read()

            dest = dest_root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

            entries.append({
                "path": str(dest.relative_to(REPO_ROOT)),
                "sqlalchemy_version": version,
                "source_path": f"{DOC_ROOT}/{rel_path}",
                "bytes": len(content),
                "sha256": sha256(content),
            })

    entries.sort(key=lambda e: e["path"])
    return entries


def build_manifest() -> dict:
    versions = {"1.4": pin_1_4(), "2.0": pin_2_0()}
    sources, files = [], []

    for series, version in versions.items():
        tag = tag_for(version)
        url = TARBALL_URL.format(tag=tag)
        print(f"fetching {tag} ...", file=sys.stderr)
        blob = download(url)
        entries = extract(blob, version, take_migration_guide=series == "2.0")

        sources.append({
            "series": series,
            "sqlalchemy_version": version,
            "tag": tag,
            "url": url,
            "tarball_bytes": len(blob),
            "tarball_sha256": sha256(blob),
            "file_count": len(entries),
            "bytes": sum(e["bytes"] for e in entries),
        })
        files.extend(entries)

    return {
        "generated_by": "rag/corpus.py",
        "decision": "phases/PHASE-1.md Step 1",
        "selection": {
            "doc_root": DOC_ROOT,
            "narrative_dirs": list(NARRATIVE_DIRS),
            "root_files": list(ROOT_FILES),
            "migration_guide": {
                "path": MIGRATION_GUIDE,
                "versions": ["2.0"],
                "note": (
                    "named individually; the rest of changelog/ is excluded, so this "
                    "is not an inconsistency"
                ),
            },
            "excluded": {
                "changelog/ (except migration_20.rst)": "~60% of bytes, per-release bug entries and 1.0-1.4 migration guides",
                "dialects/": "backend specifics, not migration material",
                "index/contents/copyright/intro .rst": "navigation and licence, no answers",
                "API reference": "generated from docstrings at Sphinx build time; absent from .rst source",
                "deliverables/BREAKAGES.md": "seeds the Phase 2 golden dataset; keeping it out keeps that answer key clean",
            },
        },
        "sources": sources,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Verify and report
# ---------------------------------------------------------------------------

def check(manifest: dict) -> list[str]:
    """Every manifest entry, re-hashed off disk. Returns the problems found."""
    problems = []
    for entry in manifest["files"]:
        path = REPO_ROOT / entry["path"]
        if not path.exists():
            problems.append(f"missing: {entry['path']}")
        elif sha256(path.read_bytes()) != entry["sha256"]:
            problems.append(f"changed: {entry['path']}")
    return problems


def report(manifest: dict) -> None:
    """
    Every number below is counted off the manifest that was just built. None of
    them is a literal, which is the rule this repo is held to.
    """
    print(f"corpus manifest: {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    for source in manifest["sources"]:
        print(
            f"  {source['tag']:<11} {source['file_count']:>4} files  "
            f"{source['bytes']:>8} bytes   {source['url']}"
        )

    files = manifest["files"]
    print(f"  {'TOTAL':<11} {len(files):>4} files  {sum(f['bytes'] for f in files):>8} bytes")

    # Top-level grouping, derived from the paths rather than assumed from the
    # selection rules — if the two disagree, the selection rules are wrong.
    groups: dict[str, dict[str, int]] = {}
    for entry in files:
        rel = entry["source_path"][len(DOC_ROOT) + 1:]
        group = rel.split("/")[0] if "/" in rel else "(root)"
        bucket = groups.setdefault(group, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += entry["bytes"]

    print("  by top-level directory:")
    for group in sorted(groups, key=lambda g: -groups[g]["bytes"]):
        print(f"    {group:<12} {groups[group]['files']:>4} files  {groups[group]['bytes']:>8} bytes")


def main() -> None:
    force = "--force" in sys.argv
    check_only = "--check" in sys.argv

    if check_only:
        if not MANIFEST_PATH.exists():
            sys.exit(f"no manifest at {MANIFEST_PATH} — run without --check first")
        manifest = json.loads(MANIFEST_PATH.read_text())
        problems = check(manifest)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            sys.exit(f"{len(problems)} of {len(manifest['files'])} files do not match the manifest")
        print(f"all {len(manifest['files'])} files match the manifest")
        report(manifest)
        return

    if MANIFEST_PATH.exists() and not force:
        manifest = json.loads(MANIFEST_PATH.read_text())
        if not check(manifest):
            # Safe to re-run: an intact corpus is left alone, like seed.py.
            print("corpus already on disk and matching the manifest (--force to refetch)")
            report(manifest)
            return
        print("corpus on disk does not match the manifest — refetching", file=sys.stderr)

    manifest = build_manifest()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    report(manifest)


if __name__ == "__main__":
    main()
