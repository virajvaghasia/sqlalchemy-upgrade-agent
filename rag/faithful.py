"""
Phase 4 — faithfulness: is this claim actually supported by the page it cites?

    uv run python -m rag.faithful --check            # one call; proves the key works
    uv run python -m rag.faithful --models           # what this key can actually pin to

THE HALF THAT NEEDS A MODEL, AND WHY IT WAITED

`rag/judge.py` measures everything about an answer that can be counted:
citations that point at sources which exist (`D73`), code blocks with no source
attached, and dotted API calls that appear in none of the retrieved pages
(`D77`). All deterministic, no key, no free tier, exact.

What none of it reaches is a claim made in **prose**. `g056` is the standing
example: it fabricates in sentences rather than in a code block, so the
groundedness detector is structurally blind to it (`D77` says so in as many
words). "Is this sentence supported by that passage" is a reading task, and
reading needs a reader.

WHAT "PINNED" IS ACTUALLY BUYING, WHICH IS LESS THAN PHASE-4.md CLAIMED

`PHASE-4.md` Step 2 argued the judge must be pinned "the same way swapping the
golden set would" invalidate rows (`D65`/`D61`). **That analogy imported the
conclusion without the cost structure.** Re-cutting the golden ruler is ~25
hours of `D06` hand-verification; re-running this judge is ~60 calls and a few
minutes. Pinning is a convenience here, not a correctness requirement.

Two properties ARE tight, and neither is the snapshot id:

  * **Same judge, both arms, one sitting.** `D54` applied to the judge instead
    of the generator. Judge D on Monday and H on Friday and the comparison is
    worthless no matter how carefully the model was pinned. Free to honour.
  * **Agreement with a human, measured.** Step 5 asks for a hand-check of ten.
    A pinned judge with unmeasured agreement is a precise instrument of unknown
    accuracy, and `g065` is the proof that the unmeasurable label is exactly
    where this repo has been wrong before.

So `MODEL` below is recorded rather than defended, and every row this module
writes carries the model that produced it. A future run that disagrees then has
something to blame instead of a mystery.

WHY THE MODEL ID IS NOT HARDCODED FROM MEMORY

Model ids churn and a stale one 404s. `--models` asks the key what it can
actually reach and prints the ids, so the pin is chosen from what exists rather
than from what someone remembered. Put the chosen id in `MODEL` and it travels
into every row.

**Measured on 2026-08-31, first contact with a real key.** `gemini-2.5-flash`
-- written here from memory -- returned:

    HTTP 404: This model models/gemini-2.5-flash is no longer available to new
    users. Please update your code to use models/gemini-3.6-flash

and the key itself was fine: a 404 on the model, not a 401 on the credential.
That is the whole argument for `--models` in one response.

**AND THE CATALOG IS NOT THE TRUTH.** `--models` lists `gemini-2.5-flash` --
the same id that had just 404'd. The listing is what the API advertises; what a
call does is what a call does. **`--check` is the authority, not `--models`.**
So `--models` is for discovering candidates and `--check` is for confirming
one, and neither substitutes for the other.

No dated snapshot exists for the stable flash line -- the dated ids in the
catalog are all previews -- so the best available pin is a version-numbered id
(`gemini-3.6-flash`), not `gemini-flash-latest`, which floats by design and is
exactly what D78 says to avoid.

ZERO PAID API CALLS (unchanged, and this module cannot enforce it)

The free tier is the constraint. This module does not and cannot check whether
billing is attached to the key -- that is a property of the Google Cloud
project, not of the request. `--check` makes exactly ONE call so that finding
out the key is wrong costs one call rather than a hundred.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"

# The pinned judge. Chosen from `--models` output rather than from memory, and
# written into every row this module produces (see `stamp()`), so a number can
# always be traced to the reader that produced it.
MODEL = "gemini-3.6-flash"

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
KEY_VAR = "GEMINI_API_KEY"

# A judge that rambles is a judge whose output needs parsing, and a parser is
# one more thing that can silently disagree with what the model meant. The
# three verdicts are the whole vocabulary.
VERDICTS = ("SUPPORTED", "UNSUPPORTED", "PARTIAL")

JUDGE_PROMPT = """\
You are checking one claim against source passages. Answer with exactly one \
word on the first line: SUPPORTED, UNSUPPORTED, or PARTIAL.

SUPPORTED   - the passages state this, or state something it follows from.
UNSUPPORTED - the passages do not state this. Use this even if the claim is
              true in general; the question is what the passages say.
PARTIAL     - part of the claim is in the passages and part is not.

Then one short sentence saying which passage decided it, or that none did.

CLAIM:
{claim}

PASSAGES:
{passages}
"""


def api_key() -> str | None:
    """The key from the environment, falling back to `.env`.

    `.env` is gitignored and is where the repo already keeps `DATABASE_URL`,
    but nothing loads it for host scripts -- Compose reads it for containers
    and `seed.py` uses a plain `os.getenv`. A host script that silently sees no
    key would report "no key" to someone looking straight at the line in the
    file, so the fallback is worth the fifteen lines.
    """
    if os.environ.get(KEY_VAR):
        return os.environ[KEY_VAR]
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == KEY_VAR:
            # Strip quotes -- a key pasted as KEY="abc" is the common shape and
            # sending the quotes produces a 400 that reads like a bad key.
            return value.strip().strip("'\"") or None
    return None


def _post(path: str, body: dict, key: str, timeout: int = 120) -> dict:
    request = urllib.request.Request(
        f"{API_ROOT}/{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _get(path: str, key: str, timeout: int = 30) -> dict:
    request = urllib.request.Request(
        f"{API_ROOT}/{path}", headers={"x-goog-api-key": key}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def generate(prompt: str, *, key: str, model: str = MODEL,
             post=_post) -> str:
    """One non-streaming call to the judge. `post` is injectable so every test
    in this module runs without a key and without a network."""
    data = post(
        f"models/{model}:generateContent",
        {
            "contents": [{"parts": [{"text": prompt}]}],
            # Zero temperature for the same reason ask.py pins it: a judge that
            # answers differently on re-read cannot be compared with itself.
            "generationConfig": {"temperature": 0.0},
        },
        key,
    )
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def parse_verdict(text: str) -> tuple[str, str]:
    """First word is the verdict, the rest is the reason.

    Anything that is not one of the three words is returned as `UNPARSED`
    rather than coerced to a verdict. A judge that stopped following the format
    is a fact about the run, and silently mapping it onto UNSUPPORTED would
    move a number in the flattering direction -- the same failure ask.refused()
    had before it became a prefix test (`D76`).
    """
    head, _, rest = text.strip().partition("\n")
    # First alphabetic run on the first line. Models decorate freely --
    # `**SUPPORTED**`, `SUPPORTED:`, `### SUPPORTED` -- and refusing those
    # would report UNPARSED for a judge that answered correctly. Pulling the
    # word out rather than stripping a fixed character set means the next
    # decoration nobody predicted still parses.
    words = re.findall(r"[A-Za-z]+", head)
    verdict = words[0].upper() if words else ""
    if verdict not in VERDICTS:
        return "UNPARSED", text.strip()
    # The reason may sit on the verdict's own line (`SUPPORTED: because ...`)
    # or on the next one. Keep both rather than dropping whichever is second.
    tail = head[head.upper().index(verdict) + len(verdict):].lstrip("*_`:-— ")
    return verdict, "\n".join(x for x in (tail.strip(), rest.strip()) if x)


def judge_claim(claim: str, passages: list[str], *, key: str,
                model: str = MODEL, post=_post) -> dict:
    numbered = "\n\n".join(
        f"[{n}] {p}" for n, p in enumerate(passages, start=1)
    )
    raw = generate(
        JUDGE_PROMPT.format(claim=claim, passages=numbered),
        key=key, model=model, post=post,
    )
    verdict, reason = parse_verdict(raw)
    return stamp({"claim": claim, "verdict": verdict, "reason": reason}, model)


def stamp(row: dict, model: str = MODEL) -> dict:
    """Every row carries the judge that produced it.

    This is the property that actually matters (see the module docstring): not
    that the model never changes, but that a row never loses track of which
    model read it.
    """
    return {**row, "judge_model": model}


# --- CLI --------------------------------------------------------------------

def check(key: str, model: str = MODEL, post=_post) -> tuple[bool, str]:
    """Exactly one call. Proves the key authenticates and the pinned model
    answers, before anything spends a hundred of them."""
    try:
        out = generate("Reply with the single word: SUPPORTED", key=key,
                       model=model, post=post)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        return False, f"HTTP {exc.code} from {model}\n{detail}"
    except urllib.error.URLError as exc:
        return False, f"cannot reach {API_ROOT}: {exc.reason}"
    return True, out


def main() -> None:
    argv = sys.argv[1:]
    key = api_key()
    if not key:
        sys.exit(
            f"no {KEY_VAR}.\n"
            f"  put it in {ENV_FILE} as {KEY_VAR}=... (that file is gitignored)\n"
            f"  or export it for this shell.\n"
            f"  free key: https://aistudio.google.com/apikey  (do NOT attach billing)"
        )

    if "--models" in argv:
        try:
            data = _get("models", key)
        except urllib.error.HTTPError as exc:
            sys.exit(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:400]}")
        names = [
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        print(f"{len(names)} models this key can call:\n")
        for n in sorted(names):
            print(f"  {n}{'   <- MODEL' if n == MODEL else ''}")
        print(
            f"\nPin one of these in rag/faithful.py MODEL. Prefer a dated snapshot\n"
            f"over a floating alias -- the alias moves under you, the snapshot does not."
        )
        return

    if "--check" in argv:
        ok, out = check(key)
        print(f"key: found ({len(key)} chars)")
        print(f"pinned MODEL: {MODEL}")
        print(f"one call: {'OK' if ok else 'FAILED'}")
        print(f"  {out}")
        if not ok:
            print("\n  --models lists what this key can actually reach.")
            sys.exit(1)
        return

    sys.exit(__doc__.strip().splitlines()[0] + "\n\n  pass --check or --models")


if __name__ == "__main__":
    main()
