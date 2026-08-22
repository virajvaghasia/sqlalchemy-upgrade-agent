"""
BM25 keyword search over `corpus/chunks.jsonl` (Phase 3, lever 2).

Dense retrieval maps *meaning*. It fails when the developer types a rare API
symbol whose nearest pages talk about the same *idea* under different words
(`table_names` → pages about reflection that never say the removed name near
the top). BM25 maps *letters*: the same rarity that hurts dense is exactly what
IDF rewards.

No third-party BM25 package — Okapi BM25 is ~40 lines, and pinning another
library for one formula would be theatre. The index builds once from
`chunks.jsonl` and lives in a module global so a scoring run pays the cost once.

Tokenisation is deliberate: `engine.table_names()` becomes
`engine` + `table_names`, not one dotted token. A dotted compound never appears
in the docs as a single token, so it would score nothing.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from rag import corpus, embed

# Word characters + underscore. Dots and punctuation are split points so
# `engine.table_names()` yields `engine` and `table_names` separately.
_TOKEN = re.compile(r"[a-z0-9_]+", re.I)

# Tiny English stop list. Kept short on purpose: `not`, `no`, `error` stay —
# they appear in real developer questions and in error-page headings.
_STOP = frozenset(
    "a an the to of in on for with is are was were be been being and or "
    "do does did how what why when where which this that it my i me we you "
    "your from as at by".split()
)

# Okapi defaults. Not tuned yet — the fusion constants (`hybrid.RRF_*`) are the
# measured levers; changing k1/b without a paired score is guessing.
K1 = 1.2
B = 0.75


def tokenize(text: str) -> list[str]:
    """Split on non-identifier characters; keep snake_case wholes.

    `engine.table_names()` → ['engine', 'table_names'].
    Does **not** further split `table_names` into `table`+`names` — those parts
    are common words and drown the rare symbol (measured: snake-split dropped
    recall@5 versus whole-identifier tokens).
    """
    out: list[str] = []
    for raw in _TOKEN.findall(text):
        t = raw.lower()
        if t in _STOP or len(t) <= 1:
            continue
        out.append(t)
    return out


@dataclass
class Bm25Hit:
    chunk_id: str
    score: float


@dataclass
class Bm25Index:
    """Inverted index over the chunk corpus. Build once; search many times."""

    chunk_ids: list[str]
    doc_len: list[int]
    avgdl: float
    df: dict[str, int]
    inv: dict[str, list[tuple[int, int]]]  # term → [(doc_index, tf), ...]
    # Parallel metadata so a version filter does not need a second pass over jsonl.
    versions: list[str]
    payloads: list[dict]

    def search(
        self,
        query: str,
        limit: int = 20,
        version: str | None = None,
    ) -> list[Bm25Hit]:
        scores: dict[int, float] = defaultdict(float)
        N = len(self.chunk_ids)
        for term in tokenize(query):
            df = self.df.get(term)
            if not df:
                continue
            # BM25 IDF with the (+0.5) smoothing Robertson/Sparck Jones used.
            idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
            for i, tf in self.inv[term]:
                if version is not None and self.versions[i] != version:
                    continue
                dl = self.doc_len[i]
                denom = tf + K1 * (1.0 - B + B * dl / self.avgdl)
                scores[i] += idf * (tf * (K1 + 1.0)) / denom
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
        return [Bm25Hit(self.chunk_ids[i], s) for i, s in ranked]


def _doc_text(chunk: dict) -> str:
    # Heading path is part of what `rag/embed.py` prepends before embedding.
    # BM25 sees the same raw words as dense (`D69` rejected stripping roles —
    # cleaning BM25 alone also failed to move absents without hurting fusion).
    head = " ".join(chunk.get("heading_path") or [])
    return f"{head} {chunk['text']}"


def build(chunks: Iterable[dict] | None = None) -> Bm25Index:
    if chunks is None:
        path = embed.CHUNKS_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"missing {path.relative_to(corpus.REPO_ROOT)} — run `uv run python -m rag.chunk`"
            )
        chunks = [json.loads(line) for line in path.read_text().splitlines() if line]

    chunk_ids: list[str] = []
    doc_len: list[int] = []
    versions: list[str] = []
    payloads: list[dict] = []
    inv: dict[str, list[tuple[int, int]]] = defaultdict(list)
    df: Counter[str] = Counter()

    for chunk in chunks:
        toks = tokenize(_doc_text(chunk))
        i = len(chunk_ids)
        chunk_ids.append(chunk["id"])
        doc_len.append(len(toks))
        versions.append(chunk["sqlalchemy_version"])
        payloads.append(chunk)
        tf = Counter(toks)
        df.update(tf.keys())
        for term, f in tf.items():
            inv[term].append((i, f))

    n = len(chunk_ids)
    avgdl = (sum(doc_len) / n) if n else 0.0
    return Bm25Index(
        chunk_ids=chunk_ids,
        doc_len=doc_len,
        avgdl=avgdl,
        df=dict(df),
        inv=dict(inv),
        versions=versions,
        payloads=payloads,
    )


_INDEX: Bm25Index | None = None


def get_index() -> Bm25Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = build()
    return _INDEX


def reset_index() -> None:
    """Tests only — drop the cached index so the next call rebuilds."""
    global _INDEX
    _INDEX = None
