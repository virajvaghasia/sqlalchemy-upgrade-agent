"""
Pin the three D43 prompt variants.

These tests never call Ollama. They check the only thing that can silently
rot: that the three system prompts still differ in exactly one sentence, and
that B is still the string `rag.ask` actually ships. If someone edits
`ask.SYSTEM` and forgets this file, B stops being the shipped prompt and the
comparison quietly measures something else.
"""

from rag import ask, compare_prompts as cp


def test_the_shipped_variant_is_ask_system_not_a_copy():
    """
    B must BE ask.SYSTEM — the object identity check — AND ask.SYSTEM must still
    carry the last-resort wording D43 settled on.

    The identity half alone is worthless: `system_prompt("B")` returns
    `ask.SYSTEM`, so comparing the two is a string compared to itself and
    cannot fail. Mutation-checking caught exactly that (D25). The second half
    is what actually pins production, so editing the shipped clause without
    revisiting D43 breaks a test.
    """
    assert cp.system_prompt("D") is ask.SYSTEM, "the sentinel moved to D when D shipped (D54)"
    assert "even partially" in ask.SYSTEM
    assert "name the specific thing you looked for" in ask.SYSTEM
    assert "say exactly" not in ask.SYSTEM, "that is prompt A's wording"
    assert "genuinely silent" not in ask.SYSTEM, "that is prompt B's, replaced 2026-08-17"


def test_variants_differ_only_in_the_refusal_clause():
    """Strip the refusal sentence from each and the remainder must be identical."""
    a, b, c = (cp.system_prompt(v) for v in "ABC")
    strict = cp.REFUSAL_CLAUSES["A"]
    last_resort = (
        "Prefer answering from what the sources do say, even if they address the question "
        "indirectly. Only if the sources are genuinely silent on the topic, reply: "
        "\"The sources do not answer this.\" "
    )
    assert a.replace(strict, "") == c
    assert b.replace(last_resort, "") == c


def test_a_makes_refusal_the_exit_and_c_removes_it():
    a, c = cp.system_prompt("A"), cp.system_prompt("C")
    assert "say exactly" in a, "A must instruct the canned sentence"
    assert "The sources do not answer this" not in c, "C must grant no permission to refuse"
    assert len(c) < len(a) < len(cp.system_prompt("B"))


def test_both_question_kinds_are_present():
    """One answerable, one the corpus provably cannot answer — the point of the test."""
    kinds = [k.strip() for k, _ in cp.QUESTIONS]
    assert kinds == ["ANSWERABLE", "UNANSWERABLE"]


def test_unanswerable_question_is_a_real_corpus_hole():
    """
    The unanswerable question must actually be unanswerable, or C's failure
    proves nothing. `Session.execute`'s signature lives in the API reference,
    which D07 excluded — so no chunk carries the argument list.
    """
    import json
    from rag import corpus

    _, question = cp.QUESTIONS[1]
    assert "signature" in question and "Session.execute" in question

    path = corpus.REPO_ROOT / "corpus" / "chunks.jsonl"
    if not path.exists():          # corpus not built in this checkout
        return
    with open(path) as fh:
        hits = sum(1 for line in fh if ".. automethod:: Session.execute" in line)
    assert hits == 0, "if the API reference ever enters the corpus, D43's C cell changes meaning"


def test_refusal_detector_is_not_a_verdict():
    """`refused` reports a cell, and is deliberately blind to correctness (D46)."""
    assert cp.refused("The sources do not answer this.")
    assert not cp.refused("You can no longer call engine.execute() because [1]...")


def test_the_refusal_detector_is_ask_pys_not_a_second_implementation(monkeypatch):
    """It held its own `.lower().startswith(...)` until 2026-08-22, which missed
    a refusal with a leading space that ask.py caught. One concept, one detector,
    beside the prompt clause that mandates the string.

    Unified on evidence: over the 100 answers the first golden sweep saved, the
    two implementations disagreed on zero, so no recorded number moved."""
    monkeypatch.setattr(cp.ask, "refused", lambda a: a == "sentinel")
    assert cp.refused("sentinel")
    assert not cp.refused("The sources do not answer this.")


def test_a_leading_space_no_longer_hides_a_refusal():
    """The concrete case the two implementations disagreed on."""
    assert cp.refused(" The sources do not answer this.")


def test_sweep_all_covers_every_probe_question():
    """
    --all must run the whole probe set, not a subset.

    D43 chose a prompt on two questions and Round 7 found it refusing 8 of 19
    (D51) — a rate the original experiment was too small to see. A sweep that
    quietly sampled would reproduce exactly that mistake.
    """
    from rag import probe
    import inspect as _inspect
    src = _inspect.getsource(cp.sweep_all)
    assert "probe.QUESTIONS" in src, "the sweep must iterate the full question set"
    assert "[:5]" not in src and "sample" not in src, "no subsetting"
    assert len(probe.QUESTIONS) == 19


def test_prompt_d_is_a_different_mechanism_not_a_tuned_b():
    """
    D must differ from B in kind, not degree.

    D52: A and B refused the same 8 questions, identically — the search space
    was two points that turned out to be one. A fourth wording that merely
    softens B's adverbs would repeat that. So D is pinned on the two things
    that make it a different mechanism: partial answers are expected output,
    and a refusal must name what was looked for.
    """
    d, b = cp.system_prompt("D"), cp.system_prompt("B")
    assert d != b
    assert "even partially" in d, "partial answers must be the expected output"
    assert "name the specific thing you looked for" in d, "refusal must require naming"
    assert "genuinely silent" not in d, "that is B's sufficiency test — D must not inherit it"
    # the shared scaffolding is unchanged, so the comparison stays controlled
    for shared in ("cite the source number in brackets", "if versions", "1.4 to 2.0"):
        assert shared in d and shared in b, shared


def test_every_variant_shares_the_same_scaffolding():
    """Only the refusal sentence may vary, or the comparison measures something else."""
    for v in cp.REFUSAL_CLAUSES:
        s = cp.system_prompt(v)
        assert s.startswith("You answer questions about migrating Python code")
        assert s.endswith("picking one silently.")


# --- Phase 4 variants (D72 / D73) --------------------------------------------

def test_phase4_variants_are_built_from_the_shipped_prompt_not_retyped():
    """If ask.SYSTEM changes, E/F/G must change with it. A retyped copy would
    quietly start comparing new wordings against a prompt nobody runs -- which
    is the failure D43 had, and the reason this whole module exists."""
    for v in ("E", "F", "G"):
        s = cp.system_prompt(v)
        assert "The sources do not answer this." in s, "D's refusal sentence must survive"
        assert "Each source is labelled with the SQLAlchemy version" in s


def test_the_stale_citation_sentence_guard_fires():
    """_CITE_D is quoted from ask.SYSTEM. If the shipped prompt reworded that
    sentence, .replace() would silently no-op and E would BE D -- a null result
    that looks like a measurement."""
    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(cp.ask, "SYSTEM", "a prompt with no citation sentence in it")
        with _pytest.raises(AssertionError, match="_CITE_D is stale"):
            cp.system_prompt("E")


def test_e_and_f_change_different_things():
    """E attacks citations (D73), F attacks over-refusal (D72). If both edited
    the same sentence, the sweep could not tell which lever moved a number."""
    e, f = cp.system_prompt("E"), cp.system_prompt("F")
    assert "not acceptable" in e and "not acceptable" not in f
    assert "search engine" in f and "search engine" not in e
    assert "not acceptable" in cp.system_prompt("G")
    assert "search engine" in cp.system_prompt("G")


def test_h_keeps_the_shipped_system_prompt_and_moves_the_rule_to_the_user_turn():
    """H is a position change, not a wording change: same system message as what
    ships, the requirement placed next to the ANSWER cue. The smoke run is why
    -- E stated the rule as hard as English allows and g002 came back with zero
    citations anyway."""
    assert cp.system_prompt("H") is cp.ask.SYSTEM
    prompt = cp.ask.build_prompt("q", [])
    assert cp.user_prompt("H", prompt) != prompt


def test_the_reminder_lands_before_the_answer_cue_not_after_it():
    """Anything after "ANSWER:" reads as the opening of the answer itself, so
    the model would be completing our sentence rather than obeying it."""
    out = cp.user_prompt("H", cp.ask.build_prompt("q", []))
    assert out.endswith("ANSWER:")
    assert out.count("ANSWER:") == 1
    assert "cite the source number" in out


def test_variants_without_a_suffix_leave_the_user_prompt_untouched():
    """D is the control. If the sweep altered its user message too, every
    comparison would be against something that never ran in production."""
    prompt = cp.ask.build_prompt("q", [])
    for v in ("A", "B", "C", "D", "E", "F", "G"):
        assert cp.user_prompt(v, prompt) == prompt


def test_all_variants_is_every_variant():
    """--prompt validates against this. A variant missing from it is one the
    CLI rejects while the sweep still runs it."""
    assert set(cp.ALL_VARIANTS) == set(cp.REFUSAL_CLAUSES) | set(cp.PHASE4_VARIANTS)
    assert set(cp.LABELS) == set(cp.ALL_VARIANTS), "every variant needs a label"


# --- surviving a bad night ----------------------------------------------------
#
# A sweep is ~300 generations over several hours. On 2026-08-22 one Ollama call
# exceeded its timeout at item 150 and the whole run died with nothing written:
# urllib raises socket.timeout, which is a TimeoutError and NOT a URLError, so
# it walked straight past the handler. Second time a long run in this repo has
# ended with zero output. These pin the fix, because the code paths only ever
# execute on a night that has already gone wrong.

def _failed(gid, answerable=True, in_prompt=True):
    return {"id": gid, "failed": True, "answerable": answerable,
            "answer_in_prompt": in_prompt}


def _ok(gid, refused, answerable=True, in_prompt=True, uncited=False):
    return {"id": gid, "failed": False, "answerable": answerable,
            "answer_in_prompt": in_prompt, "refused": refused, "uncited": uncited,
            "code_blocks": 0, "uncited_code_blocks": 0, "out_of_range": []}


def test_a_failed_generation_is_neither_an_answer_nor_a_refusal(capsys):
    """Counting it either way lets a flaky night read as a prompt effect.

    **Changed 2026-09-10: this test used to assert `1/1` and that was the bug.**
    A failed row leaves the NUMERATOR, never the denominator. Dropping it from
    both gave each arm its own ruler -- H measured 47/90 here against a
    published 47/91 -- which is precisely what `D61` forbids and what
    `judge._sweep_generation` had already been fixed for. The two modules
    disagreed and only the judge side had a test."""
    results = {"D": [_ok("g001", refused=False), _failed("g002")]}
    cp._report_golden(results, ["D"])
    out = capsys.readouterr().out
    # One answerable item reached the prompt and was answered; the failed one
    # must not appear in the end-to-end numerator -- but it is still an
    # answerable item, so it stays in the denominator.
    assert "1/2" in out


def test_pairing_drops_items_that_failed_on_either_side(capsys):
    """A flip needs both halves. If the control failed and the variant answered,
    that is not a fix -- it is a missing measurement."""
    results = {
        "D": [_failed("g001"), _ok("g002", refused=True)],
        "H": [_ok("g001", refused=False), _ok("g002", refused=False)],
    }
    cp._report_golden(results, ["D", "H"])
    out = capsys.readouterr().out
    assert "g002" in out, "the genuine flip must be reported"
    assert "g001" not in out, "the unpaired item must not be counted as a fix"


def test_generate_retries_a_timeout_before_giving_up(monkeypatch):
    """One retry costs seconds. Not retrying cost ~50 minutes of generations."""
    calls = []

    def flaky(request, timeout=None):
        calls.append(timeout)
        raise TimeoutError("slow")

    monkeypatch.setattr(cp.urllib.request, "urlopen", flaky)
    with __import__("pytest").raises(TimeoutError, match="failed twice"):
        cp.generate("sys", "prompt")
    assert calls == [300, 900], "second attempt must allow longer, not repeat the same ceiling"


def test_a_timeout_is_not_mistaken_for_ollama_being_down(monkeypatch):
    """URLError means 'no server' and exits; a timeout means 'this one was slow'
    and must not. They arrived at the same handler until 2026-08-22."""
    monkeypatch.setattr(cp.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("slow")))
    try:
        cp.generate("sys", "prompt")
    except SystemExit:  # pragma: no cover
        raise AssertionError("a slow generation must not be reported as Ollama being down")
    except TimeoutError:
        pass


def test_uncited_counts_every_answer_the_user_sees_not_just_answerable_ones():
    """One metric, one denominator (`D85`).

    This table and `judge --report` both print a column called `uncited`, and
    they disagreed: `cells()` counted **answerable items only**, while
    `_sweep_citations` counted **every answered row**. Same saved data, D read
    `18/45 = 40%` in one command and `20/47 = 43%` in the other.

    The two rows in the gap are answers to items marked `answerable: false` --
    the fabrications. Excluding them excludes exactly the answers least worth
    trusting, and a user has no idea which of their questions was unanswerable.
    An answer on screen with no source is the defect `D73` names, whatever the
    label on the question says."""
    rows = [_ok("g001", refused=False, answerable=True, uncited=True),
            _ok("g002", refused=False, answerable=False, uncited=True),
            _ok("g003", refused=True, answerable=True)]
    got = cp.cells(rows)
    assert got["answered"] == 2, "the fabricated answer is still an answer"
    assert got["uncited"] == 2


def test_the_fabricated_answer_is_still_counted_as_a_fabrication():
    """The other column must not double-shift: including unanswerable answers
    in the citation denominator does not change what `fabr` means."""
    rows = [_ok("g001", refused=False, answerable=True),
            _ok("g002", refused=False, answerable=False)]
    got = cp.cells(rows)
    assert got["fabricated"] == 1
    assert got["n_ans"] == 1


def test_a_failed_row_is_in_no_citation_denominator():
    """D75: a row that never got a generation is not an answer."""
    rows = [_ok("g001", refused=False, answerable=True, uncited=True),
            {"id": "g002", "failed": True, "answerable": True,
             "answer_in_prompt": True}]
    assert cp.cells(rows)["answered"] == 1


def test_the_two_commands_report_the_same_uncited_number():
    """The guard that would have caught `D85` on the day it appeared.

    `compare_prompts --golden` and `judge --report` each print a column called
    `uncited`, computed in different modules. They drifted apart and nothing
    noticed, because no test ever asked them the same question. This one runs
    both derivations over the real saved sweep and requires the answer to
    match -- so a future private copy of the rule fails here rather than in a
    doc six weeks later."""
    import json
    from rag import judge
    sweep = json.loads(
        (judge.DELIVERABLES / judge.SWEEP_NAME).read_text())
    for variant in ("D", "H", "I"):
        mine = cp.cells(sweep[variant])
        theirs, _ = judge._sweep_citations(sweep[variant])
        assert mine["answered"] == theirs["n_answered"], variant
        assert mine["uncited"] == theirs["uncited"], variant
        assert mine["with_code"] == theirs["with_code"], variant
        assert mine["uncited_code"] == theirs["uncited_code"], variant
        assert mine["out_of_range"] == theirs["out_of_range"], variant


def test_cells_reproduces_the_published_generation_figures():
    """`D72`/`D74`: D 39/91 and H 47/91 on the Mac sweep. Reading the stored
    `refused` field gave H 51/91 instead, because those rows predate `D76` --
    so this pins the re-scoring, not just the arithmetic."""
    import json
    from rag import judge
    sweep = json.loads((judge.DELIVERABLES / judge.SWEEP_NAME).read_text())
    assert cp.cells(sweep["D"])["end_to_end"] == 39
    assert cp.cells(sweep["H"])["end_to_end"] == 47
    assert cp.cells(sweep["I"])["end_to_end"] == 46


def test_both_arms_are_scored_against_the_same_denominator():
    """D61: a paired comparison needs one ruler. A D75 failed row leaves the
    numerator, never the denominator -- otherwise the arm that hit a timeout
    is graded out of a smaller total and looks better for having failed."""
    rows = [_ok("g001", refused=False, answerable=True),
            {"id": "g002", "failed": True, "answerable": True,
             "answer_in_prompt": True}]
    got = cp.cells(rows)
    assert got["n_ans"] == 2, "the failed item is still an answerable item"
    assert got["end_to_end"] == 1
