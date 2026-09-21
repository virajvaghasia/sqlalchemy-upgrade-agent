"""Sphinx/RST normalization for retrieval — no model needed."""

from rag import textnorm


def test_role_drops_module_path_to_public_name():
    assert textnorm.for_retrieval(":class:`_orm.Session`") == "Session"
    assert textnorm.for_retrieval(":meth:`_engine.Engine.table_names`") == "table_names"


def test_role_with_angle_target_keeps_visible_name():
    assert textnorm.for_retrieval(":class:`User <myapp.models.User>`") == "User"


def test_double_backtick_literals_unwrap():
    assert textnorm.for_retrieval("call ``engine.execute()`` now") == "call engine.execute() now"


def test_plain_prose_unchanged():
    s = "Session.execute returns Row objects."
    assert textnorm.for_retrieval(s) == s


def test_mixed_sentence():
    raw = "Use :meth:`Session.get` instead of ``Query.get``."
    assert textnorm.for_retrieval(raw) == "Use get instead of Query.get."
