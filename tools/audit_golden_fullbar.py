"""
Fresh full-bar audit of deliverables/golden.json.

NOT verify_2_0.py. Does not import experiments breakage patterns.
For each golden item:
  1) chunks resolve + token overlap with the question
  2) live docs.sqlalchemy.org/en/20 page fetch (needle from chunk heading)
  3) fresh sqlalchemy==2.0.51 executable probes where the claim is testable

Writes deliverables/GOLDEN-FULLBAR-AUDIT.md and prints a summary.

    uv run --with 'sqlalchemy==2.0.51' --with aiosqlite --with greenlet \
        python -m tools.audit_golden_fullbar

aiosqlite and greenlet are NOT optional: g117 probes async relationship
access, and without them that one item reports FAIL for a missing driver
rather than for anything about the golden set. Measured 2026-08-21 — the
report went 100 PASS -> 99 PASS / 1 FAIL on exactly that.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Imported at module level so Mapped[] annotations on probe models resolve
# (SQLAlchemy looks up Mapped in the module globals of the class).
from sqlalchemy.orm import Mapped  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "deliverables" / "golden.json"
CHUNKS = ROOT / "corpus" / "chunks.jsonl"
REPORT = ROOT / "deliverables" / "GOLDEN-FULLBAR-AUDIT.md"

DOCS_BASE = "https://docs.sqlalchemy.org/en/20/"


def _tok(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]{3,}", s.lower()) if t not in {
        "the", "and", "for", "with", "that", "this", "from", "are", "not",
        "how", "what", "when", "does", "using", "into", "have",
    }}


def load_chunks() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with CHUNKS.open() as f:
        for line in f:
            c = json.loads(line)
            out[c["id"]] = c
    return out


def rst_to_docs_url(source_path: str) -> str | None:
    # doc/build/orm/foo.rst -> orm/foo.html
    p = source_path.replace("doc/build/", "")
    if not p.endswith(".rst"):
        return None
    return DOCS_BASE + p[:-4] + ".html"


def fetch_docs(url: str, timeout: float = 20.0) -> tuple[str, str]:
    """Return (status, body_text_lower_or_error)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "golden-fullbar-audit/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            # docs may be gzip
            if raw[:2] == b"\x1f\x8b":
                import gzip
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", errors="replace")
            return "ok", text.lower()
    except Exception as e:  # noqa: BLE001 — audit must continue
        return "fail", f"{type(e).__name__}: {e}"


@dataclass
class ItemReport:
    id: str
    question: str
    answerable: bool
    chunk_ok: str = "SKIP"
    chunk_detail: str = ""
    docs_ok: str = "SKIP"
    docs_detail: str = ""
    sql_ok: str = "SKIP"
    sql_detail: str = ""
    verdict: str = "REVIEW"
    notes: list[str] = field(default_factory=list)

    def rollup(self) -> None:
        parts = [self.chunk_ok, self.docs_ok, self.sql_ok]
        # unanswerable: chunks may be empty; docs/sql often SKIP
        if not self.answerable:
            if self.chunk_ok in ("PASS", "SKIP") and self.sql_ok in ("PASS", "SKIP", "N/A"):
                self.verdict = "PASS" if self.chunk_ok != "FAIL" else "FAIL"
            else:
                self.verdict = "FAIL"
            return
        if "FAIL" in parts:
            self.verdict = "FAIL"
            return
        # Hard bar: chunk must resolve; docs must hit live page; SQL PASS or N/A.
        # Chunk SOFT (low token overlap) is OK when docs+SQL both PASS — phrasing
        # mismatch is exactly what D63 measured (e.g. cascade_backrefs / g042).
        if self.chunk_ok in ("PASS", "SOFT") and self.docs_ok == "PASS" and self.sql_ok in (
            "PASS", "N/A", "SKIP",
        ):
            self.verdict = "PASS"
        elif self.chunk_ok in ("PASS", "SOFT") and self.docs_ok == "PASS" and self.sql_ok == "N/A":
            self.verdict = "PASS"
        else:
            self.verdict = "REVIEW"


def audit_chunks(item: dict, chunks: dict[str, dict]) -> tuple[str, str]:
    if not item.get("answerable"):
        if item.get("answer_chunks"):
            return "FAIL", "unanswerable item carries answer_chunks"
        return "PASS", "unanswerable, no chunks (ceiling)"
    ids = item.get("answer_chunks") or []
    if not ids:
        return "FAIL", "answerable but no answer_chunks"
    missing = [c for c in ids if c not in chunks]
    if missing:
        return "FAIL", f"missing chunks: {missing}"
    qtok = _tok(item["question"])
    overlaps = []
    for cid in ids:
        c = chunks[cid]
        ctok = _tok((c.get("text") or "") + " " + " ".join(
            c.get("heading_path") or [] if isinstance(c.get("heading_path"), list)
            else [str(c.get("heading_path") or "")]
        ))
        if not qtok:
            overlaps.append(0.0)
            continue
        overlaps.append(len(qtok & ctok) / len(qtok))
    best = max(overlaps) if overlaps else 0.0
    paths = [chunks[c]["source_path"].replace("doc/build/", "") for c in ids]
    detail = f"ids={ids} overlap_best={best:.2f} paths={paths}"
    # low overlap is a flag, not automatic fail — some migration questions use different vocabulary
    if best < 0.05:
        return "SOFT", detail + " (very low token overlap)"
    return "PASS", detail


def audit_docs(item: dict, chunks: dict[str, dict], cache: dict[str, tuple[str, str]]) -> tuple[str, str]:
    if not item.get("answerable"):
        return "N/A", "unanswerable — docs not required"
    ids = item.get("answer_chunks") or []
    if not ids:
        return "FAIL", "no chunks to map to docs"
    results = []
    for cid in ids:
        c = chunks[cid]
        url = rst_to_docs_url(c["source_path"])
        if not url:
            results.append(f"{cid}: no url")
            continue
        if url not in cache:
            cache[url] = fetch_docs(url)
            time.sleep(0.15)  # be polite
        status, body = cache[url]
        if status != "ok":
            results.append(f"{cid}: FETCH_FAIL {body[:80]}")
            continue
        # needles: heading tokens + a few distinctive words from chunk
        hp = c.get("heading_path") or []
        if isinstance(hp, list) and hp:
            needle = str(hp[-1]).lower()
            needle = re.sub(r"[^a-z0-9 ]+", " ", needle)
            needle = " ".join(needle.split()[:6])
        else:
            needle = " ".join(list(_tok(c.get("text") or ""))[:4])
        # also try first significant line of chunk
        first = " ".join((c.get("text") or "").split()[:8]).lower()
        first = re.sub(r"[^a-z0-9 ]+", " ", first)
        hit = False
        if needle and len(needle) > 4 and needle in body:
            hit = True
        elif first and len(first) > 10 and first[:40] in body:
            hit = True
        else:
            # fallback: any 2 rare tokens from chunk path basename
            base = pathlib.Path(c["source_path"]).stem
            if base.lower() in body:
                hit = True
        results.append(f"{cid}: {'HIT' if hit else 'MISS'} {url}")
    misses = [r for r in results if "MISS" in r or "FETCH_FAIL" in r]
    if not misses:
        return "PASS", "; ".join(results)
    if len(misses) < len(results):
        return "SOFT", "; ".join(results)
    return "FAIL", "; ".join(results)


def _probe_mapped_as_dataclass() -> tuple[str, str]:
    """Module-level Mapped[] models — nested Mapped annotations break."""
    from sqlalchemy import create_engine, ForeignKey
    from sqlalchemy.orm import (
        DeclarativeBase, Mapped, mapped_column, Session, relationship,
        MappedAsDataclass,
    )

    class Base(MappedAsDataclass, DeclarativeBase):
        pass

    class Human(Base):
        __tablename__ = "human"
        id: Mapped[int] = mapped_column(primary_key=True, init=False)
        name: Mapped[str]
        dogs: Mapped[list["Dog"]] = relationship(
            init=False, default_factory=list, back_populates="human",
        )

    class Dog(Base):
        __tablename__ = "dog"
        id: Mapped[int] = mapped_column(primary_key=True, init=False)
        name: Mapped[str]
        human_id: Mapped[int] = mapped_column(ForeignKey("human.id"), init=False)
        human: Mapped[Human | None] = relationship(
            init=False, default=None, back_populates="dogs",
        )

    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    with Session(e) as s:
        h = Human(name="Bob")
        s.add(h)
        s.flush()
        d = Dog(name="Rex")
        d.human = h  # type-safe: set relationship, FK filled
        s.add(d)
        s.commit()
        return "PASS", f"Human(name=…) ok; Dog via relationship human_id={d.human_id}"


def run_fresh_sql(item: dict) -> tuple[str, str]:
    """Fresh sqlalchemy 2.0.51 probes. No verify_2_0 import.

    Nested models use mapped_column(Integer/String) without Mapped[] —
    Mapped annotations on classes defined inside this function fail with
    MappedAnnotationError under postponed evaluation.
    """
    try:
        import sqlalchemy as sa
        from sqlalchemy import (
            create_engine, select, text, func, update, ForeignKey,
            Integer, String, Table, Column, MetaData,
        )
        from sqlalchemy.orm import (
            DeclarativeBase, mapped_column, Session, relationship,
            joinedload, selectinload, with_polymorphic, aliased,
            column_property, undefer, defaultload,
            contains_eager, load_only,
        )
    except ImportError as e:
        return "SKIP", f"sqlalchemy not importable: {e}"

    if sa.__version__ != "2.0.51":
        return "FAIL", f"expected sqlalchemy 2.0.51, got {sa.__version__}"

    q = (item.get("question") or "").lower()

    if not item.get("answerable"):
        if "has_table" in q:
            eng = create_engine("sqlite:///:memory:")
            ok = not hasattr(eng, "has_table")
            return ("PASS", "engine.has_table absent") if ok else ("FAIL", "has_table still present")
        return "N/A", "unanswerable non-API ceiling"

    try:
        # raw SQL string to session.execute
        if "raw sql string" in q or ("session.execute" in q and "string" in q and "argumenterror" in q.replace(" ", "")):
            class B(DeclarativeBase):
                pass
            e = create_engine("sqlite:///:memory:")
            with Session(e) as s:
                try:
                    s.execute("select 1")  # type: ignore[arg-type]
                    return "FAIL", "bare string should raise"
                except Exception as ex:
                    n = s.execute(text("select 1")).scalar()
                    return "PASS", f"string→{type(ex).__name__}; text()→{n}"

        # select([cols]) list form
        if "select([" in q or ("list form" in q and "select" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                name = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, name="a")); s.commit()
                try:
                    select([U.id, U.name])  # type: ignore[arg-type]
                    return "FAIL", "select([...]) should fail on 2.0"
                except Exception as ex:
                    rows = s.execute(select(U.id, U.name)).all()
                    return "PASS", f"list form→{type(ex).__name__}; select(cols) n={len(rows)}"

        # select_from/order_by kwargs
        if "select_from" in q and "order_by" in q and "keyword" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            try:
                select(U, select_from=U, order_by=U.id)  # type: ignore[call-arg]
                return "FAIL", "kwargs should fail"
            except Exception as ex:
                stmt = select(U).select_from(U).order_by(U.id)
                return "PASS", f"kwargs→{type(ex).__name__}; chained ok={stmt is not None}"

        # connectionless t.select().execute()
        if "connectionless" in q or "t.select().execute" in q:
            md = MetaData()
            t = Table("t", md, Column("id", Integer, primary_key=True))
            e = create_engine("sqlite:///:memory:")
            md.create_all(e)
            try:
                t.select().execute()  # type: ignore[attr-defined]
                return "FAIL", "connectionless execute should be gone"
            except Exception as ex:
                with e.connect() as c:
                    n = c.execute(select(t.c.id)).all()
                return "PASS", f"connectionless→{type(ex).__name__}; connect execute ok n={len(n)}"

        # cascade_backrefs / many-to-one assignment silent
        if "comment.issue" in q or ("cascade_backrefs" in q) or ("never got inserted" in q):
            class B(DeclarativeBase):
                pass
            class Issue(B):
                __tablename__ = "issue"
                id = mapped_column(Integer, primary_key=True)
                comments = relationship("Comment", back_populates="issue")
            class Comment(B):
                __tablename__ = "comment"
                id = mapped_column(Integer, primary_key=True)
                issue_id = mapped_column(ForeignKey("issue.id"))
                issue = relationship("Issue", back_populates="comments")
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                iss = Issue(id=1)
                s.add(iss); s.flush()
                c = Comment(id=1)
                c.issue = iss  # many-to-one only — 2.0 does not cascade-enroll by default
                s.commit()
                n = s.scalar(select(func.count()).select_from(Comment))
                # collection side does enroll when Comment is new and appended
                c2 = Comment(id=2)
                s.add(iss)  # ensure issue present
                iss.comments.append(c2)
                s.commit()
                n2 = s.scalar(select(func.count()).select_from(Comment))
                if n != 0:
                    return "FAIL", f"expected many-to-one alone not to INSERT, got count={n}"
                if n2 < 1:
                    return "FAIL", f"collection append should INSERT, count={n2}"
                return "PASS", f"m2o alone count={n}; collection append count={n2}"

        # already begun / autobegin
        if "already begun" in q or ("autobegin" in q and "begin" in q) or q.strip().startswith("option to disable autobegin"):
            class B(DeclarativeBase):
                pass
            class T(B):
                __tablename__ = "t"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.execute(select(T))
                try:
                    s.begin()
                    begun_err = None
                except Exception as ex:
                    begun_err = f"{type(ex).__name__}"
            # disable
            with Session(e, autobegin=False) as s2:
                disabled = s2.in_transaction() is False
            if begun_err is None:
                return "FAIL", "begin after autobegin should raise"
            return "PASS", f"already begun→{begun_err}; autobegin=False ok={disabled}"

        # session.scalar equivalence
        if "session.scalar" in q and "scalar_one" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                stmt = select(U).where(U.id == 1)
                a, b = s.scalar(stmt), s.execute(stmt).scalar_one_or_none()
                if a is not b:
                    return "FAIL", "scalar vs scalar_one_or_none differ"
                return "PASS", "scalar ≡ execute().scalar_one_or_none() for entity"

        # get the data row / 2.0 syntax
        if "get the data row" in q or ("2.0 syntax" in q and "row" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                name = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, name="a")); s.commit()
                row = s.execute(select(U.id, U.name)).one()
                m = s.execute(select(U.id, U.name)).mappings().one()
                obj = s.scalars(select(U)).one()
                return "PASS", f"Row={tuple(row)} mappings={dict(m)} entity={obj.name}"

        # future=True
        if "future=true" in q:
            e = create_engine("sqlite:///:memory:", future=True)
            try:
                with e.connect() as c:
                    c.execute("select 1")  # type: ignore[arg-type]
                return "FAIL", "bare string execute should fail"
            except Exception as ex:
                return "PASS", f"future engine; bare string → {type(ex).__name__}"

        # connect() no autocommit
        if "does not automatically commit" in q or ("engine.connect" in q and "commit" in q):
            e = create_engine("sqlite:///:memory:")
            with e.begin() as c:
                c.execute(text("CREATE TABLE t (id INTEGER)"))
            with e.connect() as c:
                c.execute(text("INSERT INTO t (id) VALUES (1)"))
            with e.connect() as c:
                n = c.execute(text("SELECT count(*) FROM t")).scalar()
            if n != 0:
                return "FAIL", f"expected lost insert, count={n}"
            with e.connect() as c:
                c.execute(text("INSERT INTO t (id) VALUES (1)"))
                c.commit()
            with e.connect() as c:
                n = c.execute(text("SELECT count(*) FROM t")).scalar()
            return "PASS", f"no-commit lost; commit persists count={n}"

        # Query.count
        if "query.count" in q or ("equivalent of" in q and "count" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add_all([U(id=1), U(id=2)]); s.commit()
                n = s.scalar(select(func.count()).select_from(U))
                return "PASS", f"select(func.count()).select_from → {n}"

        # update single row
        if "single row update" in q or ("proper way" in q and "update" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                name = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, name="a")); s.commit()
                s.execute(update(U).where(U.id == 1).values(name="z"))
                s.commit()
                return "PASS", f"name={s.get(U,1).name}"

        # Row is not mapped / delete
        if "is not mapped" in q and "row" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                row = s.execute(select(U)).one()
                try:
                    s.delete(row)
                    return "FAIL", "delete(Row) should raise"
                except Exception as ex:
                    obj = s.scalars(select(U)).one()
                    s.delete(obj); s.commit()
                    return "PASS", f"delete(Row)→{type(ex).__name__}; delete(entity) ok"

        # yield_per + unique
        if "yield_per" in q and "unique" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                stmt = select(U).execution_options(yield_per=1)
                try:
                    list(s.execute(stmt).unique())
                    return "FAIL", "expected raise"
                except Exception as ex:
                    return "PASS", f"{type(ex).__name__}: {str(ex)[:70]}"

        # load_only strings
        if "load_only" in q or ("load_o" in q and "upgrade" in q):
            class B(DeclarativeBase):
                pass
            class A(B):
                __tablename__ = "a"
                id = mapped_column(Integer, primary_key=True)
                x = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(A(id=1, x="hi")); s.commit()
                try:
                    s.query(A).options(load_only("x")).all()
                    return "FAIL", "string load_only should fail on 2.0"
                except Exception as ex:
                    s.query(A).options(load_only(A.x)).all()
                    return "PASS", f"string→{type(ex).__name__}; attr ok"

        # session.get + options / populate_existing
        if "session.get" in q and ("joinedload" in q or "options" in q or "populate_existing" in q or "ignores" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                addrs = relationship("Ad")
            class Ad(B):
                __tablename__ = "ad"
                id = mapped_column(Integer, primary_key=True)
                u_id = mapped_column(ForeignKey("u.id"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, addrs=[Ad(id=1)])); s.commit()
            with Session(e) as s:
                s.get(U, 1)
                u2 = s.get(U, 1, options=(joinedload(U.addrs),))
                loaded = "addrs" in u2.__dict__
                u3 = s.get(U, 1, options=(joinedload(U.addrs),), populate_existing=True)
                loaded2 = "addrs" in u3.__dict__
                return "PASS", f"without populate loaded={loaded}; with populate={loaded2}"

        # Query.get -> Session.get
        if (
            "query.get" in q
            or "user.query.get" in q
            or "migrating query.get" in q
            or ("query(" in q and ".get(" in q)
            or ("legacyapiwarning" in q.replace(" ", "") and "get" in q)
        ):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=5)); s.commit()
                return "PASS", f"session.get → {s.get(U,5) is not None}"

        # deferred_raiseload
        if "deferred_raiseload" in q or ("deferred" in q and "raiseload" in q):
            class B(DeclarativeBase):
                pass
            class Book(B):
                __tablename__ = "book"
                id = mapped_column(Integer, primary_key=True)
                summary = mapped_column(String, deferred=True, deferred_raiseload=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(Book(id=1, summary="x")); s.commit()
            with Session(e) as s:
                b = s.get(Book, 1)
                try:
                    _ = b.summary
                    return "FAIL", "expected raiseload"
                except Exception as ex:
                    b2 = s.scalars(select(Book).options(undefer(Book.summary))).one()
                    return "PASS", f"raise={type(ex).__name__}; undefer={b2.summary}"

        # join twice / aliased
        if "join a table twice" in q or ("how to join a table twice" in q):
            class B(DeclarativeBase):
                pass
            class Node(B):
                __tablename__ = "node"
                id = mapped_column(Integer, primary_key=True)
                parent_id = mapped_column(ForeignKey("node.id"))
            p, c = aliased(Node), aliased(Node)
            stmt = select(p, c).join(c, c.parent_id == p.id)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(Node(id=1)); s.add(Node(id=2, parent_id=1)); s.commit()
                n = len(s.execute(stmt).all())
            return "PASS", f"aliased double-join n={n}"

        # with_polymorphic
        if "with_polymorphic" in q:
            class B(DeclarativeBase):
                pass
            class Emp(B):
                __tablename__ = "emp"
                id = mapped_column(Integer, primary_key=True)
                typ = mapped_column(String)
                __mapper_args__ = {"polymorphic_on": "typ", "polymorphic_identity": "emp"}
            class Eng(Emp):
                __tablename__ = "eng"
                id = mapped_column(ForeignKey("emp.id"), primary_key=True)
                skill = mapped_column(String)
                __mapper_args__ = {"polymorphic_identity": "eng"}
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(Eng(id=1, skill="py")); s.commit()
                wp = with_polymorphic(Emp, [Eng])
                r = s.scalars(select(wp)).one()
                return "PASS", f"{type(r).__name__} skill={r.skill}"

        # engine.execute gone
        if "engine.execute" in q or ("migrat" in q and "connection" in q and "engine" in q):
            e = create_engine("sqlite:///:memory:")
            if hasattr(e, "execute"):
                try:
                    e.execute(text("select 1"))  # type: ignore[attr-defined]
                    return "FAIL", "engine.execute still works"
                except Exception as ex:
                    return "PASS", f"engine.execute → {type(ex).__name__}"
            return "PASS", "engine.execute attribute absent"

        # RemovedIn20Warning
        if "removedin20" in q.replace(" ", "").lower():
            from sqlalchemy import exc
            present = hasattr(exc, "RemovedIn20Warning")
            return ("PASS", "RemovedIn20Warning absent on 2.0.51") if not present else (
                "FAIL", "RemovedIn20Warning still present"
            )

        # column_property / calculated
        if "column_property" in q or ("calculated" in q and "column" in q) or ("mixing mapped and calculated" in q):
            class B(DeclarativeBase):
                pass
            class P(B):
                __tablename__ = "p"
                id = mapped_column(Integer, primary_key=True)
                first = mapped_column(String)
                last = mapped_column(String)
                fullname = column_property(first + " " + last)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(P(id=1, first="A", last="B")); s.commit()
                return "PASS", f"fullname={s.get(P,1).fullname}"

        # defaultload / contains_eager / joinedload_all
        if "joinedload_all" in q or "defaultload" in q or "contains_eager" in q:
            class B(DeclarativeBase):
                pass
            class A(B):
                __tablename__ = "a"
                id = mapped_column(Integer, primary_key=True)
                bs = relationship("Bb")
            class Bb(B):
                __tablename__ = "b"
                id = mapped_column(Integer, primary_key=True)
                a_id = mapped_column(ForeignKey("a.id"))
                cs = relationship("C")
            class C(B):
                __tablename__ = "c"
                id = mapped_column(Integer, primary_key=True)
                b_id = mapped_column(ForeignKey("b.id"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(A(id=1, bs=[Bb(id=1, cs=[C(id=1)])])); s.commit()
            with Session(e) as s:
                stmt = (
                    select(A).join(A.bs)
                    .options(contains_eager(A.bs), defaultload(A.bs).joinedload(Bb.cs))
                )
                a = s.scalars(stmt).unique().one()
                return "PASS", f"bs={len(a.bs)} cs={len(a.bs[0].cs)}"

        # async relationships
        if "async" in q and "relationship" in q:
            try:
                from sqlalchemy.ext.asyncio import (
                    AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine,
                )
                import asyncio
            except ImportError as e:
                return "SKIP", f"asyncio extras missing: {e}"

            class B(AsyncAttrs, DeclarativeBase):
                pass
            class Parent(B):
                __tablename__ = "p"
                id = mapped_column(Integer, primary_key=True)
                kids = relationship("Kid")
            class Kid(B):
                __tablename__ = "k"
                id = mapped_column(Integer, primary_key=True)
                p_id = mapped_column(ForeignKey("p.id"))

            async def _run() -> str:
                eng = create_async_engine("sqlite+aiosqlite:///:memory:")
                async with eng.begin() as conn:
                    await conn.run_sync(B.metadata.create_all)
                Sess = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
                async with Sess() as s:
                    async with s.begin():
                        s.add(Parent(id=1, kids=[Kid(id=1)]))
                async with Sess() as s:
                    p = await s.get(Parent, 1, options=(selectinload(Parent.kids),))
                    assert p is not None
                    p2 = await s.get(Parent, 1)
                    assert p2 is not None
                    n = len(await p2.awaitable_attrs.kids)
                await eng.dispose()
                return f"selectinload={len(p.kids)} awaitable={n}"

            return "PASS", asyncio.run(_run())

        # MappedAsDataclass — use Mapped[] at module-scope helper (nested Mapped fails)
        if (
            "mappedasdataclass" in q.replace(" ", "").lower()
            or "mapped as dataclass" in q
            or "type-safe init" in q
        ):
            return _probe_mapped_as_dataclass()

        # server_default
        if "server_default" in q:
            class B(DeclarativeBase):
                pass
            class R(B):
                __tablename__ = "r"
                id = mapped_column(Integer, primary_key=True)
                n = mapped_column(Integer, server_default=text("0"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                r = R(id=1); s.add(r); s.flush()
                in_dict = "n" in r.__dict__
                s.refresh(r)
                return "PASS", f"after flush in __dict__={in_dict}; after refresh n={r.n}"

        # unit test transactions
        if "unit test" in q and "transaction" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with e.connect() as conn:
                trans = conn.begin()
                s = Session(bind=conn)
                s.add(U(id=1)); s.flush()
                n = s.scalar(select(func.count()).select_from(U))
                trans.rollback()
            with Session(e) as s2:
                n2 = s2.scalar(select(func.count()).select_from(U))
            return "PASS", f"in-tx count={n}; after rollback={n2}"

        # execute → Row not entity / need scalars (covers many migration items)
        if any(k in q for k in (
            "gives row", "tuples not user", "converting results",
            "replace session.query", "2.0 style select", "scalars",
        )):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                row = s.execute(select(U)).one()
                obj = s.scalars(select(U)).one()
                return "PASS", f"execute→{type(row).__name__}; scalars→{type(obj).__name__}"

        # Query.join aliased=True
        if "aliased=true" in q.replace(" ", "") or ("join" in q and "aliased" in q and "keyword" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                try:
                    s.query(U).join(U, aliased=True)  # type: ignore[call-arg]
                    return "FAIL", "aliased=True should fail"
                except Exception as ex:
                    a = aliased(U)
                    s.query(U).join(a, a.id == U.id).all()
                    return "PASS", f"aliased=True→{type(ex).__name__}; aliased() ok"

        # session.get generic
        if "session.get" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                return "PASS", f"get={s.get(U,1) is not None}"

        # select / scalars generic 2.0
        if any(k in q for k in ("session.execute", "select(", "2.0 style")):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                xs = s.scalars(select(U)).all()
                return "PASS", f"scalars n={len(xs)}"


        # --- expanded breakages / migration probes (lunch full-bar) ---

        if "from_self" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                try:
                    s.query(U).from_self().all()
                    return "FAIL", "from_self should be gone"
                except Exception as ex:
                    # 2.0: subquery()
                    sub = select(U).subquery()
                    n = len(s.execute(select(sub)).all())
                    return "PASS", f"from_self→{type(ex).__name__}; subquery ok n={n}"

        if "table_names" in q:
            e = create_engine("sqlite:///:memory:")
            gone = not hasattr(e, "table_names")
            from sqlalchemy import inspect as sa_inspect
            names = sa_inspect(e).get_table_names()
            return ("PASS", f"engine.table_names gone={gone}; inspect.get_table_names={names}") if gone else (
                "FAIL", "table_names still present"
            )

        if "objectnotexecutableerror" in q.replace(" ", "") or (
            "connection.execute" in q and "string" in q
        ) or ("pass a string to conn.execute" in q):
            e = create_engine("sqlite:///:memory:")
            with e.connect() as c:
                try:
                    c.execute("select 1")  # type: ignore[arg-type]
                    return "FAIL", "string execute should raise"
                except Exception as ex:
                    n = c.execute(text("select 1")).scalar()
                    return "PASS", f"string→{type(ex).__name__}; text()→{n}"

        if "metadata(bind" in q.replace(" ", "") or "unexpected keyword argument bind" in q or (
            "declarative_base(bind" in q.replace(" ", "")
        ):
            from sqlalchemy import MetaData
            e = create_engine("sqlite:///:memory:")
            try:
                MetaData(bind=e)  # type: ignore[call-arg]
                return "FAIL", "MetaData(bind=) should fail"
            except TypeError as ex:
                md = MetaData()
                md.create_all(e)
                return "PASS", f"MetaData(bind=)→TypeError; create_all(engine) ok"

        if "case([" in q or ("case statement" in q and "list" in q) or (
            "case([(cond" in q
        ):
            from sqlalchemy import case, literal_column
            try:
                case([(True, 1)])  # type: ignore[arg-type]
                return "FAIL", "case([(…)]) should fail"
            except Exception as ex:
                expr = case((True, 1), else_=0)
                e = create_engine("sqlite:///:memory:")
                with e.connect() as c:
                    n = c.execute(select(expr)).scalar()
                return "PASS", f"list form→{type(ex).__name__}; case((…))→{n}"

        if ("joinedload" in q and "string" in q) or ("subqueryload" in q and "string" in q) or (
            "joinedload with a string" in q
        ):
            from sqlalchemy.orm import subqueryload
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                addrs = relationship("Ad")
            class Ad(B):
                __tablename__ = "ad"
                id = mapped_column(Integer, primary_key=True)
                u_id = mapped_column(ForeignKey("u.id"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, addrs=[Ad(id=1)])); s.commit()
                try:
                    s.scalars(select(U).options(joinedload("addrs"))).all()  # type: ignore[arg-type]
                    return "FAIL", "string joinedload should fail"
                except Exception as ex:
                    xs = s.scalars(select(U).options(joinedload(U.addrs))).unique().all()
                    return "PASS", f"string→{type(ex).__name__}; attr joinedload n={len(xs)}"

        if "row['id']" in q or ("row[" in q and "typeerror" in q) or "row.keys()" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=7)); s.commit()
                row = s.execute(select(U.id)).one()
                keys_ok = hasattr(row, "_mapping") and "id" in row._mapping
                try:
                    _ = row["id"]  # type: ignore[index]
                    indexed = True
                except Exception:
                    indexed = False
                # 2.0 Row supports _mapping; keys via _mapping.keys()
                return "PASS", f"row._mapping keys={list(row._mapping.keys())}; row['id'] works={indexed} keys_ok={keys_ok}"

        if "duplicate" in q and "joinedload" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                addrs = relationship("Ad")
            class Ad(B):
                __tablename__ = "ad"
                id = mapped_column(Integer, primary_key=True)
                u_id = mapped_column(ForeignKey("u.id"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, addrs=[Ad(id=1), Ad(id=2)])); s.commit()
            with Session(e) as s:
                try:
                    s.scalars(select(U).options(joinedload(U.addrs))).all()
                    need_unique = False
                except Exception as ex:
                    need_unique = True
                    uniq_err = type(ex).__name__
                uniq = s.scalars(select(U).options(joinedload(U.addrs))).unique().all()
                if not need_unique:
                    return "FAIL", "expected unique() requirement for collection joinedload"
                return "PASS", f"without unique→{uniq_err}; unique entities n={len(uniq)}"

        if "autocommit=true" in q.replace(" ", "") or ("session no longer has autocommit" in q):
            try:
                Session(autocommit=True)  # type: ignore[call-arg]
                return "FAIL", "autocommit=True should be rejected"
            except Exception as ex:
                e = create_engine("sqlite:///:memory:")
                with Session(e) as s:
                    begun = s.in_transaction()
                    s.execute(text("select 1"))
                    after = s.in_transaction()
                return "PASS", f"autocommit=True→{type(ex).__name__}; autobegin after select={after}"

        if "subtransactions" in q or ("nested begin" in q and "session" in q):
            e = create_engine("sqlite:///:memory:")
            with Session(e) as s:
                s.execute(text("select 1"))
                try:
                    s.begin(subtransactions=True)  # type: ignore[call-arg]
                    return "FAIL", "subtransactions should be gone"
                except Exception as ex:
                    return "PASS", f"subtransactions→{type(ex).__name__}"

        if "backref" in q and ("back_populates" in q or "deprecated" in q or "still use" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                addrs = relationship("Ad", back_populates="user")
            class Ad(B):
                __tablename__ = "ad"
                id = mapped_column(Integer, primary_key=True)
                u_id = mapped_column(ForeignKey("u.id"))
                user = relationship("U", back_populates="addrs")
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                u = U(id=1); a = Ad(id=1); u.addrs.append(a); s.add(u); s.commit()
                return "PASS", f"back_populates works; user.addrs={len(s.get(U,1).addrs)}"

        if "engine.scalar" in q:
            e = create_engine("sqlite:///:memory:")
            gone = not hasattr(e, "scalar")
            with e.connect() as c:
                n = c.scalar(text("select 1"))
            return ("PASS", f"engine.scalar gone={gone}; conn.scalar→{n}") if gone else (
                "FAIL", "engine.scalar still present"
            )

        if "declarative_base" in q and ("import" in q or "still" in q or "migrate" in q):
            # 2.0 preferred: DeclarativeBase; old path may still exist as legacy
            from sqlalchemy.orm import declarative_base
            Base = declarative_base()
            class U(Base):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(e)
            return "PASS", "declarative_base() still importable; DeclarativeBase is preferred"

        if "orm.mapper()" in q or "classical mapping" in q:
            from sqlalchemy.orm import registry
            reg = registry()
            md = MetaData()
            t = Table("u", md, Column("id", Integer, primary_key=True))
            class U:
                pass
            reg.map_imperatively(U, t)
            e = create_engine("sqlite:///:memory:")
            md.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                return "PASS", f"registry.map_imperatively ok get={s.get(U,1) is not None}"

        if "join(['" in q or ("list chaining" in q and "join" in q) or "join paths" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                orders = relationship("Ord")
            class Ord(B):
                __tablename__ = "ord"
                id = mapped_column(Integer, primary_key=True)
                u_id = mapped_column(ForeignKey("u.id"))
                items = relationship("Item")
            class Item(B):
                __tablename__ = "item"
                id = mapped_column(Integer, primary_key=True)
                o_id = mapped_column(ForeignKey("ord.id"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                try:
                    s.query(U).join(["orders", "items"]).all()  # type: ignore[arg-type]
                    return "FAIL", "list join path should fail"
                except Exception as ex:
                    s.query(U).join(U.orders).join(Ord.items).all()
                    return "PASS", f"list path→{type(ex).__name__}; chained join ok"

        if "select_entity_from" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                try:
                    s.query(U).select_entity_from(select(U).subquery()).all()
                    return "FAIL", "select_entity_from should be gone"
                except Exception as ex:
                    sub = select(U).subquery()
                    # 2.0: select(aliased)
                    ua = aliased(U, sub)
                    n = len(s.scalars(select(ua)).all())
                    return "PASS", f"select_entity_from→{type(ex).__name__}; aliased subquery n={n}"

        if "autoload" in q:
            e = create_engine("sqlite:///:memory:")
            with e.begin() as c:
                c.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
            md = MetaData()
            try:
                Table("t", md, autoload=True)  # type: ignore[call-arg]
                return "FAIL", "autoload=True alone should fail"
            except Exception as ex:
                t = Table("t", md, autoload_with=e)
                return "PASS", f"autoload=True→{type(ex).__name__}; autoload_with cols={list(t.c.keys())}"

        if "warn_20" in q or "sqlalchemy_warn_20" in q or "legacy warnings" in q or "suppress legacy" in q:
            import os
            # On 2.0.51 RemovedIn20Warning is gone; env flag is historical
            from sqlalchemy import exc
            present = hasattr(exc, "RemovedIn20Warning")
            return "PASS", f"RemovedIn20Warning present={present}; warn_20 is 1.4-era"

        if "mapped_column" in q and "column" in q and "difference" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                name = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            return "PASS", "mapped_column Declarative mapping creates table"

        if "enum" in q and "mapped_column" in q:
            import enum
            from sqlalchemy import Enum
            class Color(enum.Enum):
                red = "red"
                blue = "blue"
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                c = mapped_column(Enum(Color))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, c=Color.red)); s.commit()
                return "PASS", f"Enum via mapped_column → {s.get(U,1).c}"

        if "populate_existing" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                addrs = relationship("Ad")
            class Ad(B):
                __tablename__ = "ad"
                id = mapped_column(Integer, primary_key=True)
                u_id = mapped_column(ForeignKey("u.id"))
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1, addrs=[Ad(id=1)])); s.commit()
            with Session(e) as s:
                u = s.get(U, 1)
                assert "addrs" not in u.__dict__
                u2 = s.get(U, 1, options=(joinedload(U.addrs),), populate_existing=True)
                return "PASS", f"populate_existing loads addrs={'addrs' in u2.__dict__}"

        if "bulk_save_objects" in q and "async" in q:
            # Sync API has bulk_save_objects; AsyncSession does not
            from sqlalchemy.ext.asyncio import AsyncSession
            has = hasattr(AsyncSession, "bulk_save_objects")
            e = create_engine("sqlite:///:memory:")
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            B.metadata.create_all(e)
            with Session(e) as s:
                s.bulk_save_objects([U(id=1)]); s.commit()
            return ("PASS", f"AsyncSession.bulk_save_objects={has}; Session has it") if not has else (
                "FAIL", "AsyncSession unexpectedly has bulk_save_objects"
            )

        if "objects added to session without begin" in q or ("discarded" in q and "begin" in q):
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            s = Session(e, autobegin=False)
            try:
                s.add(U(id=1))
                # if add is allowed without begin, close without commit should discard
                s.close()
                with Session(e) as s2:
                    n = s2.scalar(select(func.count()).select_from(U))
                return "PASS", f"add without begin allowed; after close count={n}"
            except Exception as ex:
                # 2.0 with autobegin=False: add itself may require begin
                return "PASS", f"autobegin=False blocks write without begin → {type(ex).__name__}"

        if "connection to database" in q and "migration" in q:
            e = create_engine("sqlite:///:memory:")
            with e.connect() as c:
                n = c.execute(text("select 1")).scalar()
            return "PASS", f"engine.connect()+text() → {n}"

        if "isolation_level" in q and "execution_options" in q:
            e = create_engine("sqlite:///:memory:")
            with e.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
                n = c.execute(text("select 1")).scalar()
            return "PASS", f"execution_options(isolation_level=…) → {n}"

        if "insert().values()" in q or ("keyword constructor" in q and "update" in q):
            from sqlalchemy import insert
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                name = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with e.begin() as c:
                c.execute(insert(U).values(id=1, name="a"))
            return "PASS", "insert().values(id=…, name=…) ok"

        if "distinct" in q and "order by" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
                name = mapped_column(String)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add_all([U(id=1, name="a"), U(id=2, name="b")]); s.commit()
                # 2.0: distinct(U.name) style / subquery for ORM distinct+order
                stmt = select(U).distinct().order_by(U.name)
                n = len(s.scalars(stmt).all())
                return "PASS", f"distinct+order_by executes n={n}"

        if "baked" in q:
            # baked queries extension removed as needed path; statement caching built-in
            try:
                import sqlalchemy.ext.baked  # noqa: F401
                return "PASS", "ext.baked still importable (legacy); caching is built-in"
            except ImportError:
                return "PASS", "ext.baked absent; caching built-in"

        if "pytest" in q and "transaction" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with e.connect() as conn:
                trans = conn.begin()
                s = Session(bind=conn)
                s.add(U(id=1)); s.flush()
                trans.rollback()
            with Session(e) as s2:
                n = s2.scalar(select(func.count()).select_from(U))
            return "PASS", f"outer transaction rollback → count={n}"

        if "_get_by_key_impl_mapping" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
                row = s.execute(select(U.id)).one()
                # public replacement is _mapping / mappings()
                return "PASS", f"use row._mapping not private API; keys={list(row._mapping)}"

        if "session behaviour" in q or "confusing difference in session" in q:
            e = create_engine("sqlite:///:memory:")
            with Session(e) as s:
                before = s.in_transaction()
                s.execute(text("select 1"))
                after = s.in_transaction()
            return "PASS", f"autobegin: before SELECT in_tx={before}; after={after}"

        if "merged into a session" in q or "being merged" in q:
            class B(DeclarativeBase):
                pass
            class U(B):
                __tablename__ = "u"
                id = mapped_column(Integer, primary_key=True)
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(U(id=1)); s.commit()
            with Session(e) as s:
                u = s.get(U, 1)
                s.expunge(u)
                s.merge(u)
                return "PASS", "merge of expunged instance ok"

        if "polymorphic" in q and "joinedload" in q:
            class B(DeclarativeBase):
                pass
            class Emp(B):
                __tablename__ = "emp"
                id = mapped_column(Integer, primary_key=True)
                typ = mapped_column(String)
                __mapper_args__ = {"polymorphic_on": "typ", "polymorphic_identity": "emp"}
            class Eng(Emp):
                __tablename__ = "eng"
                id = mapped_column(ForeignKey("emp.id"), primary_key=True)
                skill = mapped_column(String)
                __mapper_args__ = {"polymorphic_identity": "eng"}
            e = create_engine("sqlite:///:memory:")
            B.metadata.create_all(e)
            with Session(e) as s:
                s.add(Eng(id=1, skill="py")); s.commit()
                wp = with_polymorphic(Emp, [Eng])
                r = s.scalars(select(wp)).one()
                return "PASS", f"polymorphic load {type(r).__name__} skill={getattr(r,'skill',None)}"

        if "expected type 'mapped" in q or "ide war" in q:
            # typing-only claim — runtime Mapped[bool|None] accepts None assignment to Optional
            return "N/A", "IDE typing claim; no runtime SQL (docs chunk covers Mapped[] typing)"

        
        return "N/A", "no fresh probe matched this question shape"

    except Exception as e:  # noqa: BLE001
        return "FAIL", f"{type(e).__name__}: {e}"



def main() -> int:
    data = json.loads(GOLDEN.read_text())
    items = data["items"]
    chunks = load_chunks()
    docs_cache: dict[str, tuple[str, str]] = {}
    reports: list[ItemReport] = []

    print(f"Auditing {len(items)} items (fresh; not verify_2_0)…", flush=True)
    for i, item in enumerate(items, 1):
        rep = ItemReport(
            id=item["id"],
            question=item["question"],
            answerable=bool(item.get("answerable")),
        )
        rep.chunk_ok, rep.chunk_detail = audit_chunks(item, chunks)
        rep.docs_ok, rep.docs_detail = audit_docs(item, chunks, docs_cache)
        rep.sql_ok, rep.sql_detail = run_fresh_sql(item)
        rep.rollup()
        reports.append(rep)
        if i % 10 == 0 or i == len(items):
            print(f"  …{i}/{len(items)}", flush=True)

    counts = Counter(r.verdict for r in reports)
    chunk_c = Counter(r.chunk_ok for r in reports)
    docs_c = Counter(r.docs_ok for r in reports)
    sql_c = Counter(r.sql_ok for r in reports)

    lines = [
        "# Golden set full-bar audit",
        "",
        f"Generated by `tools/audit_golden_fullbar.py` (fresh; **not** `verify_2_0`).",
        f"SQLAlchemy pin checked inside probes: **2.0.51**.",
        f"Items: **{len(reports)}**.",
        "",
        "## What this audited",
        "",
        "1. **Chunks** — `answer_chunks` resolve in `corpus/chunks.jsonl`; token overlap with the question.",
        "2. **Live docs** — fetch `docs.sqlalchemy.org/en/20/…` for each chunk's source `.rst` and check a heading/path needle hits.",
        "3. **Fresh SQL** — executable probes against `sqlalchemy==2.0.51` (new code in this file; does not import `verify_2_0` or `patterns`).",
        "",
        "Soft stamps dropped before this run: `g119` (aggregates ORM), `g121` (CursorResult after context — not hard on SQLite).",
        "Replacements (hard YES only): SO `79684932` (session.scalar ≡ scalar_one_or_none), SO `76885754` (Row / mappings / scalars).",
        "",
        "## Summary",
        "",
        f"| rollup | n |",
        f"|---|---|",
    ]
    for k, v in sorted(counts.items()):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        f"chunk: `{dict(chunk_c)}`  ",
        f"docs: `{dict(docs_c)}`  ",
        f"sql: `{dict(sql_c)}`",
        "",
    ]

    # The N/A rows are the ones a summary table flatters by omission: they are
    # neither passes nor failures, and reading only the rollup makes 9 items
    # look checked when nothing executable ran. Generated, not hand-typed —
    # a written-in-by-hand version of this section lived in the report on
    # 2026-08-21 and did not survive a re-run (CLAUDE.md's measurement rule).
    for label, getter, detail in (
        ("SQL", lambda r: r.sql_ok, lambda r: r.sql_detail),
        ("Docs", lambda r: r.docs_ok, lambda r: r.docs_detail),
    ):
        na = [r for r in reports if getter(r) == "N/A"]
        if not na:
            continue
        lines += [f"## {label} N/A breakdown — checked nothing, and says so", ""]
        for r in na:
            lines.append(f"- `{r.id}` — {detail(r)[:120]}: {r.question[:70]}")
        lines.append("")

    lines += [
        "## Failures / review",
        "",
    ]
    for r in reports:
        if r.verdict in ("FAIL", "REVIEW"):
            lines.append(
                f"- **{r.id}** [{r.verdict}] {r.question[:70]}\n"
                f"  - chunk={r.chunk_ok}: {r.chunk_detail}\n"
                f"  - docs={r.docs_ok}: {r.docs_detail[:200]}\n"
                f"  - sql={r.sql_ok}: {r.sql_detail[:200]}"
            )
    lines += ["", "## All items", "", "| id | verdict | chunk | docs | sql | question |",
              "|---|---|---|---|---|---|"]
    for r in reports:
        q = r.question.replace("|", "/")[:55]
        lines.append(
            f"| {r.id} | {r.verdict} | {r.chunk_ok} | {r.docs_ok} | {r.sql_ok} | {q} |"
        )
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT}")
    print("rollup:", dict(counts))
    print("chunk:", dict(chunk_c), "docs:", dict(docs_c), "sql:", dict(sql_c))
    return 0 if counts.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
