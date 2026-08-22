"""
Sphinx/RST text cleanup — **rejected experiment** (`D69`, 2026-08-22).

Tried stripping `:class:`_orm.Session`` → `Session` (and unwrap ``literals``)
before dense embed and BM25. Full re-embed dropped recall@5 **0.64 → 0.58** and
broke two baseline hits (`g008`, `g013`). Production embed/BM25 stay on **raw**
`chunk["text"]`; this module is kept so the next sitting does not re-derive a
worse index.

`chunks.jsonl` was never rewritten — citations always show the source markup.
"""

from __future__ import annotations

import re

# :class:`Session`, :meth:`Connection.execute`, :paramref:`x`, …
_ROLE = re.compile(r":[a-z-]+:`([^`]+)`")

# ``literal`` in RST — keep the inner text, drop the backticks.
_LITERAL = re.compile(r"``([^`]+)``")


def _role_inner(inner: str) -> str:
    """Turn a role payload into the token a developer would type.

    `:class:`_orm.Session``  → Session
    `:meth:`Engine.table_names`` → table_names
    `:class:`User <myapp.User>`` → User
    """
    inner = inner.strip()
    if "<" in inner and inner.endswith(">"):
        inner = inner.split("<", 1)[0].strip()
    if "." in inner:
        inner = inner.rsplit(".", 1)[-1]
    # Leading underscore private-module markers (_orm, _engine) already removed
    # by the rsplit when a dotted path was present.
    return inner


def for_retrieval(text: str) -> str:
    """Remove role wrappers and double-backtick literals. Not used in production (`D69`)."""
    text = _ROLE.sub(lambda m: _role_inner(m.group(1)), text)
    return _LITERAL.sub(r"\1", text)
