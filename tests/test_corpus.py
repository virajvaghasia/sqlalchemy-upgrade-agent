"""The Phase 1 corpus decision, pinned.

`phases/PHASE-1.md` Step 1 records what is in the corpus and what is deliberately
out. `rag/corpus.py` implements it. These tests exist so the two cannot drift,
and so a later "just add the changelog, it's only text" cannot happen quietly.

Everything here reads `corpus/MANIFEST.json`, which is committed. Nothing reads
`corpus/raw/`, which is gitignored and therefore absent in CI — the manifest is
the provenance record, so the manifest is what gets checked.
"""

import json
import pathlib

import pytest

from rag import corpus

MANIFEST = json.loads((corpus.MANIFEST_PATH).read_text())
FILES = MANIFEST["files"]
SOURCES = {source["series"]: source for source in MANIFEST["sources"]}


def doc_relpaths(version: str | None = None) -> set[str]:
    """Paths relative to doc/build/, optionally for one version."""
    prefix = len(corpus.DOC_ROOT) + 1
    return {
        entry["source_path"][prefix:]
        for entry in FILES
        if version is None or entry["sqlalchemy_version"] == version
    }


# --- the selection rule itself, no manifest involved -----------------------

@pytest.mark.parametrize(
    "rel_path",
    [
        "orm/queryguide/select.rst",
        "core/engines.rst",
        "tutorial/engine.rst",
        "faq/performance.rst",
        "errors.rst",
        "glossary.rst",
    ],
)
def test_selected(rel_path):
    assert corpus.is_selected(rel_path, take_migration_guide=True)


@pytest.mark.parametrize(
    "rel_path",
    [
        "changelog/changelog_20.rst",      # per-release bug entries — the excluded bulk
        "changelog/migration_14.rst",      # an older migration guide — version skew
        "dialects/postgresql.rst",         # backend specifics
        "index.rst",                       # navigation
        "contents.rst",
        "copyright.rst",
        "intro.rst",
        "orm/queryguide/select.html",      # not .rst
        "conf.py",
    ],
)
def test_not_selected(rel_path):
    assert not corpus.is_selected(rel_path, take_migration_guide=True)


def test_migration_guide_is_2_0_only():
    """The one file taken out of changelog/, and only from the 2.0 tree.

    1.4 ships its own copy of migration_20.rst as a preview of a release that
    had not happened yet. Ingesting both would put two versions of the same
    guide in the index, differing in exactly the places that matter.
    """
    assert corpus.is_selected(corpus.MIGRATION_GUIDE, take_migration_guide=True)
    assert not corpus.is_selected(corpus.MIGRATION_GUIDE, take_migration_guide=False)


# --- the corpus that actually got built ------------------------------------

def test_versions_match_the_repo_pins():
    """The corpus documents the releases the rest of the repo is on.

    1.4.52 comes from pyproject's dependency pin; 2.0.51 from verify_2_0.PIN,
    the constant BREAKAGES.md was measured against. Neither is typed in
    rag/corpus.py, so this test fails if a pin moves and the corpus does not.
    """
    assert SOURCES["1.4"]["sqlalchemy_version"] == corpus.pin_1_4()
    assert SOURCES["2.0"]["sqlalchemy_version"] == corpus.pin_2_0()


def test_only_one_changelog_file_and_it_is_the_migration_guide():
    changelog = {rel for rel in doc_relpaths() if rel.startswith("changelog/")}
    assert changelog == {corpus.MIGRATION_GUIDE}
    assert corpus.MIGRATION_GUIDE in doc_relpaths(SOURCES["2.0"]["sqlalchemy_version"])
    assert corpus.MIGRATION_GUIDE not in doc_relpaths(SOURCES["1.4"]["sqlalchemy_version"])


def test_no_dialect_pages():
    assert not [rel for rel in doc_relpaths() if rel.startswith("dialects/")]


def test_root_files_are_exactly_errors_and_glossary():
    """Both versions, and nothing else from doc/build's top level."""
    for version in (SOURCES["1.4"], SOURCES["2.0"]):
        roots = {rel for rel in doc_relpaths(version["sqlalchemy_version"]) if "/" not in rel}
        assert roots == set(corpus.ROOT_FILES)


def test_breakages_is_not_in_the_corpus():
    """It seeds the Phase 2 golden dataset. A corpus holding the answer key
    makes Phase 2 measure whether retrieval can find its own answers."""
    assert not [entry for entry in FILES if "BREAKAGES" in entry["path"]]


def test_every_file_carries_its_version():
    """Step 4 retrieves across both releases without filtering, so the version
    is the only thing that will explain a wrong answer in the Step 5 file."""
    known = {source["sqlalchemy_version"] for source in MANIFEST["sources"]}
    assert {entry["sqlalchemy_version"] for entry in FILES} == known
    assert all(entry["sha256"] and entry["bytes"] > 0 for entry in FILES)


def test_source_totals_agree_with_the_file_list():
    """The per-source counts are a summary of `files`, not a second opinion."""
    for source in MANIFEST["sources"]:
        entries = [e for e in FILES if e["sqlalchemy_version"] == source["sqlalchemy_version"]]
        assert source["file_count"] == len(entries)
        assert source["bytes"] == sum(e["bytes"] for e in entries)


def test_manifest_has_no_timestamp():
    """Deliberate: it makes the manifest a pure function of the tags and the
    selection rules, so a diff on it means the corpus really moved."""
    assert "generated_at" not in MANIFEST


# --- the numbers quoted in the docs ----------------------------------------

def test_phase_1_quotes_the_measured_totals():
    """PHASE-1.md pastes rag/corpus.py's report. This fails if the corpus moves
    and the doc does not — the failure mode this repo keeps finding."""
    doc = (pathlib.Path(corpus.REPO_ROOT) / "phases" / "PHASE-1.md").read_text()

    total_line = (
        f"  {'TOTAL':<11} {len(FILES):>4} files  {sum(e['bytes'] for e in FILES):>8} bytes"
    )
    assert total_line in doc, f"PHASE-1.md does not contain: {total_line!r}"

    for source in MANIFEST["sources"]:
        line = (
            f"  {source['tag']:<11} {source['file_count']:>4} files  "
            f"{source['bytes']:>8} bytes   {source['url']}"
        )
        assert line in doc, f"PHASE-1.md does not contain: {line!r}"
