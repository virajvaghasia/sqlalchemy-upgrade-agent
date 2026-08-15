"""The embedding run's compatibility contract, pinned.

Two runs of `rag/embed.py` produce vectors that can live in the same index
**only if** the model revision, the normalization setting and the dtype match.
Get any of those wrong across two runs and the index is not degraded, it is
meaningless — vectors from different revisions are not in the same space, and
cosine similarity between them is noise. See `study/09-DECISIONS.md` D36.

None of this imports torch or sentence-transformers. CI runs `uv sync --frozen`
without `--extra embed`, so the embedding stack is absent there — and a test
that can only run on the developer's laptop is not protecting the repo.
"""

import json

import pytest

from rag import embed

STATS = json.loads(embed.STATS_PATH.read_text()) if embed.STATS_PATH.exists() else None
needs_stats = pytest.mark.skipif(STATS is None, reason="no EMBED_STATS.json — run rag.embed")


# --- the settings that decide compatibility --------------------------------

def test_model_revision_is_pinned():
    """A name is not a version. "BAAI/bge-m3" is a repository and repositories
    move; re-embedding half a corpus after it moves silently produces an index
    that is two incompatible things at once."""
    assert embed.MODEL_REVISION, "MODEL_REVISION is None — resolve it and pin it"
    assert len(embed.MODEL_REVISION) == 40, "expected a full 40-char git sha"


def test_normalization_is_on():
    """Qdrant's COSINE distance expects unit-length vectors. A run that skipped
    normalization would still return results, just wrong ones — which is why
    this is asserted rather than left as a call-site argument."""
    assert embed.NORMALIZE is True


def test_max_seq_length_covers_the_chunker_target():
    """The window has to exceed what the chunker actually emits, or every large
    chunk is embedded as a truncated version of itself."""
    from rag import chunk

    assert embed.MAX_SEQ_LENGTH * 2 > chunk.HARD_MAX, (
        "MAX_SEQ_LENGTH tokens must comfortably exceed HARD_MAX characters; "
        "English is roughly 4 chars/token and code roughly 3"
    )


# --- what gets embedded ----------------------------------------------------

def test_heading_path_is_prepended_to_the_text():
    """Headings ARE context. A chunk reading "this was removed in 2.0" embeds as
    an orphaned sentence unless the heading naming "this" travels with it."""
    text = embed.embedding_input({
        "heading_path": ["Using SELECT Statements", "Working with SQL Functions"],
        "text": "This was removed in 2.0.",
    })
    assert text.startswith("Using SELECT Statements > Working with SQL Functions")
    assert text.endswith("This was removed in 2.0.")


def test_missing_heading_path_does_not_produce_a_leading_separator():
    text = embed.embedding_input({"heading_path": [], "text": "Body only."})
    assert text == "Body only."


# --- device selection ------------------------------------------------------

@pytest.mark.parametrize("requested", ["cpu", "cuda", "mps"])
def test_explicit_device_is_honoured_without_importing_torch(requested):
    """`--device` is the flag that lets the same code run on the Mac and the lab
    PC (D37). It resolves before torch is imported, which is also what makes it
    testable here where torch is not installed."""
    assert embed.pick_device(requested) == requested


# --- the run that actually happened ----------------------------------------

@needs_stats
def test_stats_record_the_settings_that_produced_them():
    """The stats file is what a later step trusts to describe the index. If it
    disagrees with the module, one of them is lying."""
    assert STATS["revision"] == embed.MODEL_REVISION
    assert STATS["revision_pinned"] is True
    assert STATS["normalize"] is embed.NORMALIZE
    assert STATS["dtype"] == "float32"
    assert STATS["max_seq_length"] == embed.MAX_SEQ_LENGTH


@needs_stats
def test_one_vector_per_chunk():
    """The count has to match the chunker's, or rows and chunks have drifted and
    every citation would point at the wrong source."""
    chunk_stats = json.loads((embed.corpus.CORPUS_DIR / "CHUNK_STATS.json").read_text())
    assert STATS["n_vectors"] == chunk_stats["n_chunks"]


@needs_stats
def test_the_recorded_run_was_complete():
    """`--limit` runs are smoke tests. One must never be mistaken for the index."""
    assert STATS["run"]["complete"] is True


@needs_stats
def test_truncation_is_counted_not_assumed():
    """A truncated chunk is embedded as something other than what it says, and
    nothing downstream can tell. The number may be non-zero — it must be known."""
    assert "truncated" in STATS["tokens"]
    assert isinstance(STATS["tokens"]["truncated"], int)
