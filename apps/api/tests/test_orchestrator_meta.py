"""Guards against chain-of-thought / rubric text in visible debate lines."""

from app.debate.orchestrator import (
    _is_degenerate_repetitive_output,
    _keep_first_non_meta_sentences,
    _looks_like_moderator_echo,
    _scrub_transcript_tail_for_prompt,
    _sentence_smells_meta,
)


def test_sentence_smells_meta_flags_planning():
    assert _sentence_smells_meta("We need to output as Ethical Guardian.")
    assert _sentence_smells_meta('Check no meta. No "we".')
    assert not _sentence_smells_meta(
        "Risk Guru, late-night cramming often cuts sleep enough to wipe next-day gains."
    )


def test_keep_first_non_meta_sentences_skips_prefix():
    blob = (
        "We need to output as Data Analyst. Must be three sentences. "
        "I'd lean toward studying tonight because measurable exam readiness typically matters."
    )
    out = _keep_first_non_meta_sentences(blob, 3)
    assert "We need to output" not in out
    assert "Must be three" not in out
    assert "lean toward studying" in out


def test_keep_first_non_meta_interjection_style():
    t = (
        'Check no meta. No "we". Avoid repeating Data Analyst. '
        "Research shows brief walks after reading improve retention by a few percent."
    )
    out = _keep_first_non_meta_sentences(t, 2)
    assert "Check no meta" not in out
    assert "Research shows" in out


def test_degenerate_repetition_detected():
    loop = "We answered: Yes " * 40
    assert _is_degenerate_repetitive_output(loop)
    assert not _is_degenerate_repetitive_output(
        "Risk Guru, surveys show most participants exit within a year with net losses after purchases."
    )


def test_sentence_smells_meta_flags_instruction_echo():
    assert _sentence_smells_meta("We answered: YesWe answered: YesWe answered: Yes")


def test_scrub_drops_instruction_echo_lines():
    blob = (
        "[Turn 2][Data Analyst]: Tracking hours matters.\n"
        "Must be in-character, spoken dialogue only.\n"
        "Risk Guru, the downside is real."
    )
    out = _scrub_transcript_tail_for_prompt(blob)
    assert "Must be in-character" not in out
    assert "Risk Guru" in out


def test_moderator_echo_detected():
    assert _looks_like_moderator_echo(
        "Must be in-character, spoken dialogue only. Must agree or disagree."
    )
    assert not _looks_like_moderator_echo(
        "Risk Guru, surveys show most participants exit within a year with net losses."
    )
