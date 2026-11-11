"""The web server: status codes, health checks and the request log. No model, no network.

`rag.demo` decides what an answer is and is covered by tests/test_demo.py. This
file covers what only the server adds: an HTTP status a client or a load balancer
can act on, without changing the JSON body the page already reads.
"""

import json
import logging
import urllib.error

import pytest
from fastapi.testclient import TestClient

from rag import demo, server

Q = "query(User).get(1) warns LegacyAPIWarning, where did get move to"


class Hit:
    payload = {"sqlalchemy_version": "2.0.51", "source_path": "changelog/migration_20.rst",
               "heading_path": ["Migration", "get"], "text": "Session.get replaces Query.get.",
               "chunk_id": "c00001"}


def reply(text):
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture
def client(monkeypatch):
    """A server whose search and model are stand-ins, with a fresh rate limiter."""
    monkeypatch.setattr(server, "LIMITER", demo.RateLimiter())
    monkeypatch.setattr(server, "BACKEND", "nvidia")
    monkeypatch.setattr(server, "_key", lambda: "k")
    monkeypatch.setattr(server, "RETRIEVE", lambda q: [Hit()])
    monkeypatch.setattr(server, "POST", lambda m, k: reply("Use Session.get [1]."))
    return TestClient(server.app)


def test_an_answer_is_200_and_keeps_the_body_the_page_reads(client):
    r = client.post("/api/ask", json={"question": Q, "session": "s1"})
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "answered" and body["sources"][0]["cited"] is True
    assert body["code"] is None
    # The id in the body is the id in the header and in the log line: one request, one name.
    assert body["request_id"] == r.headers["x-request-id"]


def test_a_decline_is_still_200_because_declining_is_a_correct_answer(client, monkeypatch):
    monkeypatch.setattr(server, "POST", lambda m, k: reply("The sources do not answer this."))
    r = client.post("/api/ask", json={"question": Q, "session": "s1"})
    assert r.status_code == 200 and r.json()["status"] == "declined"


def test_an_empty_or_overlong_question_is_422_with_the_page_shaped_body(client):
    for question in ("", "x" * (demo.MAX_QUESTION_CHARS + 1), "hello"):
        r = client.post("/api/ask", json={"question": question, "session": "s"})
        assert r.status_code == 422, question[:10]
        assert r.json()["status"] == "error" and r.json()["error"]


def test_a_rate_limited_visitor_gets_429_a_retry_after_and_still_the_sources(client):
    assert client.post("/api/ask", json={"question": Q, "session": "s1"}).status_code == 200
    r = client.post("/api/ask", json={"question": Q, "session": "s1"})
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= demo.SESSION_MIN_SECONDS
    assert r.json()["code"] == "rate_limited" and r.json()["sources"]


def test_a_failed_model_is_503_and_the_search_results_survive(client, monkeypatch):
    def boom(m, k):
        raise urllib.error.URLError("down")
    monkeypatch.setattr(server, "POST", boom)
    r = client.post("/api/ask", json={"question": Q, "session": "s1"})
    assert r.status_code == 503 and r.json()["code"] == "generator_unavailable"
    assert r.json()["sources"]


def test_a_missing_key_is_503_not_configured(client, monkeypatch):
    monkeypatch.setattr(server, "_key", lambda: None)
    r = client.post("/api/ask", json={"question": Q, "session": "s1"})
    assert r.status_code == 503 and r.json()["code"] == "not_configured"


def test_a_body_that_is_not_the_expected_shape_is_422_not_a_crash(client):
    assert client.post("/api/ask", json={"question": ["not", "a", "string"]}).status_code == 422
    assert client.post("/api/ask", content=b"not json",
                       headers={"content-type": "application/json"}).status_code == 422


def test_healthz_says_the_process_is_up_and_touches_nothing(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_readyz_is_503_until_the_corpus_and_the_generator_are_both_there(client, monkeypatch, tmp_path):
    present = tmp_path / "here"
    present.write_text("x")
    monkeypatch.setattr(server, "CORPUS_FILES", [present])
    assert client.get("/readyz").status_code == 200

    monkeypatch.setattr(server, "CORPUS_FILES", [present, tmp_path / "missing.npy"])
    r = client.get("/readyz")
    assert r.status_code == 503 and r.json()["checks"]["corpus"] is False

    monkeypatch.setattr(server, "CORPUS_FILES", [present])
    monkeypatch.setattr(server, "_key", lambda: None)
    r = client.get("/readyz")
    assert r.status_code == 503 and r.json()["checks"]["generator"] is False


def test_every_request_is_one_json_log_line_without_the_question_text(client, caplog):
    with caplog.at_level(logging.INFO, logger="sqla_upgrade.request"):
        r = client.post("/api/ask", json={"question": Q, "session": "s1"})
    lines = [json.loads(rec.getMessage()) for rec in caplog.records
             if rec.name == "sqla_upgrade.request"]
    assert len(lines) == 1
    line = lines[0]
    assert line["request_id"] == r.headers["x-request-id"]
    assert line["status"] == 200 and line["outcome"] == "answered"
    assert line["question_chars"] == len(Q)
    assert set(line) >= {"retrieve_ms", "generate_ms", "total_ms", "model", "sources"}
    # A visitor's question can hold their code. Its length is logged; its text is not.
    assert Q not in json.dumps(line)


def test_the_page_and_its_config_are_served(client):
    assert client.get("/").status_code == 200
    cfg = client.get("/api/config").json()
    assert len(cfg["examples"]) == 5 and cfg["max_chars"] == demo.MAX_QUESTION_CHARS


def test_importing_the_server_does_not_switch_the_search_path(monkeypatch):
    """The server searches in memory; every measurement searches Qdrant. The switch
    is an environment variable, so setting it at import would silently move any
    test that runs after this file onto a different index."""
    import importlib
    import os

    from rag.index import DENSE_ENV
    monkeypatch.delenv(DENSE_ENV, raising=False)
    importlib.reload(server)
    assert DENSE_ENV not in os.environ
    with TestClient(server.app):                  # starting the server is what sets it
        assert os.environ[DENSE_ENV] == "memory"
    monkeypatch.delenv(DENSE_ENV, raising=False)
