"""What the chunker must never do, pinned.

Phase 1 Step 2 has two rules that are easy to state and easy to break silently:
**code blocks must not be split**, and **headings are context**. A chunker that
violates either still produces plausible-looking output — which is exactly why
these are tests rather than a note in the docs.

Split in two halves:

- The pure functions are tested on hand-written RST, so they run in CI where
  `corpus/raw/` does not exist (it is fetched, not committed).
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
    code = [b[1] for b in blocks if b[0] == "code"]
    assert len(code) == 1
    assert ">>> session.execute(select(User))" in code[0]
    assert "[(User(id=1),)]" in code[0]


def test_code_atom_keeps_the_sentence_that_introduces_it():
    """In RST the line ending `::` is the last line of the introducing
    paragraph. Severed, the example arrives with nothing saying what it shows."""
    blocks = chunk.split_blocks(SAMPLE.split("\n"))
    code = next(b[1] for b in blocks if b[0] == "code")
    assert "A paragraph before the example, ending in a colon::" in code


def test_pack_never_splits_a_block():
    big = "x" * 5000
    out = chunk.pack([("code", big, 0, 9)], chunk.TARGET, chunk.HARD_MAX, chunk.OVERLAP_MAX)
    assert [t for t, _, _ in out] == [big], "an oversized code block is emitted whole, not cut"


def test_overlap_carries_whole_blocks_only():
    """The first version carried `tail[-200:]` and produced a chunk opening
    with the word "sed on". Overlap is whole prose blocks or nothing."""
    blocks = [("prose", "A" * 300, 0, 1), ("prose", "B" * 1700, 2, 3),
              ("prose", "C" * 1700, 4, 5)]
    out = chunk.pack(blocks, chunk.TARGET, chunk.HARD_MAX, chunk.OVERLAP_MAX)
    for text, _, _ in out:
        for part in text.split("\n\n"):
            assert part in {"A" * 300, "B" * 1700, "C" * 1700}, "a partial block was carried"


def test_code_is_never_carried_forward():
    """A duplicated half-example is the failure this module exists to avoid."""
    blocks = [("code", "c" * 300, 0, 1), ("prose", "p" * 1700, 2, 3)]
    out = chunk.pack(blocks, chunk.TARGET, chunk.HARD_MAX, chunk.OVERLAP_MAX)
    assert sum(text.count("c" * 300) for text, _, _ in out) == 1


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
    assert all(len(e) == 4 for e in entries), "entries carry (kind, text, first, last)"
    assert "crud" in entries[0][1] and "executemany" not in entries[0][1]
    assert "executemany" in entries[1][1]


# --- the character range Phase 1 Step 2 requires ------------------------

# SAMPLE above is deliberately tiny and every chunk from it falls under
# MIN_CHARS, so it is dropped. These tests need paragraphs that survive.
RANGE_SAMPLE = """\
================
Engine and Rows
================

""" + "\n\n".join(
    f"Paragraph {n} explains a distinct part of the engine and connection API in "
    f"enough words that the chunker keeps it rather than folding it away as markup."
    for n in range(1, 8)
) + """

Using SELECT
============

""" + "\n\n".join(
    f"Section paragraph {n} describes selecting rows and how the 2.0 form differs "
    f"from the 1.4 one, at a length the minimum-size floor will not discard."
    for n in range(1, 6)
) + "\n"

def test_a_chunk_reports_where_in_the_source_it_came_from(tmp_path):
    """Step 2's "Done when" asks for source file, heading path AND character
    range. The first version shipped a length (`n_chars`) and no offsets, which
    names a file but not a place in it — so a reader who distrusts a retrieved
    passage cannot go and open the original."""
    src = tmp_path / "sample.rst"
    src.write_text(RANGE_SAMPLE)
    chunks = chunk.chunk_file(src, "2.0.51", "doc/build/sample.rst")
    assert chunks
    for c in chunks:
        assert "char_start" in c and "char_end" in c
        assert 0 <= c["char_start"] < c["char_end"] <= len(RANGE_SAMPLE)


def test_the_range_actually_brackets_the_chunk(tmp_path):
    """An offset that is present but wrong is worse than one that is absent."""
    src = tmp_path / "sample.rst"
    src.write_text(RANGE_SAMPLE)
    for c in chunk.chunk_file(src, "2.0.51", "doc/build/sample.rst"):
        span = RANGE_SAMPLE[c["char_start"]:c["char_end"]]
        body = [l.strip() for l in c["text"].split("\n") if l.strip()]
        assert body[0] in span, f"chunk starts outside its own range: {body[0]!r}"
        assert body[-1] in span, f"chunk ends outside its own range: {body[-1]!r}"


def test_every_chunk_in_the_corpus_has_a_sane_range():
    """chunks.jsonl is generated and gitignored, so this skips in CI."""
    import json
    if not chunk.CHUNKS_PATH.exists():
        pytest.skip("no chunks.jsonl — run rag.chunk")
    chunks = [json.loads(l) for l in chunk.CHUNKS_PATH.read_text().splitlines()]
    for c in chunks:
        assert c["char_start"] < c["char_end"], c["id"]


def test_sample_does_not_write_anything(tmp_path, monkeypatch):
    """`--sample` is read-only.

    It used to rewrite chunks.jsonl and CHUNK_STATS.json before printing. That
    looked harmless because the chunker is deterministic — the rewrite
    reproduced the file byte-for-byte. It is not harmless while anything
    downstream is running: embeddings.npy is row-aligned to chunks.jsonl BY
    POSITION, so rewriting the chunks under a running embed produces an index
    whose vectors point at the wrong text, with no error anywhere.
    """
    import sys
    if not chunk.CHUNKS_PATH.exists():
        pytest.skip("no chunks.jsonl — run rag.chunk")
    before = (chunk.CHUNKS_PATH.stat().st_mtime_ns, chunk.STATS_PATH.stat().st_mtime_ns)
    monkeypatch.setattr(sys, "argv", ["rag.chunk", "--sample", "1"])
    chunk.main()
    after = (chunk.CHUNKS_PATH.stat().st_mtime_ns, chunk.STATS_PATH.stat().st_mtime_ns)
    assert before == after, "--sample wrote to disk"


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


# --- the "stands on its own" audit -----------------------------------
#
# These run on hand-written chunks, not the corpus, so they work in CI where
# corpus/raw/ is absent. The corpus-wide numbers are pinned separately, off the
# committed stats file.

def _c(cid, text, start, end, path="doc/build/x.rst", version="2.0.51"):
    return {"id": cid, "text": text, "char_start": start, "char_end": end,
            "source_path": path, "sqlalchemy_version": version, "n_chars": len(text),
            "has_code": False, "heading_path": []}


def test_backward_opener_fires_on_a_real_dangling_reference():
    """c00138's actual opening. If this stops matching, the audit stops seeing
    the failure it was built from.

    Note it does not pin any single branch of the pattern: two alternatives
    match this string, so breaking one leaves the test green. That is the
    detector being robust, not the test being strong -- checked by mutation."""
    assert chunk.OPENS_BACKWARD.search(
        "While the above example is against the built-in :class:`.AddConstraint`")


def test_backward_opener_ignores_a_chunk_that_repairs_itself():
    """c01480 opens backwards too -- 'We've constructed...' -- and then says
    what was constructed in the same sentence, so it stands alone. This is the
    control: without it the audit only measures how eagerly the regex fires,
    and every number it prints would be meaningless."""
    assert not chunk.OPENS_BACKWARD.search(
        "We've constructed a fairly elaborate object hierarchy to represent")


def test_audit_counts_a_chunk_ending_on_a_promise():
    a = _c("a", "the state is as follows:", 0, 100)
    b = _c("b", "* first\n* second", 100, 200)
    assert chunk.audit([a, b])["ends_open"] == 1


def test_audit_separates_a_bad_chunk_from_lost_content():
    """The distinction the chunk audit turns on. Both pairs have a chunk ending mid-promise;
    only one has lost the payload. Overlap is what decides, and conflating the
    two would have reported 352 broken chunks as 352 holes in the corpus."""
    # Identical first chunk in both. The ONLY difference is whether the chunk
    # after it starts before it ends -- c03012 (overlapped, payload survives)
    # against c00138 (not overlapped, payload gone).
    covered = [_c("a", "as follows:", 0, 100), _c("b", "as follows:\n* one", 80, 200)]
    orphan = [_c("a", "as follows:", 0, 100), _c("b", "* one", 100, 200)]

    assert chunk.audit(covered)["ends_open"] == 1
    assert chunk.audit(covered)["ends_open_lost"] == 0
    assert chunk.audit(covered)["lost"] == 0

    assert chunk.audit(orphan)["ends_open"] == 1
    assert chunk.audit(orphan)["ends_open_lost"] == 1
    assert chunk.audit(orphan)["lost"] == 1


# --- shape C: the boundary that lands inside a code listing -----
#
# The two shapes are prose. This one is not, and that is the point: broken
# prose is visible on sight, broken code is not. Until 2026-08-22 this defect
# had a hand-computed number and no code behind it.


def test_a_listing_cut_in_half_is_severed():
    """Both edges are indented code and the second chunk starts where the first
    ends, so the statement is split across the boundary with nothing to recover
    it from."""
    a = _c("a", "some prose::\n\n    stmt = select(User).where(\n", 0, 100)
    b = _c("b", "        User.name == 'x'\n    )\n", 100, 200)
    assert chunk.severed_listing(a, b)


def test_an_overlapped_listing_is_not_severed():
    """The chunker carries whole blocks forward as overlap. If the next chunk starts before this
    one ends, the listing exists intact in the overlap and nothing was lost --
    the same distinction audit()'s `a_lost` makes for shape A."""
    a = _c("a", "prose::\n\n    stmt = select(User).where(\n", 0, 100)
    b = _c("b", "    stmt = select(User).where(\n        User.name == 'x'\n)", 80, 200)
    assert not chunk.severed_listing(a, b)


def test_indented_prose_is_not_a_severed_listing():
    """The control, and the reason the honest count is 3 real of 5 flagged rather
    than 123. Every glossary.rst definition body is indented under its term, so
    'indented on both sides' alone would flag the whole file. A Python or SQL
    token has to be there too."""
    a = _c("a", "ACID\n    a term describing a database that is\n", 0, 100)
    b = _c("b", "    atomic, consistent, isolated and durable\n", 100, 200)
    assert not chunk.severed_listing(a, b)


def test_neighbours_never_pair_two_versions_of_the_same_page():
    """A 1.4 chunk and a 2.0 chunk of the same file are a twin, not
    adjacent text. Pairing them would make every twin look like a severed
    boundary and invent a defect that is not there."""
    old = _c("a", "    stmt = select(User)\n", 0, 100, version="1.4.52")
    new = _c("b", "    stmt = select(User)\n", 0, 100, version="2.0.51")
    nxt, prv = chunk.neighbours([old, new])
    assert nxt == {} and prv == {}


def test_the_module_level_predicates_are_what_audit_counts():
    """audit() used to hold these inline. The absents survey needed the same questions asked of
    a subset, and two copies of a detector drift. If this fails, the survey and
    the corpus audit have started disagreeing."""
    a = _c("a", "the state is as follows:", 0, 100)
    b = _c("b", "While the above example shows the constraint", 100, 200)
    assert chunk.ends_open_shape(a) and not chunk.ends_open_shape(b)
    assert chunk.opens_backward_shape(b) and not chunk.opens_backward_shape(a)
    stats = chunk.audit([a, b])
    assert stats["ends_open"] == 1 and stats["opens_backward"] == 1
