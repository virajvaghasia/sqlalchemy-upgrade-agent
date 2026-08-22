"""BM25 + RRF hybrid — unit tests, no Qdrant required."""

from __future__ import annotations

from rag import bm25, hybrid


def test_tokenize_splits_dotted_api_names():
    assert bm25.tokenize('engine.table_names() attribute error') == [
        "engine",
        "table_names",
        "attribute",
        "error",
    ]


def test_tokenize_keeps_snake_case_whole():
    """Do not split table_names → table+names; those drown the rare symbol."""
    toks = bm25.tokenize("get_table_names")
    assert "get_table_names" in toks
    assert "table" not in toks


def test_bm25_ranks_exact_symbol_above_unrelated_prose():
    chunks = [
        {
            "id": "c_hit",
            "sqlalchemy_version": "2.0.51",
            "source_path": "a.rst",
            "heading_path": ["Reflection"],
            "text": "Use inspect(engine).get_table_names() instead of engine.table_names().",
            "n_chars": 10,
            "char_start": 0,
            "char_end": 10,
            "has_code": True,
        },
        {
            "id": "c_miss",
            "sqlalchemy_version": "2.0.51",
            "source_path": "b.rst",
            "heading_path": ["Sessions"],
            "text": "A Session represents a workspace for ORM objects.",
            "n_chars": 10,
            "char_start": 0,
            "char_end": 10,
            "has_code": False,
        },
    ]
    idx = bm25.build(chunks)
    hits = idx.search("engine.table_names() is gone", limit=2)
    assert [h.chunk_id for h in hits] == ["c_hit"]
    assert hits[0].score > 0


def test_bm25_version_filter_excludes_other_release():
    chunks = [
        {
            "id": "c14",
            "sqlalchemy_version": "1.4.52",
            "source_path": "a.rst",
            "heading_path": ["X"],
            "text": "table_names on the engine",
            "n_chars": 1,
            "char_start": 0,
            "char_end": 1,
            "has_code": False,
        },
        {
            "id": "c20",
            "sqlalchemy_version": "2.0.51",
            "source_path": "a.rst",
            "heading_path": ["X"],
            "text": "table_names on the engine",
            "n_chars": 1,
            "char_start": 0,
            "char_end": 1,
            "has_code": False,
        },
    ]
    idx = bm25.build(chunks)
    only20 = idx.search("table_names", limit=5, version="2.0.51")
    assert [h.chunk_id for h in only20] == ["c20"]


def test_rrf_dense_heavy_keeps_dense_top_when_sparse_disagrees():
    """kd < kb → dense rank-1 beats sparse rank-1 when they are different docs."""
    dense = ["d1", "d2", "d3"]
    sparse = ["s1", "s2", "s3"]
    fused = hybrid.rrf_fuse(dense, sparse, kd=25, kb=90, limit=6)
    assert fused[0] == "d1"
    # Sparse still contributes — s1 lands after the dense head, not first.
    assert fused.index("s1") > fused.index("d1")


def test_rrf_promotes_shared_hit_over_single_channel():
    """A chunk in both lists beats a dense-only neighbour at the same dense rank."""
    dense = ["a", "b"]
    sparse = ["b", "c"]
    fused = hybrid.rrf_fuse(dense, sparse, kd=25, kb=90, limit=3)
    assert fused[0] == "b"


def test_rrf_constants_match_measured_zero_regression_point():
    """Guard against silently reverting to equal-k fusion that broke items."""
    assert hybrid.RRF_K_DENSE == 25
    assert hybrid.RRF_K_SPARSE == 90
    assert hybrid.RRF_K_DENSE < hybrid.RRF_K_SPARSE
