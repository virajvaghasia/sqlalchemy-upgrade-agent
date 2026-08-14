"""What the chunker must never do, pinned.

Phase 1 Step 2 has two rules that are easy to state and easy to break silently:
**code blocks must not be split**, and **headings are context**. A chunker that
violates either still produces plausible-looking output — which is exactly why
these are tests rather than a note in the docs.

Split in two halves:

- The pure functions are tested on hand-written RST, so they run in CI where
  `corpus/raw/` does not exist (it is fetched, not committed — D11).
- The corpus-wide properties are checked against `corpus/CHUNK_STATS.json`,
  which IS committed, the same arrangement `test_corpus.py` uses.
"""

import json

import pytest

from rag import chunk

STATS = json.loads(chunk.STATS_PATH.read_text())


# --- sections and headings -------------------------------------------------

SAMPLE = """\
.. _anchor_target:

===============
Working with It
===============

Intro paragraph that says something real about the subject at hand.

Using SELECT
============

A paragraph before the example, ending in a colon::

    >>> session.execute(select(User))
    [(User(id=1),)]

Trailing prose after the block.
"""


def test_overlined_title_is_not_its_own_section():
    """`===` / title / `===` is one heading.

    Missed, the overline becomes a 15-character chunk of adornment. That is
    what put a bare `===============` in the index on the first run.
    """
    sections = chunk.split_sections(SAMPLE.split("\n"))
    titles = [path[-1] for path, _, _ in sections if path]
    assert titles == ["Working with It", "Using SELECT"]
    assert not any(chunk.ADORNMENT.match(t) for t in titles)


def test_heading_path_carries_ancestry():
    """A chunk saying "this was removed" needs the heading naming what "this" is.

    Per the RST spec, overline+underline is a DIFFERENT level from
    underline-only with the same character. Keying the level on the character
    alone collapses a page title and its sections into one depth, and every
    section silently loses its parent — which is what this asserts against.
    """
    sections = chunk.split_sections(SAMPLE.split("\n"))
    paths = [path for path, _, _ in sections if path]
    assert paths[-1] == ["Working with It", "Using SELECT"]


def test_table_rule_is_not_read_as_a_heading():
    """An adornment shorter than the line above it is a table rule, not a title."""
    lines = ["Column A    Column B", "---", "value       value"].copy()
    sections = chunk.split_sections(lines)
    assert sections == [([], 0, 3)]


# --- code blocks -----------------------------------------------------------

def test_code_block_is_one_atom():
    blocks = chunk.split_blocks(SAMPLE.split("\n"))
    code = [text for kind, text in blocks if kind == "code"]
    assert len(code) == 1
    assert ">>> session.execute(select(User))" in code[0]
    assert "[(User(id=1),)]" in code[0]


def test_code_atom_keeps_the_sentence_that_introduces_it():
    """In RST the line ending `::` is the last line of the introducing
    paragraph. Severed, the example arrives with nothing saying what it shows."""
    blocks = chunk.split_blocks(SAMPLE.split("\n"))
    code = next(text for kind, text in blocks if kind == "code")
    assert "A paragraph before the example, ending in a colon::" in code


def test_pack_never_splits_a_block():
    big = "x" * 5000
    blocks = [("code", big)]
    out = chunk.pack(blocks, chunk.TARGET, chunk.HARD_MAX, chunk.OVERLAP_MAX)
    assert out == [big], "an oversized code block is emitted whole, not cut"


def test_overlap_carries_whole_blocks_only():
    """The first version carried `tail[-200:]` and produced a chunk opening
    with the word "sed on". Overlap is whole prose blocks or nothing."""
    blocks = [("prose", "A" * 300), ("prose", "B" * 1700), ("prose", "C" * 1700)]
    out = chunk.pack(blocks, chunk.TARGET, chunk.HARD_MAX, chunk.OVERLAP_MAX)
    for text in out:
        for part in text.split("\n\n"):
            assert part in {"A" * 300, "B" * 1700, "C" * 1700}, "a partial block was carried"


def test_code_is_never_carried_forward():
    """A duplicated half-example is the failure this module exists to avoid."""
    blocks = [("code", "c" * 300), ("prose", "p" * 1700)]
    out = chunk.pack(blocks, chunk.TARGET, chunk.HARD_MAX, chunk.OVERLAP_MAX)
    assert sum(text.count("c" * 300) for text in out) == 1


# --- what counts as content ------------------------------------------------

@pytest.mark.parametrize("markup", [
    "===============",
    ".. _connections_toplevel:",
    ".. currentmodule:: sqlalchemy.types",
    ".. toctree::\n    :maxdepth: 2\n\n    engines\n    connections",
    ".. autoclass:: Index\n    :members:",
])
def test_markup_only_atoms_are_dropped(markup):
    """These retrieve nothing but can still win a short query, so they are
    worse than absent. 415 of the first run's 3860 chunks were this."""
    assert not chunk.is_content(markup)


@pytest.mark.parametrize("real", [
    ".. note::\n\n    The Session is not thread-safe, which matters when sharing one.",
    ".. versionadded:: 2.0  The insertmanyvalues feature was added in this release.",
    "A plain paragraph of documentation prose that genuinely explains a thing.",
])
def test_real_content_survives(real):
    """note / versionadded / seealso are content, and often the most quotable
    content in the file. The filter is a named list, so unknown markup is kept."""
    assert chunk.is_content(real)


def test_glossary_splits_per_term():
    """glossary.rst is ONE directive holding every term — 69236 bytes at 2.0.
    Unsplit it is a single useless chunk."""
    text = """\
.. glossary::
    :sorted:

    crud
    CRUD
        An acronym meaning "Create, Update, Delete", the operations that
        change data in a database rather than reading it.

    executemany
        A DBAPI method that runs one statement against many parameter sets,
        described in PEP 249 and used by SQLAlchemy for bulk inserts.
"""
    entries = chunk.glossary_entries(text.split("\n"))
    assert len(entries) == 2
    assert "crud" in entries[0][1] and "executemany" not in entries[0][1]
    assert "executemany" in entries[1][1]


# --- the corpus that actually got chunked ----------------------------------

def test_stats_parameters_match_the_module():
    """The committed stats describe the code as it stands, not a past run."""
    assert STATS["parameters"] == {
        "target": chunk.TARGET,
        "hard_max": chunk.HARD_MAX,
        "overlap_max": chunk.OVERLAP_MAX,
    }


def test_no_chunk_is_below_the_floor():
    assert STATS["size"]["min"] >= chunk.MIN_CHARS


def test_median_chunk_is_near_the_target_not_the_ceiling():
    """If the median sat at HARD_MAX the packer would be cramming rather than
    following the document's own boundaries."""
    assert chunk.MIN_CHARS < STATS["size"]["median"] < chunk.TARGET


def test_oversized_chunks_are_rare_and_counted():
    """Oversized means one code block bigger than HARD_MAX, emitted whole. That
    is the intended trade, but if it stops being rare the target is wrong."""
    assert STATS["oversized"] / STATS["n_chunks"] < 0.02


def test_both_versions_are_represented():
    assert set(STATS["by_version"]) == {"1.4.52", "2.0.51"}
    assert all(n > 0 for n in STATS["by_version"].values())


def test_phase_1_quotes_the_measured_chunk_counts():
    """PHASE-1.md pastes this module's report. Fails if the chunker moves and
    the doc does not."""
    doc = (chunk.corpus.REPO_ROOT / "phases" / "PHASE-1.md").read_text()
    line = f"  {STATS['n_chunks']} chunks   {STATS['n_chars']} chars"
    assert line in doc, f"PHASE-1.md does not contain: {line!r}"
