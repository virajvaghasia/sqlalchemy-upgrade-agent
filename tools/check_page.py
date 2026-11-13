"""The demo page's layout checks, in a headless browser (Phase 6 Step 4c, scripted).

    # terminal 1: serve the page (no model is asked, so any generator setting works)
    PORT=7861 DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. \
        uv run --with fastapi --with uvicorn python space/web.py
    # terminal 2: run the checks against it
    uv run --with playwright==1.62.0 python tools/check_page.py http://127.0.0.1:7861

WHY IT EXISTS

Step 4c's four checks were done by hand in Chrome, and the phone-width bug hid
on the first try: the real answer had no code block, so a page that breaks on
one long code line measured fine. A check whose input could not fail is not a
check. This script feeds the page the inputs that CAN fail.

WHAT IT DOES NOT DO

It asks no model. Each state (answered with a long code line, declined, error)
is a fixed payload in the exact shape `rag.demo.payload()` returns, pushed
through the page's own `renderAnswer` and `renderSources`. So it tests the
page's drawing, not the answers; `tests/test_demo.py` tests the payload.
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7860"
NOTICE = "Answers here are written by `qwen2.5-coder:7b` on Ollama."
LONG = "sqlalchemy.orm.session.Session.get_bind_for_mapper_with_a_very_long_identifier_name_here"
ANSWERED = {
    "status": "answered",
    "status_label": "Answered from the sources",
    "error": None,
    "seconds": 1,
    "generator": "qwen2.5-coder:7b",
    "notice": NOTICE,
    # The comment is absurdly long on purpose. It has to overflow the code panel at DESKTOP as
    # well as on a phone: when the answer column got wider on 2026-09-20 the old 93-character
    # line simply fitted, and a check whose input cannot overflow cannot test overflow.
    "answer_md": (
        f"Use `Session.get` [[1]](#src-1), see {LONG}.\n\n```python\nwith Session(engine) as s:\n"
        "    user = s.get(User, 1)  # a deliberately long comment line that is far wider than a phone,"
        " and wider than the answer column on a large desktop monitor too, which is the point of it\n```"
    ),
}
SOURCES = [
    {
        "n": 1,
        "version": "2.0.51",
        "cited": True,
        "heading": "Session > get",
        "path": "doc/build/orm/some/really/long/path/without/spaces/anywhere/in/it/at/all.rst",
        "text": LONG + "()",
    },
    {"n": 2, "version": "1.4.52", "cited": False, "heading": "Other", "path": "orm/x.rst", "text": "x"},
]
DECLINED = {
    **ANSWERED,
    "status": "declined",
    "status_label": "Declined: ...",
    "answer_md": "The sources do not answer this.",
}
ERROR = {
    **ANSWERED,
    "status": "error",
    "status_label": "Not answered",
    "error": "The local answer model (Ollama) is not running.",
    "answer_md": "",
}

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))


def show(page, payload, sources) -> None:
    page.evaluate(
        "([p, s]) => { document.getElementById('results').hidden = false; renderAnswer(p); renderSources(s); }",
        [payload, sources],
    )


def widths(page) -> dict:
    return page.evaluate("""() => {
        const de = document.documentElement, code = document.querySelector('.md pre code');
        return {page: de.scrollWidth, screen: de.clientWidth,
                code: code ? code.scrollWidth : 0, codeBox: code ? code.clientWidth : 0,
                columns: getComputedStyle(document.getElementById('results')).gridTemplateColumns.split(' ').length};
    }""")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    errors = []
    print(f"DEMO PAGE CHECKS — {URL}")

    for label, size in (
        ("desktop 1280px", {"width": 1280, "height": 900}),
        ("phone 400px", {"width": 400, "height": 860}),
    ):
        page = browser.new_page(viewport=size)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        print(f"\n{label}")
        check(
            "example chips load from /api/config",
            page.locator(".chip").count() == 5,
            f"{page.locator('.chip').count()} chips",
        )

        show(page, ANSWERED, SOURCES)
        w = widths(page)
        check("the page never scrolls sideways", w["page"] <= w["screen"], f"{w['page']} of {w['screen']} px")
        check(
            "a long code line scrolls inside its own box",
            w["code"] > w["codeBox"],
            f"{w['code']} px of code in a {w['codeBox']} px box",
        )
        check(
            "answer and sources " + ("side by side" if size["width"] > 900 else "stacked"),
            w["columns"] == (2 if size["width"] > 900 else 1),
            f"{w['columns']} column(s)",
        )
        notice = page.locator(".notice")
        check(
            "the notice draws the model name as code, no stray backtick",
            notice.locator("code").inner_text() == "qwen2.5-coder:7b" and "`" not in notice.inner_text(),
        )
        page.locator("a.cite").first.click()
        page.wait_for_timeout(300)
        check(
            "clicking [1] opens and highlights source card 1",
            page.evaluate(
                "() => { const c = document.getElementById('src-1'); return c.open && c.classList.contains('flash'); }"
            ),
        )

        show(page, DECLINED, SOURCES)
        check(
            "declined: the pill says Declined, the note shows, no citation links",
            page.locator(".pill.declined").count() == 1
            and page.locator(".declined-note").count() == 1
            and page.locator("a.cite").count() == 0,
        )

        show(page, ERROR, SOURCES)
        check(
            "error: the pill says Not answered, the message shows, sources still listed",
            page.locator(".pill.error").count() == 1
            and "Ollama" in page.locator(".md").inner_text()
            and page.locator(".src").count() == 2,
        )
        page.close()

    # The states only the submit path reaches. /api/ask is answered here, by this script, with
    # the status, header and body the server sends for each case (tests/test_server.py pins
    # those), so every branch runs without a model and without waiting out a real limit.
    print("\nsubmit path, desktop 1280px")
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))
    reply: dict = {}
    calls = []

    def answer_ask(route):
        calls.append(1)
        if reply.get("abort"):
            route.abort()
            return
        route.fulfill(
            status=reply["status"],
            headers={"Content-Type": "application/json", **reply.get("headers", {})},
            body=json.dumps(reply["body"]),
        )

    page.route("**/api/ask", answer_ask)
    page.goto(URL)
    page.wait_for_load_state("networkidle")

    def ask(text: str) -> None:
        page.fill("#q", text)
        page.click("#ask")
        page.wait_for_function("() => !document.getElementById('ask').classList.contains('busy')")

    reply.update(
        status=200, body={**ANSWERED, "sources": SOURCES, "timings": {"retrieve_ms": 2600, "generate_ms": 18400}}
    )
    ask("where did get move to")
    segs = page.locator(".t-seg").evaluate_all("els => els.map(e => e.getBoundingClientRect().width)")
    check(
        "answered: search and writing time are drawn to scale",
        len(segs) == 2 and segs[1] > 5 * segs[0] and "2.6s" in page.locator(".t-labs").inner_text(),
        f"segments {[round(x) for x in segs]} px",
    )

    page.wait_for_timeout(900)  # the smooth scroll to the answer
    top = page.evaluate(
        "() => [document.querySelector('.doc-title').getBoundingClientRect().top,"
        " document.querySelector('.topbar').getBoundingClientRect().bottom]"
    )
    check(
        "after asking, the question's title is below the fixed bar, not under it",
        top[0] >= top[1],
        f"title at {round(top[0])} px, bar ends at {round(top[1])} px",
    )
    title = page.locator(".doc-title").inner_text()
    reply.update(
        status=422, body={**ERROR, "error": "This looks like a greeting.", "code": "not_a_lookup", "sources": []}
    )
    ask("Hello")
    check(
        "rejected question: said in the box, the answer on screen is left alone",
        page.locator("#form-msg").is_visible()
        and "greeting" in page.locator("#form-msg").inner_text()
        and page.locator(".doc-title").inner_text() == title
        and page.locator(".pill.answered").count() == 1,
    )
    page.fill("#q", "Hello again")
    check("rejected question: the message clears on typing", not page.locator("#form-msg").is_visible())

    reply.update(
        status=429,
        headers={"Retry-After": "3"},
        body={**ERROR, "error": "Please wait 3 seconds.", "code": "rate_limited", "sources": SOURCES},
    )
    ask("where did get move to")
    label = page.locator("#ask .label").inner_text()
    check(
        "rate limited: named, counted down, and the button stays shut",
        page.locator(".pill.error").inner_text() == "Too many questions"
        and label.startswith("Wait ")
        and page.locator("#ask").is_disabled()
        and page.locator(".src").count() == 2,
        f"button says {label!r}",
    )
    page.wait_for_function("() => !document.getElementById('ask').disabled", timeout=6000)
    check(
        "rate limited: the button opens again when the wait is over",
        page.locator("#ask .label").inner_text() == "Ask" and "again now" in page.locator(".fail-next").inner_text(),
    )

    reply.update(
        status=503,
        headers={},
        body={**ERROR, "error": "No answer model responded.", "code": "generator_unavailable", "sources": SOURCES},
    )
    ask("where did get move to")
    before = len(calls)
    named = page.locator(".pill.error").inner_text()
    page.click("#retry")
    page.wait_for_function("() => !document.getElementById('ask').classList.contains('busy')")
    check(
        "model unavailable: named, sources listed, Ask again sends the question again",
        named == "The model did not answer" and len(calls) == before + 1 and page.locator(".src").count() == 2,
        f"{len(calls) - before} new request(s)",
    )

    reply.update(abort=True)
    ask("where did get move to")
    check(
        "server unreachable: named, with a way to ask again",
        page.locator(".pill.error").inner_text() == "Server not reached" and page.locator("#retry").count() == 1,
    )
    page.keyboard.press("Tab")
    check(
        "the live region carries the outcome, not the whole answer",
        page.locator("#live").inner_text().startswith("Server not reached")
        and page.get_attribute("#answer", "aria-live") is None,
    )
    page.close()

    check("no JavaScript errors on any page", not errors, "; ".join(errors)[:200])
    browser.close()

print(f"\n{sum(results)} of {len(results)} checks pass")
sys.exit(0 if all(results) else 1)
