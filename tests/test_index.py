"""What the Qdrant collection must never silently become.

The failure this guards is not "the load crashed" — a crash is visible. It is a
collection that holds vectors from two different model revisions, or a search
issued in a different space from the one the corpus was embedded in. Both return
plausible results while being wrong (`study/09-DECISIONS.md` D36).

CI has no Qdrant, and `uv sync --frozen` installs neither qdrant-client nor
sentence-transformers, so nothing here imports them or expects a server. The
integration checks skip rather than fail when the database is absent.
"""

import contextlib
import io
import json
import warnings

import pytest

from rag import embed, index

STATS = json.loads(embed.STATS_PATH.read_text()) if embed.STATS_PATH.exists() else None
needs_stats = pytest.mark.skipif(STATS is None, reason="no EMBED_STATS.json — run rag.embed")


# --- the collection name is the compatibility guard ------------------------

def test_collection_name_carries_model_and_revision():
    """Qdrant has no collection-level metadata field, so what produced a
    collection goes where it cannot be ignored: the name. Re-embedding with a
    different revision then yields a DIFFERENT collection rather than a silently
    mixed one — the same trick as declaring `image:` in Compose (D20)."""
    name = index.collection_name({
        "model": "BAAI/bge-m3",
        "revision": "5617a9f61b028005a4858fdac845db406aefb181",
    })
    assert name == "sqlalchemy-upgrade-agent-bge-m3-5617a9f6"


def test_a_different_revision_yields_a_different_collection():
    """The whole point. Vectors from two revisions are not comparable, so they
    must not be able to land in one collection by accident."""
    base = {"model": "BAAI/bge-m3", "revision": "5617a9f61b028005a4858fdac845db406aefb181"}
    moved = {**base, "revision": "0000000011111111222222223333333344444444"}
    assert index.collection_name(base) != index.collection_name(moved)


def test_a_different_model_yields_a_different_collection():
    base = {"model": "BAAI/bge-m3", "revision": "5617a9f61b028005a4858fdac845db406aefb181"}
    other = {**base, "model": "intfloat/e5-large"}
    assert index.collection_name(base) != index.collection_name(other)


def test_collection_name_is_a_legal_qdrant_name():
    """Lowercase, no slashes, no spaces — the model id contains a slash and it
    has to be stripped rather than passed through."""
    name = index.collection_name({"model": "BAAI/bge-m3", "revision": "a" * 40})
    assert name == name.lower()
    assert "/" not in name and " " not in name


@needs_stats
def test_the_name_matches_the_run_that_actually_happened():
    name = index.collection_name(STATS)
    assert STATS["revision"][:8] in name
    assert "bge-m3" in name


# --- the query must live in the same space as the corpus -------------------

def test_search_reuses_the_corpus_embedding_settings():
    """A query normalized differently, or truncated differently, from the corpus
    is compared against vectors it does not share a space with. Search still
    returns results; they are just ranked wrong. So `index.search` must read
    these from `rag.embed` rather than restating them."""
    source = (index.__file__ and open(index.__file__).read())
    assert "embed.NORMALIZE" in source, "search must use the corpus's normalize setting"
    assert "embed.MODEL_REVISION" in source, "search must use the pinned revision"
    assert "embed.MAX_SEQ_LENGTH" in source, "search must use the corpus's sequence window"


# --- integration, only when a database is actually there -------------------

def _live_client():
    """A Qdrant client if one is reachable, else None — and SILENT either way.

    The silence is load-bearing, not tidiness. This runs at import time, and
    `tools/check_runnable.py` compares stdout AND stderr for every `# runnable`
    block — including the ones that run `pytest --collect-only`. With Qdrant
    down, `QdrantClient` writes a version-check UserWarning to stderr, which
    breaks those blocks while their visible output stays identical. A test
    helper must not be able to invalidate the documentation.
    """
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return None
    try:
        with warnings.catch_warnings(), contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            c = QdrantClient(url=index.URL, timeout=2)
            c.get_collections()
        return c
    except BaseException:
        # BaseException: rag/index.py exits via sys.exit() on an unreachable
        # Qdrant, and SystemExit does not inherit from Exception.
        return None


needs_qdrant = pytest.mark.skipif(
    STATS is None or _live_client() is None,
    reason="no Qdrant at 127.0.0.1:6333 — docker compose up -d qdrant",
)


@needs_qdrant
def test_point_count_matches_the_embedding_run():
    """Step 3's stated gate: the count in the database matches the count of
    chunks. A short load is the failure that would otherwise go unnoticed."""
    c = _live_client()
    name = index.collection_name(STATS)
    assert c.collection_exists(name), f"{name} not loaded — run `uv run python -m rag.index`"
    assert c.count(collection_name=name, exact=True).count == STATS["n_vectors"]


@needs_qdrant
def test_collection_dimension_and_distance():
    """COSINE with unit vectors. A collection built as DOT or EUCLID would still
    return neighbours, ranked by the wrong geometry."""
    c = _live_client()
    info = c.get_collection(index.collection_name(STATS))
    params = info.config.params.vectors
    assert params.size == STATS["dim"]
    assert params.distance.lower() == "cosine"


@needs_qdrant
def test_every_point_carries_what_a_citation_needs():
    """Sources are printed next to the answer in Step 4, so the payload has to
    travel with the vector rather than be looked up by an index that could
    drift out of step with the collection."""
    c = _live_client()
    points, _ = c.scroll(index.collection_name(STATS), limit=5, with_payload=True)
    assert points
    for p in points:
        for field in ("chunk_id", "sqlalchemy_version", "source_path", "heading_path", "text"):
            assert field in p.payload, f"payload missing {field}"
        assert p.payload["text"].strip()
