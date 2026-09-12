"""
Phase 4 — faithfulness: is this claim actually supported by the page it cites?

    uv run python -m rag.faithful --check            # one call; proves the key works
    uv run python -m rag.faithful --models           # what this key can actually pin to
    uv run python -m rag.faithful --sweep --local    # judge the saved D/H answers
    uv run python -m rag.faithful --sweep --local --resume   # pick up a killed run
    uv run python -m rag.faithful --claims g056      # one item, sentence by sentence
    uv run python -m rag.faithful --agreement        # Step 5's ten, for a human
    uv run python -m rag.faithful --cross-check gemini-3.8-flash   # a 2nd model on those ten

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
catalog are all previews -- so the best available pin is a version-numbered id,
not `gemini-flash-latest`, which floats by design and is exactly what D78 says
to avoid.

**AND THEN THE PIN ITSELF WENT AWAY. Measured 2026-09-03** (`D80`), which is
the day D78's argument stopped being theoretical:

    gemini-3.6-flash     FAIL HTTP 503 from gemini-3.6-flash
    gemini-3.5-flash     OK   SUPPORTED
    gemini-3.7-flash     OK   SUPPORTED
    gemini-3.8-flash     OK   SUPPORTED

One call each, same key, same minute. `gemini-3.6-flash` -- the id pinned three
days earlier and written into this constant -- answered 503 "experiencing high
demand" through four retries, while three neighbours answered on the first
attempt. **A pinned id is a promise about a name, not about a service.**

D78 already said the snapshot is a convenience and the tight properties are
*same judge, both arms, one sitting* and *agreement measured against a human*.
Both survive this intact: `MODEL` moves to `gemini-3.7-flash`, `stamp()` puts
that id on every row it produces, and `--model` overrides it without a code
edit the next time a flash model is busy. What is NOT allowed is switching
model **mid-run** -- that breaks the one property that actually matters, so a
sweep uses one id for both arms or it is not a comparison.

ZERO PAID API CALLS (unchanged, and this module cannot enforce it)

The free tier is the constraint. This module does not and cannot check whether
billing is attached to the key -- that is a property of the Google Cloud
project, not of the request. `--check` makes exactly ONE call so that finding
out the key is wrong costs one call rather than a hundred.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import platform
import re
import sys
import time
import urllib.error
import urllib.request

from rag import judge

REPO = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"

# The pinned judge. Chosen from `--models` output rather than from memory, and
# written into every row this module produces (see `stamp()`), so a number can
# always be traced to the reader that produced it.
MODEL = "gemini-3.7-flash"

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


def machine() -> str:
    """`Darwin-arm64`, `Linux-x86_64`. The axis that turned out to matter.

    Deliberately NOT the hostname: the OS and CPU family is what separates the
    Mac from the lab 3060, and it identifies a machine class rather than a
    person's laptop.
    """
    return f"{platform.system()}-{platform.machine()}"


def stamp(row: dict, model: str = MODEL) -> dict:
    """Every row carries the judge that produced it, AND the machine it ran on.

    The judge stamp is `D78`'s: not that the model never changes, but that a
    row never loses track of which model read it.

    **The machine stamp was added 2026-09-05, because the lab measured what
    Round 15 had written down as the second possible outcome.** Same judge
    (`gemma4:e4b`), same saved answers, same corpus, temperature 0 — and prompt
    D's supported rate came back **85% on the Mac and 77% on the 3060**. The
    verdicts are not machine-independent, so a row that records only its judge
    is under-labelled, and a scorecard reading two such files cannot tell that
    it is mixing two machines. It was: `faithfulness-phase4.json` became the
    lab's while `prompt-sweep-phase4.json` stayed the Mac's, and nothing in
    either file said so.

    Round 15's own pre-decided reading called for this before the data arrived:
    *"then every faithfulness figure has to carry its machine the way rows
    already carry their judge model."*
    """
    return {**row, "judge_model": model, "machine": machine()}


# --- retrying, because a 503 is not a broken key ----------------------------
#
# Measured 2026-09-03, on the first attempt of the day:
#
#     uv run python -m rag.faithful --check
#     key: found (53 chars)
#     one call: FAILED
#     HTTP 503 from gemini-3.6-flash
#     {"error": {"code": 503, "message": "This model is currently
#      experiencing high demand..."}}
#
# The key was fine. The model was busy. Without a retry that is a run of a
# hundred calls dying somewhere in the middle -- which is exactly `D75`, where
# a slow Ollama call walked past a handler written for "Ollama is down" and
# killed a 300-generation sweep at 150 with zero rows saved.
#
# The lesson `D75` actually taught is not "catch more exceptions": it is that
# **two conditions had been collapsed into one**. *The service is gone* must
# stop; *this call was unlucky* must not. So the retry list is explicit —
# 429 (rate limited), and the 5xx family the API returns when it is overloaded.
# A 401 or a 404 is not in it and never should be: retrying a wrong key four
# times is four times the wrong answer, slower.
RETRY_CODES = (429, 500, 502, 503, 504)

# Marks a quota that resets tomorrow rather than in sixty seconds. Matched on
# the quotaId the API actually returns, not on the prose message, which is
# identical for both kinds ("You exceeded your current quota").
DAILY_QUOTA_MARKER = "PerDay"


def _is_daily_quota(exc) -> bool:
    """Does this 429 name a per-DAY quota? Unreadable bodies count as NOT
    daily, so an unparseable error still gets its retries -- the failure mode
    of guessing wrong here is a run that stops when it could have continued."""
    try:
        return DAILY_QUOTA_MARKER in exc.read().decode(errors="replace")
    except Exception:
        return False


RETRY_ATTEMPTS = 4

# Seconds between calls. The free tier is a per-MINUTE request limit, so the
# choice is between pacing under it and repeatedly hitting 429 and waiting out
# a backoff that is much longer than the pause would have been.
#
# Measured 2026-09-03, and this is why the constant exists rather than a zero:
# an unpaced run of ~110 calls spent seven minutes without completing ten
# items, because every few calls earned a 429 and then a 20-second wait. The
# arithmetic is the argument -- 6s of deliberate waiting per call is under a
# 10/min ceiling and never triggers one.
PACE_SECONDS = 6.0


def retrying(post=_post, attempts: int = RETRY_ATTEMPTS, backoff: float = 15.0,
             sleep=time.sleep):
    """Wrap a transport so overload and rate limits are survived, not fatal.

    A transport decorator rather than a branch inside `generate()`, so every
    caller -- `--check`, one claim, a hundred-row sweep -- gets the same
    behaviour, and so the tests can pass a transport that fails on demand
    without any network at all.

    `TimeoutError` is caught alongside `URLError` for the reason `D75` records:
    `socket.timeout` IS a `TimeoutError` and is NOT a `URLError`, so a handler
    written for one silently does not cover the other.
    """
    def wrapped(path, body, key, timeout=120):
        for attempt in range(1, attempts + 1):
            try:
                return post(path, body, key, timeout)
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRY_CODES or attempt == attempts:
                    raise
                # A 429 is two different conditions wearing one status code,
                # and only one of them is worth waiting for. Measured
                # 2026-09-03, the body says which:
                #
                #   quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
                #
                # A per-MINUTE limit clears in under a minute and a backoff is
                # exactly right. A per-DAY limit does not clear today, so
                # retrying it four times costs 90 seconds to arrive at the same
                # refusal -- ten items of that is fifteen minutes of a tool
                # looking busy while it fails. Same mistake as D75 in the other
                # direction: there, two conditions were collapsed and a
                # transient killed the run; here, collapsing them makes a
                # permanent failure pretend to be transient.
                if exc.code == 429 and _is_daily_quota(exc):
                    raise
                sleep(backoff * attempt)
            except (urllib.error.URLError, TimeoutError):
                if attempt == attempts:
                    raise
                sleep(backoff * attempt)
        raise RuntimeError("unreachable")          # pragma: no cover
    return wrapped


# --- the local judge, and why it is not a downgrade -------------------------
#
# MEASURED 2026-09-03, and it contradicts D78 in as many words. D78 sized the
# judging workload and concluded:
#
#     "Rate limits are not the constraint on any free tier, which removes the
#      reason most people pick one."
#
# The 429 body says otherwise, and it names the quota:
#
#     quotaId:    GenerateRequestsPerDayPerProjectPerModel-FreeTier
#     quotaValue: 20
#
# **Twenty requests per day, per model.** D + H over the saved sweep is about
# 110 calls, so the API judge cannot finish this comparison today, tomorrow, or
# in any single sitting -- and `D78`'s own tight property is that both arms are
# judged by the same judge in ONE sitting. Spreading a run across six days to
# fit the quota does not satisfy it; it destroys it.
#
# The escape is not a bigger quota. It is that `D78` already named the fallback
# and gave the reason it is a good one:
#
#     "A local judge is in fact MORE pinnable than any API -- you hold the
#      weights -- and stays the fallback if the agreement-of-ten comes back
#      poor."
#
# WHAT ABOUT "TOO WEAK TO GRADE ITSELF"
#
# `ROADMAP.md` asks for a strong judge because the local model is too weak to
# grade itself. That objection is about **self**-grading, and this is not that:
# the generator is `qwen2.5-coder:7b` and the judge is a different family and a
# different size. Nothing here asks a model to mark its own homework.
#
# It is also the objection Step 5 exists to settle rather than argue about.
# `--agreement` puts ten of this judge's verdicts in front of a human, and if
# the agreement comes back poor then the judge is poor -- measured, on this
# corpus, rather than assumed from a model card. A strong judge with unmeasured
# agreement and a weak judge with unmeasured agreement are the same object.

OLLAMA_URL = "http://127.0.0.1:11434"

# A different family and a different size from ask.MODEL (`qwen2.5-coder:7b`),
# which is the whole point: a judge that shares weights with the generator is
# the self-grading ROADMAP.md objects to.
LOCAL_MODEL = "gemma4:e4b"

# Ollama's default context is 4096 tokens and it TRUNCATES SILENTLY past it --
# no error, no warning, just a judge that read four passages out of five and
# answered confidently about the ones it saw.
#
# Measured 2026-09-03 over the H answers: the judge prompt runs 7127 to 11149
# characters, so roughly 1800-2800 tokens. That fits 4096 today, which is
# exactly the situation worth pinning: it fits until one long answer does not,
# and the run that overflows reports numbers rather than an error. 8192 is
# double the largest prompt measured and costs nothing when the prompt is small.
LOCAL_CONTEXT = 8192


def local_digests(timeout: int = 10) -> dict:
    """`{model name: content digest}` from Ollama, or `{}` if it is not there.

    Needed because a name is not an identity. Measured 2026-09-03 on this Mac:

        NAME                ID              SIZE
        gpt-5.5:latest      c6eb396dbd59    9.6 GB
        gemma4:e4b          c6eb396dbd59    9.6 GB

    **Two tags, one set of weights.** A cross-check that compared only the
    strings would accept `gemma4:e4b` against `gpt-5.5:latest`, report high
    agreement, and be measuring a model against itself -- the single most
    flattering result this tool could produce, from a run that looks entirely
    legitimate in the log.
    """
    try:
        request = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError):
        return {}
    return {m["name"]: m.get("digest", "") for m in data.get("models", [])}


def same_model(a: str, b: str, digests: dict | None = None) -> bool:
    """Are these two names the same model? Compares digests when both are
    local, and falls back to the names when they are not (a hosted id has no
    digest to compare, and two different hosted ids are genuinely different)."""
    if a == b:
        return True
    digests = local_digests() if digests is None else digests
    da, db = digests.get(a), digests.get(b)
    return bool(da and db and da == db)


def local_post(path: str, body: dict, key: str, timeout: int = 300) -> dict:
    """An Ollama call wearing the Gemini transport's shape.

    Same `(path, body, key, timeout)` signature and same return shape, so
    `generate`, `judge_claim`, `judge_answer` and `sweep_rows` are untouched by
    which judge is in use. A judge swap that needed changes in four call sites
    is a judge swap nobody makes under time pressure -- and D78 says the swap
    has to stay cheap, because the pin is a convenience.

    `key` is ignored and that is deliberate rather than sloppy: it keeps the
    two transports interchangeable, and a local model genuinely has no
    credential.
    """
    model = path.removeprefix("models/").removesuffix(":generateContent")
    prompt = body["contents"][0]["parts"][0]["text"]
    payload = json.dumps({
        "model": model,
        "stream": False,
        # Same reason ask.py pins it: a judge that answers differently on
        # re-read cannot be compared with itself.
        "options": {"temperature": 0.0, "num_ctx": LOCAL_CONTEXT},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    return {"candidates": [{"content": {"parts": [
        {"text": data["message"]["content"]}]}}]}


NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_KEY_VAR = "NVIDIA_API_KEY"
# A judge from outside Google (Gemini, gemma) and Alibaba (qwen), chosen in
# PHASE-6.md Step 3b before it read any answer.
# mistral-large-2 was the first choice and returns 404 on this key (PHASE-6.md).
NVIDIA_JUDGE = "openai/gpt-oss-20b"


def env_key(var: str) -> str | None:
    """`api_key()` for any variable name: environment first, then `.env`."""
    if os.environ.get(var):
        return os.environ[var]
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() == var:
            return value.strip().strip("'\"") or None
    return None


def nvidia_post(path: str, body: dict, key: str, timeout: int = 120) -> dict:
    """NVIDIA's OpenAI-compatible endpoint wearing the Gemini transport's shape.

    Same contract as `local_post`, for the same reason: every judge function
    stays untouched when the judge changes. Wrap it in `retrying()` like the
    others -- a 429 here is the free-credit rate limit.
    """
    model = path.removeprefix("models/").removesuffix(":generateContent")
    payload = json.dumps({
        # Reasoning model: the budget covers thinking before the one-word verdict.
        "model": model, "temperature": 0.0, "max_tokens": 4096,
        "messages": [{"role": "user", "content": body["contents"][0]["parts"][0]["text"]}],
    }).encode()
    request = urllib.request.Request(
        NVIDIA_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    return {"candidates": [{"content": {"parts": [
        {"text": data["choices"][0]["message"].get("content") or ""}]}}]}


# --- judging a whole answer -------------------------------------------------
#
# `judge_claim` grades one sentence. What a run needs to grade is an ANSWER,
# and the two are not the same thing.
#
# WHAT IS SENT TO THE JUDGE, AND WHAT IS DELIBERATELY NOT
#
# The prose only. Fenced code is stripped out before the claim is built, and
# that is a division of labour rather than a shortcut: `judge.ungrounded_calls`
# already grades code deterministically, exactly, with no key (`D77`), and it
# found D 2 ungrounded of 48 and H 0 of 62. Sending the code here as well would
# spend a paid-tier call to re-answer a question a regex already answers
# exactly, and would let a judge's opinion overrule a measurement.
#
# What that leaves is precisely `D77`'s stated blind spot:
#
#     "What it cannot see: g056, which fabricates in prose rather than in code.
#      A code grounding detector is structurally blind to that."
#
# So this is not a better version of the deterministic half. It is the other
# half, and the two do not overlap.
#
# WHY ONE CALL PER ANSWER RATHER THAN ONE PER SENTENCE
#
# Sentence-level would say *which* sentence is unsupported, which is more
# useful. It also multiplies a 110-answer run into roughly 500 calls, and the
# free tier is the constraint the whole judge was chosen under (zero paid API
# calls). One call per answer keeps D + H inside a single sitting -- which
# `D78` names as the property that actually matters, above the pinned id -- and
# the judge's one-sentence reason still names the passage that decided it.
#
# `--claims` exists for when the aggregate has already pointed at an item and
# the question becomes *which sentence*.
MIN_WORDS_TO_JUDGE = 8


def prose(answer: str) -> str:
    """The answer with its fenced code blocks removed.

    Uses `judge.CODE_FENCE` rather than a second regex. `probe.py` once held a
    private copy of a detector and silenced the very signal it existed for; the
    rule since then is that a pattern has one home.
    """
    return judge.CODE_FENCE.sub(" ", answer).strip()


def sentences(text: str) -> list[str]:
    """Prose split into claim-sized pieces for `--claims`.

    Deliberately crude -- a period, question mark or newline followed by
    whitespace. `Query.from_self()` and `2.0` survive because the split needs
    whitespace after the period, which is the only case that actually bit when
    this was tried on real answers.
    """
    parts = re.split(r"(?<=[.?!])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.split()) >= MIN_WORDS_TO_JUDGE]


def judge_answer(answer: str, passages: list[str], *, key: str,
                 model: str = MODEL, post=_post) -> dict:
    """One verdict for one answer, against the pages that answer was given.

    An answer whose prose is too short to carry a claim is recorded `NO_PROSE`
    rather than judged. That is not a pass: a code-only answer has already been
    graded by `judge.ungrounded_calls` and by `uncited_code_blocks`, and
    calling it SUPPORTED here because there was nothing to read would be the
    flattering direction -- the same trap `D62` names for refusals.
    """
    claim = prose(answer)
    if len(claim.split()) < MIN_WORDS_TO_JUDGE:
        return stamp({"claim": claim, "verdict": "NO_PROSE",
                      "reason": "no prose to judge; code is judge.py's half"},
                     model)
    return judge_claim(claim, passages, key=key, model=model, post=post)


# --- the run ----------------------------------------------------------------
#
# WHY THE ANSWERS ARE READ FROM DISK AND THE SOURCES ARE RE-RETRIEVED
#
# The saved sweep (`deliverables/prompt-sweep-phase4.json`) holds 300 answers
# that cost about two and a half hours of Mac generation. Regenerating them to
# judge them would spend that again AND make the result non-comparable, because
# `D54` says refusal cells drift across days with the prompt, temperature and
# index all unchanged. `D77` took this route for exactly this reason and it is
# the same route here.
#
# The sources are NOT in that file, so they are re-retrieved. That is cheap and
# it is safe: retrieval is deterministic and does not depend on the prompt --
# `D74`'s sweep retrieves once and reuses the hits across every variant for
# precisely that reason. So one retrieval per item serves every arm, which also
# guarantees the arms are judged against identical passages rather than against
# two runs of the same query.
#
# WHAT "ONE SITTING" MEANS HERE
#
# `D78`: the tight property is not the pinned id, it is that both arms are read
# by the same judge in one sitting. Judging D on Monday and H on Friday is
# worthless however carefully the model was pinned. So `--sweep` takes the
# variants together and interleaves them item by item, rather than finishing D
# and then starting H.


CHECKPOINT_EVERY = 10


def sweep_rows(saved: dict, items: list[dict], variants: list[str], *,
               key: str, model: str = MODEL, post=_post, k: int | None = None,
               retrieve=None, log=print, checkpoint=None,
               pace: float = 0.0, sleep=time.sleep,
               resume: dict | None = None, workers: int = 1) -> dict:
    """Judge each variant's answers against the pages that variant was given.

    Returns `{variant: [row, ...]}`. Refused, failed and unanswered rows are
    excluded before any call is made: a decline has nothing to be faithful to,
    and counting it UNSUPPORTED would make the system look worse the more
    honest it got (`D62`).
    """
    from rag import ask

    if retrieve is None:                      # imported late: needs Qdrant up
        from rag import index
        k = k or ask.DEFAULT_K

        def retrieve(question):
            return [h.payload["text"] for h in index.retrieve(question, limit=k)]

    by_id = {i["id"]: i for i in items}
    saved_rows = {v: {r["id"]: r for r in saved[v]} for v in variants}
    # Rows already judged in an earlier attempt, keyed by variant. An item is
    # skipped only when EVERY selected variant already has it -- a half-judged
    # item would otherwise leave one arm short and turn a paired comparison
    # into two averages (D61).
    # A `FAILED` row is NOT done. It is a missing measurement (D75), and
    # treating it as a verdict would make `--resume` skip the one item the
    # previous run could not judge -- a permanently absent row inside a file
    # that looks complete.
    done = {v: {r["id"]: r for r in (resume or {}).get(v, [])
                if r.get("verdict") != "FAILED"}
            for v in variants}

    # Every id that at least one arm answered. An item nobody answered costs
    # nothing to skip and would retrieve for no reader.
    def answerable_row(row):
        return (row is not None and not row.get("failed")
                and row.get("answer") and not ask.refused(row["answer"]))

    ids = [i["id"] for i in items
           if any(answerable_row(saved_rows[v].get(i["id"])) for v in variants)]

    out = {v: [row for row in done[v].values()] for v in variants}
    calls: list[str] = []
    for n, item_id in enumerate(ids, 1):
        if all(item_id in done[v] or not answerable_row(saved_rows[v].get(item_id))
               for v in variants):
            log(f"  [{n}/{len(ids)}] {item_id}  (already judged, skipped)")
            continue
        # Retrieved ONCE and handed to every arm. Two retrievals of the same
        # query would almost certainly agree, and "almost certainly" is how a
        # difference between prompts becomes a difference between lookups.
        passages = retrieve(by_id[item_id]["question"])
        todo = [v for v in variants
                if answerable_row(saved_rows[v].get(item_id))
                and item_id not in done[v]]

        def judge_one(v):
            row = saved_rows[v][item_id]
            try:
                return v, judge_answer(row["answer"], passages,
                                       key=key, model=model, post=post)
            except (urllib.error.URLError, TimeoutError) as exc:
                # MEASURED 2026-09-10: without this the sweep died at item 63
                # of 64 and three hours of judging survived only because
                # checkpoints exist. `retrying()` had already done its job --
                # it caught the `TimeoutError` that IS `D75`, retried four
                # times, and gave up -- and then the exception walked straight
                # out of the loop.
                #
                # `compare_prompts` learned this in D75 and wrote it down:
                # retry, then record the item `failed` and continue. **The
                # lesson never travelled to this module**, and nothing failed
                # until a real timeout arrived. One unreachable call must cost
                # one item, never the run.
                #
                # Recorded, not swallowed: a FAILED row is excluded from
                # `judged`, printed by `report()`, and retried by `--resume`.
                return v, stamp({"claim": "", "verdict": "FAILED",
                                 "reason": f"{type(exc).__name__}: {exc}",
                                 "failed": True}, model=model)

        # The arms of ONE item, optionally judged at the same time. Safe when
        # used: independent calls at temperature 0 against identical passages,
        # so concurrency changes WHEN a call happens, not what it reads.
        #
        # **MEASURED AND IT BUYS NOTHING, so `workers` defaults to 1.** A clean
        # A/B on an otherwise idle Mac, 2026-09-03:
        #
        #     sequential: 46s + 46s = 92s for two calls
        #     concurrent:             92s for two calls
        #
        # Ollama serialises them. The capability is kept because the lab 3060
        # is a different machine and may not, and because `--variants D,H,I`
        # would have three arms -- but the default is the honest one.
        #
        # THE FIRST MEASUREMENT SAID 1.66x AND IT WAS WRONG. It was taken while
        # the sweep itself was still running, so the "sequential" baseline was
        # a contended 108.9s rather than 46s -- I measured my own interference
        # and read it as a speedup. The lesson is not about threads: a
        # benchmark taken on a busy machine measures the machine, and the fix
        # was to stop everything and take it again.
        #
        # Never when pacing. `pace` exists to stay under a per-minute API
        # ceiling, and firing concurrent calls at a rate limit is the exact
        # behaviour it was added to stop.
        if workers > 1 and not pace and len(todo) > 1:
            with concurrent.futures.ThreadPoolExecutor(workers) as pool:
                verdicts = dict(pool.map(judge_one, todo))
        else:
            verdicts = {}
            for v in todo:
                if pace and calls:
                    sleep(pace)
                calls.append(item_id)
                verdicts.update([judge_one(v)])

        # Order is not decided here, and it is worth saying where it IS
        # decided: `pool.map` returns results in INPUT order, so `verdicts` is
        # already ordered by `todo` regardless of which call finished first.
        # Switching to `as_completed` for a marginal speedup would silently
        # make the row file's order depend on the machine's timing -- a diff
        # that changes for no reason -- and no test here would catch it,
        # because a mutation swapping this loop to iterate `verdicts` passes.
        # That was checked rather than assumed.
        #
        # What this loop does buy: `todo` may be a SUBSET when one arm was
        # already judged by --resume, and iterating `variants` keeps the row
        # order independent of which arms happened to be missing.
        seen = {}
        for v in variants:
            if v not in verdicts:
                continue
            verdict = verdicts[v]
            row = saved_rows[v][item_id]
            seen[v] = verdict["verdict"]
            out[v].append({
                "id": item_id,
                "provenance": row.get("provenance"),
                "answerable": row.get("answerable"),
                "answer_in_prompt": row.get("answer_in_prompt"),
                "verdict": verdict["verdict"],
                "reason": verdict["reason"],
                "judge_model": verdict["judge_model"],
                # Copied from the stamp rather than recomputed. Missing here
                # for one release: `stamp()` set it and this dict, which is
                # built field by field, silently dropped it -- so every saved
                # row lacked a machine and `report()` printed `judge ... on ?`
                # over a run whose machine was perfectly well known.
                #
                # The test that was supposed to prevent that called `stamp()`
                # directly, so it passed while the pipeline threw the field
                # away. **A test that pins a function instead of the path the
                # data actually takes pins nothing.** The replacement goes
                # through `sweep_rows`.
                "machine": verdict.get("machine", machine()),
                # Same trap as `machine` directly above, and it bit twice: this
                # dict is built field by field, so anything `stamp()` sets and
                # this list omits is silently thrown away. A FAILED row that
                # loses its flag is a failure that reads as a verdict.
                **({"failed": True} if verdict.get("failed") else {}),
                "claim": verdict["claim"],
            })
        log(f"  [{n}/{len(ids)}] {item_id}  "
            + "  ".join(f"{v}={seen.get(v, '-')}" for v in variants))
        # D75, literally: the first full prompt sweep died at generation 150 of
        # 300 with ZERO rows saved, and the whole night was spent again. Rows
        # cost money and minutes here too; write them down as they arrive.
        if checkpoint and n % CHECKPOINT_EVERY == 0:
            checkpoint(out)
    return out


def aggregate(rows: list[dict]) -> dict:
    counts = {verdict: 0
              for verdict in (*VERDICTS, "UNPARSED", "NO_PROSE", "FAILED")}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    judged = sum(counts[v] for v in VERDICTS)
    return {
        "answers": len(rows),
        "judged": judged,
        **counts,
        # The headline. Fully grounded in the pages the system itself chose to
        # put in the prompt -- PARTIAL is not in the numerator, because half a
        # supported answer is what g065 looks like under prompt H.
        "supported_rate": (counts["SUPPORTED"] / judged) if judged else 0.0,
        "unsupported_rate": (counts["UNSUPPORTED"] / judged) if judged else 0.0,
    }


def report(by_variant: dict) -> None:
    # The header names the model that ACTUALLY read these rows, taken from the
    # stamps, not the module constant. The first draft printed MODEL and so
    # announced `gemini-3.7-flash` over a run judged by `gemma4:e4b` -- a
    # report that misnames its own instrument, which is the exact failure D78
    # made stamp() mandatory to prevent.
    models = sorted({r["judge_model"] for rows in by_variant.values()
                     for r in rows})
    machines = sorted({r["machine"] for rows in by_variant.values()
                       for r in rows if r.get("machine")})
    print("\nFAITHFULNESS  —  prose only; code is judge.py's half (D77)")
    print(f"  judge: {', '.join(models) or '(no rows)'} on "
          f"{', '.join(machines) or 'a machine these rows do not record'}, "
          f"one sitting, both arms, identical passages")
    if len(machines) > 1:
        # Not fatal like two judges, but it must be visible: D's supported rate
        # measured 85% on Darwin-arm64 and 77% on Linux-x86_64 with everything
        # else held fixed (D83).
        print("  !! ROWS FROM MORE THAN ONE MACHINE — these verdicts do not "
              "reproduce across machines (D83)")
    if len(models) > 1:
        # Not a warning, a disqualification. D78's tight property is one judge
        # across both arms; two ids here means the comparison is void.
        print("  !! TWO JUDGES IN ONE RUN — this is not a comparison (D78)")
    print()
    head = f"  {'variant':<10}{'answers':>9}{'judged':>8}{'SUPP':>7}{'PART':>7}{'UNSUP':>7}{'UNPARSED':>10}{'NO_PROSE':>10}{'supported':>11}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for variant, rows in by_variant.items():
        a = aggregate(rows)
        print(f"  {variant:<10}{a['answers']:>9}{a['judged']:>8}{a['SUPPORTED']:>7}"
              f"{a['PARTIAL']:>7}{a['UNSUPPORTED']:>7}{a['UNPARSED']:>10}"
              f"{a['NO_PROSE']:>10}{a['supported_rate']:>10.0%}")
    for variant, rows in by_variant.items():
        bad = [r for r in rows if r["verdict"] in ("UNSUPPORTED", "PARTIAL")]
        print(f"\n  {variant}: {len(bad)} answers not fully supported by their own sources")
        for r in bad:
            print(f"    {r['id']:<6} {r['verdict']:<12} {r['reason'][:96]}")
        unparsed = [r["id"] for r in rows if r["verdict"] == "UNPARSED"]
        if unparsed:
            print(f"    UNPARSED (judge broke format, NOT coerced): {', '.join(unparsed)}")
        # A failure that does not appear here is indistinguishable from an item
        # nobody asked about -- and it is neither supported nor unsupported, so
        # it must be visible rather than inferred from a smaller denominator.
        failed = [r["id"] for r in rows if r["verdict"] == "FAILED"]
        if failed:
            print(f"    FAILED (transport, never judged — `--resume` retries "
                  f"these): {', '.join(failed)}")


# --- Step 5: the judge's own ceiling ----------------------------------------
#
# An LLM judge agrees with a human 85-92% of the time in the literature, which
# is a number about somebody else's judge on somebody else's task. Ours is
# unmeasured until ten of its verdicts are read by a human, and `PHASE-4.md`'s
# gate says the agreement rate has to be IN the report rather than assumed.
#
# The sample is risk-weighted rather than random, which is the same call the
# golden signature made on 2026-08-21 (§H CLOSED): a uniform sample of ten from
# a set that is mostly SUPPORTED measures agreement where it is easiest and
# says nothing about the verdicts a decision would actually rest on. So every
# UNSUPPORTED and PARTIAL goes in first, and SUPPORTED rows fill the rest --
# without those the sheet can only find false accusations and never a miss.
#
# Claude renders this sheet. Claude does not fill it in (`D06`).


# How many SUPPORTED rows are RESERVED in the sample of ten.
#
# Measured 2026-09-03, and the reservation exists because ranking by risk alone
# did not leave room for them: the finished run has 7 UNSUPPORTED and 5 PARTIAL
# across both arms, so the top ten were 7 + 3 and **not one SUPPORTED row got
# in**. That silently defeats the thing the sample is for.
#
# A sheet of only accusations can measure one error and not the other. It
# catches the judge condemning an answer its sources do support (a false
# accusation), and it is structurally incapable of catching the judge waving
# through an answer they do not (a miss) -- because it never shows the human a
# verdict of "fine". A miss is the g065 failure mode: the label that was wrong
# in the flattering direction and that no audit could see.
CONTROLS = 3


def agreement_sample(by_variant: dict, n: int = 10,
                     controls: int = CONTROLS) -> list[dict]:
    ranked = []
    for variant, rows in by_variant.items():
        for row in rows:
            ranked.append({**row, "variant": variant})
    order = {"UNSUPPORTED": 0, "PARTIAL": 1, "UNPARSED": 2, "SUPPORTED": 3,
             "NO_PROSE": 4}
    ranked.sort(key=lambda r: (order.get(r["verdict"], 9), r["variant"], r["id"]))

    # The controls are NOT arbitrary SUPPORTED rows, and that is the whole
    # point of them. A control only earns its slot if there is independent
    # reason to doubt the verdict, because a SUPPORTED row nobody suspects
    # teaches a human nothing.
    #
    # Measured 2026-09-03, and it is why this ranking exists at all: `g056` --
    # the item D77 names as the reason a prose judge was needed, because it
    # fabricates in prose rather than in code -- came back **SUPPORTED from
    # both arms**, while D78 records `gemini-3.6-flash` judging the same item
    # **PARTIAL**. The two judges disagree on the single most important item,
    # the local one is the lenient one, and the first version of this sample
    # did not put g056 in front of a human at all.
    #
    # So SUPPORTED rows are ordered by how suspect they are:
    #   1. answered an item the golden set marks unanswerable -- a fabrication
    #      by --refusals' definition, called grounded by the judge. If those
    #      two disagree, one of them is wrong and a human decides which.
    #   2. answered with the verified page NOT in the prompt (the open cell) --
    #      grounded in something, but not in the page the golden set names.
    #   3. everything else.
    def suspicion(row):
        if row.get("answerable") is False:
            return 0
        if row.get("answer_in_prompt") is False:
            return 1
        return 2

    supported = sorted((r for r in ranked if r["verdict"] == "SUPPORTED"),
                       key=lambda r: (suspicion(r), r["variant"], r["id"]))
    risky = [r for r in ranked if r["verdict"] != "SUPPORTED"]
    # Never more than half the sheet. The reservation exists so controls are
    # not crowded OUT; letting it crowd the risky rows out is the same mistake
    # facing the other way, and at n=3 the unclamped version returned three
    # SUPPORTED rows and no accusation at all.
    keep_controls = min(controls, len(supported), n // 2)
    picked = risky[: n - keep_controls] + supported[:keep_controls]
    # If there were not enough risky rows to fill the rest, top up rather than
    # returning a short sheet.
    if len(picked) < n:
        picked += [r for r in ranked if r not in picked][: n - len(picked)]
    return picked[:n]


HUMAN_VERDICT = "**Human verdict** (write AGREE or DISAGREE):"
SHOULD_HAVE_BEEN = ("**If DISAGREE, it should have been** "
                    "(SUPPORTED / PARTIAL / UNSUPPORTED):")


def read_agreement(path: pathlib.Path) -> dict:
    """Read the filled sheet back. The gate asks for the judge's agreement as a
    number IN the report, so the number has to come from the artifact a human
    actually wrote in -- not from a figure typed into a doc beside it.

    An unfilled row counts as unfilled, never as agreement. The rate is over
    what was answered, and the count of blanks is printed next to it, because
    "9 of 10 agree" over one filled row is the shape of every flattering
    statistic this repo has caught.
    """
    if not path.exists():
        return {"n": 0, "filled": 0, "agree": 0, "rate": None, "corrections": []}
    n = agree = filled = 0
    # The corrections, not just the count. Measured 2026-09-11 on the real
    # sheet: all three disagreements said the verdict should have been
    # PARTIAL -- the judge was not wrong at random, it was too EXTREME, in
    # both directions. "70% agreement" cannot say that, and the direction is
    # the part a reader can act on.
    corrections, item, said, pending = [], None, None, None
    for line in path.read_text().splitlines():
        head = re.match(r"##\s*\d+\.\s*`(g\d+)`", line)
        if head:
            item = head.group(1)
        verdict = re.match(r"\*\*Judge says:\*\*\s*`(\w+)`", line)
        if verdict:
            said = verdict.group(1)
        if line.startswith(SHOULD_HAVE_BEEN) and pending is not None:
            answer = line[len(SHOULD_HAVE_BEEN):].strip().strip("`_ ").upper()
            pending["should_be"] = answer or None
            corrections.append(pending)
            pending = None
            continue
        if not line.startswith(HUMAN_VERDICT):
            continue
        n += 1
        answer = line[len(HUMAN_VERDICT):].strip().strip("`_ ").upper()
        # DISAGREE contains AGREE. Order matters and a test pins it.
        if "DISAGREE" in answer:
            filled += 1
            pending = {"id": item, "judge_said": said, "should_be": None}
        elif "AGREE" in answer:
            filled += 1
            agree += 1
    if pending is not None:                      # no correction line followed
        corrections.append(pending)
    return {"n": n, "filled": filled, "agree": agree,
            "rate": (agree / filled) if filled else None,
            "corrections": corrections}


def agreement_sheet(sample: list[dict], items: list[dict], out: pathlib.Path,
                    retrieve=None, k: int | None = None,
                    second: dict | None = None) -> int:
    """Render the judge's verdicts for a human to agree or disagree with."""
    from rag import ask

    if retrieve is None:
        from rag import index
        k = k or ask.DEFAULT_K

        def retrieve(question):
            return [(h.payload.get("chunk_id", "?"), h.payload["text"])
                    for h in index.retrieve(question, limit=k)]

    by_id = {i["id"]: i for i in items}
    lines = [
        "# The judge's ceiling — ten verdicts for a human to check",
        "",
        "Generated by `rag.faithful --agreement`. **Claude renders this sheet and",
        "does not fill it in** (`D06`). `PHASE-4.md`'s gate asks for the judge's",
        "agreement with a human as a number in the report rather than an",
        "assumption, and this is the ten it is computed from.",
        "",
        "The sample is **risk-weighted, not random**: every UNSUPPORTED and",
        "PARTIAL first, SUPPORTED rows filling the rest. A uniform ten from a set",
        "that is mostly SUPPORTED measures agreement where it is easiest. The",
        "SUPPORTED rows are not filler either — without them the sheet can only",
        "catch the judge accusing wrongly, never the judge missing something.",
        "",
        "For each item the question is only:",
        "",
        "> Read the answer's prose against the passages below — **is the judge's",
        "> verdict right?** Mark `AGREE` or `DISAGREE`, and if you disagree, say",
        "> which verdict it should have been.",
        "",
        "Code blocks are stripped from the claim on purpose: code grounding is",
        "`judge.ungrounded_calls`' deterministic half (`D77`), and this half is",
        "the prose it is structurally blind to.",
        "",
        "---",
        "",
    ]
    for n, row in enumerate(sample, 1):
        item = by_id.get(row["id"], {})
        passages = retrieve(item.get("question", "")) if item else []
        lines += [
            f"## {n}. `{row['id']}`  (variant `{row['variant']}`, "
            f"{row.get('provenance', '?')})",
            "",
            f"**Question.** {item.get('question', '(not in golden.json)')}",
            "",
            f"**Judge says:** `{row['verdict']}` — {row['reason']}",
            "",
            f"_judge model: `{row['judge_model']}`_",
            "",
        ]
        other = (second or {}).get(f"{row['variant']}:{row['id']}")
        if other:
            flag = ("**they DISAGREE**" if other["verdict"] != row["verdict"]
                    else "they agree")
            lines += [
                f"**A second model says:** `{other['verdict']}` — "
                f"{other['reason']}",
                "",
                f"_second model: `{other['judge_model']}` — {flag}. Two models "
                f"agreeing can still both be wrong; your reading is the one "
                f"that counts (`D06`)._",
                "",
            ]
        lines += [
            "**The claim it read** (the answer with code fences removed):",
            "",
            "```",
            row["claim"].strip() or "(no prose)",
            "```",
            "",
            "**The passages it was given** (the same five the model answered from):",
            "",
        ]
        for m, (chunk_id, text) in enumerate(passages, 1):
            body = text.strip()
            clipped = body[:1400]
            lines += [
                f"<details><summary>[{m}] <code>{chunk_id}</code></summary>",
                "",
                "```",
                clipped + ("\n… truncated; full text: "
                           f"uv run python -m rag.golden --show {chunk_id}"
                           if len(body) > len(clipped) else ""),
                "```",
                "",
                "</details>",
                "",
            ]
        lines += [
            # Written so a human fills it in one word AND a script can read it
            # back. The first draft printed "`AGREE` / `DISAGREE` — _______",
            # which puts both words on the line and makes "has this been
            # answered" indistinguishable from "what was the answer" -- so the
            # agreement rate would have counted the blank template as a verdict.
            f"{HUMAN_VERDICT} _______",
            "",
            f"{SHOULD_HAVE_BEEN} _______",
            "",
            "---",
            "",
        ]
    out.write_text("\n".join(lines))
    return len(sample)


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


SWEEP_DEFAULT = REPO / "deliverables" / "prompt-sweep-phase4.json"
# One file per machine, and the machine is IN THE NAME rather than only in the
# rows. Stamping alone was not enough, and the proof is in the repo's history:
# the lab's run wrote `faithfulness-phase4.json` straight over the Mac's, so
# `--report` began reading the lab's verdicts beside the Mac's answers. The
# Mac's rows survived only because git had them (`169e94c`: D 40/2/5 against
# the lab's 36/5/6).
#
# A stamp tells you afterwards which machine a row came from. A distinct path
# stops the second machine from destroying the first one's evidence in the
# first place -- and comparing the two runs is the entire point of running it
# twice (`D83`).
ROWS_DEFAULT = REPO / "deliverables" / f"faithfulness-phase4.{machine()}.json"
ROWS_LEGACY = REPO / "deliverables" / "faithfulness-phase4.json"
SHEET_DEFAULT = REPO / "deliverables" / "JUDGE-AGREEMENT.md"
CROSSCHECK_DEFAULT = REPO / "deliverables" / "JUDGE-CROSSCHECK.json"


def _golden_items() -> list[dict]:
    data = json.loads((REPO / "deliverables" / "golden.json").read_text())
    return [i for i in data["items"] if i.get("verified_by") == "human"]


def _arg(argv: list[str], flag: str, default=None):
    """The token after `flag`, unless that token is itself a flag.

    `--sweep` takes an optional path, so `--sweep --variants D,H` must read as
    "default sweep file" rather than as a file literally named `--variants`.
    Without the guard that is a FileNotFoundError naming the wrong thing.
    """
    if flag not in argv:
        return default
    nxt = argv.index(flag) + 1
    if nxt >= len(argv) or argv[nxt].startswith("--"):
        return default
    return argv[nxt]


def main() -> None:
    argv = sys.argv[1:]
    local = "--local" in argv
    key = api_key()
    if not key and not local:
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
        ok, out = check(key, post=retrying())
        print(f"key: found ({len(key)} chars)")
        print(f"pinned MODEL: {MODEL}")
        print(f"one call: {'OK' if ok else 'FAILED'}")
        print(f"  {out}")
        if not ok:
            print("\n  --models lists what this key can actually reach.")
            sys.exit(1)
        return

    if "--sweep" in argv:
        # Judges SAVED answers. It does not generate: D54 says a re-run drifts,
        # and a faithfulness row describing a different answer than the one
        # D72/D73 were computed from is worse than no row at all.
        src_path = pathlib.Path(_arg(argv, "--sweep", str(SWEEP_DEFAULT)))
        saved = json.loads(src_path.read_text())
        if "rows" in saved:                       # a judge --save file
            saved = {"(saved run)": saved["rows"]}
        variants = _arg(argv, "--variants", "D,H").split(",")
        missing = [v for v in variants if v not in saved]
        if missing:
            sys.exit(f"{src_path} has no variant(s) {missing}; it holds "
                     f"{sorted(saved)}")
        items = _golden_items()
        if "--limit" in argv:
            items = items[: int(_arg(argv, "--limit"))]
        model = _arg(argv, "--model", LOCAL_MODEL if local else MODEL)
        # `--resume` picks up a run that died or was killed. It is NOT a way to
        # spread a run across days: D78's binding property is same judge, both
        # arms, one sitting. What makes a resume safe here is that the sweep
        # judges D and H back-to-back on each item, so a gap falls BETWEEN
        # items rather than between arms -- and the judge is a local model with
        # fixed weights at temperature 0, so it is the same reader on either
        # side of the gap. A resume across a model change is refused rather
        # than silently mixed.
        resume = None
        _rows_path = pathlib.Path(_arg(argv, "--save", str(ROWS_DEFAULT)))
        if "--resume" in argv and _rows_path.exists():
            prior = json.loads(_rows_path.read_text())
            if prior.get("judge_model") != model:
                sys.exit(f"cannot resume: those rows were judged by "
                         f"{prior.get('judge_model')}, this run uses {model}.\n"
                         f"  Two judges in one comparison is not a comparison "
                         f"(D78). Delete the file, or pass --model {prior.get('judge_model')}.")
            resume = prior.get("variants", {})
            print(f"resuming: {sum(len(r) for r in resume.values())} rows "
                  f"already judged by {model}", flush=True)
        # No quota locally, so no pacing: the 6-second gap exists only to stay
        # under a per-minute API ceiling and would add 11 minutes for nothing.
        post = retrying(local_post) if local else retrying()
        pace = 0.0 if local else PACE_SECONDS
        out = pathlib.Path(_arg(argv, "--save", str(ROWS_DEFAULT)))
        if out.exists() and "--resume" not in argv:
            prior = json.loads(out.read_text()).get("machine")
            if prior and prior != machine():
                sys.exit(
                    f"{out.name} holds rows from {prior}; this host is "
                    f"{machine()}.\n"
                    f"  Overwriting would destroy the other machine's evidence, "
                    f"and comparing the two is the point (D83).\n"
                    f"  Default path for this host: {ROWS_DEFAULT.name}")

        def save(rows):
            out.write_text(json.dumps({"judge_model": model,
                                       "machine": machine(),
                                       "source": src_path.name,
                                       "variants": rows}, indent=1) + "\n")

        print(f"judging {', '.join(variants)} from {src_path.name} with "
              f"{model} - one sitting, both arms, identical passages (D78)")
        try:
            rows = sweep_rows(saved, items, variants, key=key or "", model=model,
                              post=post, checkpoint=save, pace=pace,
                              resume=resume,
                              workers=int(_arg(argv, "--workers", "1")),
                              log=lambda line: print(line, flush=True))
        except urllib.error.HTTPError as exc:
            # D75: a sweep that dies with nothing written is the expensive
            # failure. Say what died, and say what survived.
            hint = ("  the free tier is 20 requests PER DAY PER MODEL "
                    "(measured 2026-09-03); this run needs ~110.\n"
                    "  --local judges with Ollama instead: no quota, and D78 "
                    "names it as the fallback.\n"
                    if exc.code == 429 else
                    "  --models lists what this key can reach; --model picks "
                    "another without a code edit.\n")
            sys.exit(f"\njudge {model} failed with HTTP {exc.code} and did not "
                     f"recover after {RETRY_ATTEMPTS} attempts.\n"
                     f"{hint}"
                     f"  rows written so far: {out}")
        report(rows)
        save(rows)
        print(f"\nsaved {sum(len(r) for r in rows.values())} rows to {out}")
        return

    if "--claims" in argv:
        # The deep dive the aggregate points at. One item, one call per
        # sentence, so the answer is WHICH sentence rather than how many
        # answers.
        item_id = _arg(argv, "--claims")
        variant = _arg(argv, "--variant", "D")
        saved = json.loads(pathlib.Path(
            _arg(argv, "--sweep-file", str(SWEEP_DEFAULT))).read_text())
        row = next((r for r in saved[variant] if r["id"] == item_id), None)
        if row is None:
            sys.exit(f"{item_id} is not in variant {variant}")
        item = next(i for i in _golden_items() if i["id"] == item_id)
        from rag import ask, index
        passages = [h.payload["text"]
                    for h in index.retrieve(item["question"],
                                            limit=ask.DEFAULT_K)]
        post = retrying(local_post) if local else retrying()
        model = _arg(argv, "--model", LOCAL_MODEL if local else MODEL)
        print(f"{item_id} under prompt {variant}, sentence by sentence "
              f"({model}):\n")
        for n, claim in enumerate(sentences(prose(row["answer"])), 1):
            verdict = judge_claim(claim, passages, key=key or "", model=model,
                                  post=post)
            print(f"  [{n}] {verdict['verdict']}")
            print(f"      claim : {claim[:150]}")
            print(f"      reason: {verdict['reason'][:150]}\n")
        return

    if "--cross-check" in argv:
        # A SECOND judge on the SAME ten the human will read. Not a
        # replacement for the human -- two models agreeing can both be wrong in
        # the same direction, which is the whole reason Step 5 asks for a
        # person. What it does buy is a cheap prior on WHERE to look, and it
        # fits the free tier: ten calls against a 20/day/model ceiling (D80).
        #
        # It exists because of one measured disagreement. `g056` -- D77's named
        # blind spot -- is SUPPORTED under gemma4:e4b and PARTIAL under
        # gemini-3.6-flash (D78). One item is not a pattern; ten is a start.
        rows_path = pathlib.Path(_arg(argv, "--rows", str(ROWS_DEFAULT)))
        if not rows_path.exists():
            sys.exit(f"{rows_path} does not exist - run --sweep first")
        saved = json.loads(rows_path.read_text())
        sample = agreement_sample(saved["variants"], int(_arg(argv, "--n", "10")))
        second = _arg(argv, "--cross-check", MODEL)
        if same_model(second, saved.get("judge_model", "")):
            sys.exit(f"--cross-check {second} is the SAME MODEL that produced "
                     f"these rows ({saved.get('judge_model')}); a model "
                     f"agreeing with itself measures nothing.\n"
                     f"  Names differing is not enough — on this machine "
                     f"gpt-5.5:latest and gemma4:e4b share one digest.")
        from rag import ask, index
        items = {i["id"]: i for i in _golden_items()}
        post = retrying()
        print(f"cross-checking {len(sample)} verdicts: "
              f"{saved.get('judge_model')} (rows) vs {second} (second opinion)\n")
        agree = asked = asked_failed = 0
        seconds = {}
        for row in sample:
            passages = [h.payload["text"] for h in
                        index.retrieve(items[row["id"]]["question"],
                                       limit=ask.DEFAULT_K)]
            # A second opinion is best-effort by definition, so one bad call
            # must not throw away the ones already collected. Measured
            # 2026-09-03: this died on item 6 of 10 with a 503 and printed
            # nothing but a traceback -- D75's shape for the third time in one
            # day, in the one place I had already written the lesson down.
            try:
                got = judge_claim(row["claim"], passages, key=key,
                                  model=second, post=post)
            except (urllib.error.HTTPError, urllib.error.URLError,
                    TimeoutError) as exc:
                code = getattr(exc, "code", exc)
                print(f"  {row['id']:<6} {row['variant']:<2} "
                      f"{row['verdict']:<12} -> (no answer: {code})")
                asked_failed += 1
                continue
            same = got["verdict"] == row["verdict"]
            agree += same
            asked += 1
            seconds[f"{row['variant']}:{row['id']}"] = {
                "verdict": got["verdict"], "reason": got["reason"],
                "judge_model": got["judge_model"]}
            print(f"  {row['id']:<6} {row['variant']:<2} "
                  f"{row['verdict']:<12} -> {got['verdict']:<12} "
                  f"{'agree' if same else 'DIFFER'}")
            if not same:
                print(f"         {second}: {got['reason'][:110]}")
        # The denominator is what was actually answered, and the unanswered
        # count prints beside it. A rate over "the ones that worked" with the
        # failures quietly dropped is the flattering shape this repo keeps
        # catching.
        out = pathlib.Path(_arg(argv, "--save", str(CROSSCHECK_DEFAULT)))
        out.write_text(json.dumps({"second_model": second,
                                   "rows_judge": saved.get("judge_model"),
                                   "verdicts": seconds}, indent=1) + "\n")
        print(f"\n  {agree}/{asked} = {agree/asked:.0%} model-to-model agreement"
              if asked else "\n  no verdicts came back")
        print(f"  saved to {out} — --agreement puts both opinions on the sheet")
        if asked_failed:
            print(f"  {asked_failed} of {len(sample)} got no answer from "
                  f"{second} — free tier is 20/day/model (D80)")
        print("  This is NOT the Step 5 number. Two models can be wrong the "
              "same way; only a human closes it (D06).")
        return

    if "--agreement" in argv:
        rows_path = pathlib.Path(_arg(argv, "--rows", str(ROWS_DEFAULT)))
        if not rows_path.exists():
            sys.exit(f"{rows_path} does not exist - run --sweep first")
        saved = json.loads(rows_path.read_text())
        sample = agreement_sample(saved["variants"],
                                  int(_arg(argv, "--n", "10")))
        out = pathlib.Path(_arg(argv, "--out", str(SHEET_DEFAULT)))
        cross = CROSSCHECK_DEFAULT
        second = (json.loads(cross.read_text()).get("verdicts")
                  if cross.exists() else None)
        n = agreement_sheet(sample, _golden_items(), out, second=second)
        counts = {}
        for row in sample:
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        print(f"{n} verdicts -> {out}")
        print("  " + ", ".join(f"{v} {c}" for v, c in sorted(counts.items())))
        print("D06: a human agrees or disagrees. This script does not.")
        return

    sys.exit(__doc__.strip().splitlines()[0]
             + "\n\n  pass --check, --models, --sweep, --claims or "
               "--agreement")


if __name__ == "__main__":
    main()
