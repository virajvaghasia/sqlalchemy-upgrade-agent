"""The demo page's layout checks, in a headless browser (Phase 6 Step 4c, scripted).

    uv run --with playwright==1.62.0 python .claude/skills/webapp-testing/scripts/with_server.py \
        --timeout 90 --server "PORT=7861 DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. \
        uv run --with fastapi --with uvicorn python space/web.py" --port 7861 \
        -- uv run --with playwright==1.62.0 python tools/check_page.py http://127.0.0.1:7861

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

import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7860"
NOTICE = "Answers here are written by `qwen2.5-coder:7b` on Ollama."
LONG = "sqlalchemy.orm.session.Session.get_bind_for_mapper_with_a_very_long_identifier_name_here"
ANSWERED = {
    "status": "answered", "status_label": "Answered from the sources", "error": None, "seconds": 1,
    "generator": "qwen2.5-coder:7b", "notice": NOTICE,
    # The comment is absurdly long on purpose. It has to overflow the code panel at DESKTOP as
    # well as on a phone: when the answer column got wider on 2026-09-20 the old 93-character
    # line simply fitted, and a check whose input cannot overflow cannot test overflow.
    "answer_md": (f"Use `Session.get` [[1]](#src-1), see {LONG}.\n\n```python\nwith Session(engine) as s:\n"
                  "    user = s.get(User, 1)  # a deliberately long comment line that is far wider than a phone,"
                  " and wider than the answer column on a large desktop monitor too, which is the point of it\n```"),
}
SOURCES = [{"n": 1, "version": "2.0.51", "cited": True, "heading": "Session > get",
            "path": "doc/build/orm/some/really/long/path/without/spaces/anywhere/in/it/at/all.rst",
            "text": LONG + "()"},
           {"n": 2, "version": "1.4.52", "cited": False, "heading": "Other", "path": "orm/x.rst", "text": "x"}]
DECLINED = {**ANSWERED, "status": "declined", "status_label": "Declined: ...",
            "answer_md": "The sources do not answer this."}
ERROR = {**ANSWERED, "status": "error", "status_label": "Not answered",
         "error": "The local answer model (Ollama) is not running.", "answer_md": ""}

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))


def show(page, payload, sources) -> None:
    page.evaluate("([p, s]) => { document.getElementById('results').hidden = false;"
                  " renderAnswer(p); renderSources(s); }", [payload, sources])


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

    for label, size in (("desktop 1280px", {"width": 1280, "height": 900}),
                        ("phone 400px", {"width": 400, "height": 860})):
        page = browser.new_page(viewport=size)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        print(f"\n{label}")
        check("example chips load from /api/config", page.locator(".chip").count() == 5,
              f"{page.locator('.chip').count()} chips")

        show(page, ANSWERED, SOURCES)
        w = widths(page)
        check("the page never scrolls sideways", w["page"] <= w["screen"], f"{w['page']} of {w['screen']} px")
        check("a long code line scrolls inside its own box", w["code"] > w["codeBox"],
              f"{w['code']} px of code in a {w['codeBox']} px box")
        check("answer and sources " + ("side by side" if size["width"] > 900 else "stacked"),
              w["columns"] == (2 if size["width"] > 900 else 1), f"{w['columns']} column(s)")
        notice = page.locator(".notice")
        check("the notice draws the model name as code, no stray backtick",
              notice.locator("code").inner_text() == "qwen2.5-coder:7b" and "`" not in notice.inner_text())
        page.locator("a.cite").first.click()
        page.wait_for_timeout(300)
        check("clicking [1] opens and highlights source card 1",
              page.evaluate("() => { const c = document.getElementById('src-1'); "
                            "return c.open && c.classList.contains('flash'); }"))

        show(page, DECLINED, SOURCES)
        check("declined: the pill says Declined, the note shows, no citation links",
              page.locator(".pill.declined").count() == 1 and page.locator(".declined-note").count() == 1
              and page.locator("a.cite").count() == 0)

        show(page, ERROR, SOURCES)
        check("error: the pill says Not answered, the message shows, sources still listed",
              page.locator(".pill.error").count() == 1 and "Ollama" in page.locator(".md").inner_text()
              and page.locator(".src").count() == 2)
        page.close()

    check("no JavaScript errors on either page", not errors, "; ".join(errors)[:200])
    browser.close()

print(f"\n{sum(results)} of {len(results)} checks pass")
sys.exit(0 if all(results) else 1)
