"""The demo page driven the way a person drives it: click, type, press Enter.

    DEMO_GENERATOR=ollama RAG_DENSE=memory PYTHONPATH=. \
      uv run --with fastapi --with uvicorn python space/web.py &
    uv run --with playwright==1.62.0 python tools/check_page_live.py http://127.0.0.1:7860

WHY IT EXISTS, AND WHY IT IS SEPARATE FROM check_page.py

`tools/check_page.py` pushes fixed payloads straight into `renderAnswer` and
`renderSources`, so it tests the page's DRAWING and asks no model. That is what
makes it fast and CI-able -- and it means the entire submit path was covered by
nothing: the send button, the suggestion chips, the Enter key, the disabled
state while a question is in flight, and the recorded example being cleared when
a real answer replaces it. Viraj asked whether the send button was actually
wired. It was, but nothing in the repo could have told him so.

This script asks the real model through the real endpoint, three times, so it
needs Ollama running and takes a couple of minutes. It is NOT part of CI and is
not a pytest: it is the check you run before showing the page to anyone.
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
ok = []
def check(name, cond, detail=""):
    ok.append(bool(cond))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))

def state(pg):
    return pg.evaluate("""() => ({
        label: document.querySelectorAll('.example-label').length,
        pill: (document.querySelector('.pill')||{}).textContent || '',
        cites: document.querySelectorAll('a.cite').length,
        srcs: document.querySelectorAll('.src').length,
        disabled: document.getElementById('ask').disabled,
        wide: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    })""")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1100, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(400)

    print("\nopening state")
    s0 = state(pg)
    check("opens on the recorded example", s0["label"] == 1 and s0["srcs"] == 5, f"{s0['srcs']} sources")
    check("the example is highlighted and dressed",
          pg.locator(".codeblock .copy").count() == 1 and pg.locator("pre code .hljs-keyword").count() > 0)

    print("\nempty box")
    check("the send button is dead until there is a question", state(pg)["disabled"])
    pg.fill("#q", "x"); pg.wait_for_timeout(150)
    check("typing wakes it up", not state(pg)["disabled"])
    pg.fill("#q", "   "); pg.wait_for_timeout(150)
    check("whitespace does not count as a question", state(pg)["disabled"])
    check("nothing was submitted while doing that", state(pg)["label"] == 1)

    print("\nSEND BUTTON")
    pg.fill("#q", "engine.execute is gone, how do I run a select in 2.0")
    pg.click("#ask")
    pg.wait_for_timeout(300)
    mid = state(pg)
    check("button disables and a working state shows while it runs",
          mid["disabled"] and "Working" in mid["pill"], f"pill={mid['pill']!r}")
    check("the recorded-example label is cleared on submit", mid["label"] == 0)
    pg.wait_for_function("() => !document.getElementById('ask').disabled", timeout=300000)
    s1 = state(pg)
    check("a live answer comes back", s1["pill"] and "Working" not in s1["pill"], f"pill={s1['pill']!r}")
    check("sources are listed", s1["srcs"] > 0, f"{s1['srcs']} sources")
    check("button is re-enabled", not s1["disabled"])
    check("no sideways scroll after a live answer", not s1["wide"])

    print("\nSUGGESTION CHIP")
    pg.locator(".chip").first.click()
    pg.wait_for_timeout(300)
    check("chip fills the box and submits", state(pg)["disabled"])
    pg.wait_for_function("() => !document.getElementById('ask').disabled", timeout=300000)
    s2 = state(pg)
    check("chip produced an answer with citations", s2["cites"] > 0, f"{s2['cites']} citations")

    print("\nCITATION CLICK")
    pg.locator("a.cite").first.click(); pg.wait_for_timeout(400)
    check("source opens and highlights",
          pg.evaluate("() => { const c=document.querySelector('.src'); return c.open && document.querySelectorAll('.src.flash').length>0; }"))

    print("\nENTER KEY")
    pg.fill("#q", "what replaces Query.get in 2.0")
    pg.press("#q", "Enter"); pg.wait_for_timeout(300)
    check("Enter submits", state(pg)["disabled"])
    pg.wait_for_function("() => !document.getElementById('ask').disabled", timeout=300000)
    check("Enter produced an answer", "Working" not in state(pg)["pill"])

    print("\nSHIFT+ENTER")
    pg.fill("#q", "line one")
    pg.press("#q", "Shift+Enter")
    pg.type("#q", "line two")
    pg.wait_for_timeout(200)
    val = pg.input_value("#q")
    check("Shift+Enter makes a new line instead of submitting", "\n" in val and not state(pg)["disabled"], repr(val))

    check("no JavaScript errors throughout", not errs, "; ".join(errs)[:200])
    pg.close(); b.close()

print(f"\n{sum(ok)} of {len(ok)} interaction checks pass")
sys.exit(0 if all(ok) else 1)
