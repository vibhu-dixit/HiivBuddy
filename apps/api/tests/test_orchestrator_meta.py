"""Post-processing for visible debate lines (meta strip + sentence cap)."""

from app.debate.orchestrator import (
    _clean_primary_spoken_text,
    _is_degenerate_repetitive_output,
    _is_near_duplicate_primary,
    _looks_like_moderator_echo,
    _normalize_spoken_line,
    _scrub_transcript_tail_for_prompt,
)


def test_clean_primary_text_slices_after_i_think_when_present():
    blob = (
        "We need to output as Data Analyst. Must be three sentences. "
        "I think I'd lean toward studying tonight because measurable exam readiness typically matters."
    )
    out = _clean_primary_spoken_text(blob)
    assert out.startswith("I think")
    assert "We need to output" not in out


def test_clean_primary_text_keeps_natural_opening_without_i_think():
    blob = (
        "Honestly, sunrise wins on consistency—you're trading drama for sleep debt.\n\n"
        "Second paragraph stays."
    )
    out = _clean_primary_spoken_text(blob)
    assert "Honestly" in out
    assert "Second paragraph" in out


def test_normalize_spoken_line_caps_sentences():
    t = "I think one. Two here? Three! Four dropped."
    out = _normalize_spoken_line(t, 3)
    assert out == "I think one. Two here? Three!"
    assert "Four dropped" not in out


def test_degenerate_repetition_detected():
    loop = "We answered: Yes " * 40
    assert _is_degenerate_repetitive_output(loop)
    assert not _is_degenerate_repetitive_output(
        "I think surveys show most participants exit within a year with net losses after purchases."
    )


def test_scrub_drops_instruction_echo_lines():
    blob = (
        "[Turn 2][Data Analyst]: Tracking hours matters.\n"
        "Must be in-character, spoken dialogue only.\n"
        "I think the downside is real."
    )
    out = _scrub_transcript_tail_for_prompt(blob)
    assert "Must be in-character" not in out
    assert "I think" in out


def test_near_duplicate_primary_detected():
    a = "I think sunrise gives calm energy for tests without wrecking sleep cycles entirely."
    assert _is_near_duplicate_primary(a, a)
    assert _is_near_duplicate_primary(a, a + " ")
    assert not _is_near_duplicate_primary(a, "I think sunset fits night owls better.")


def test_moderator_echo_detected():
    assert _looks_like_moderator_echo(
        "Must be in-character, spoken dialogue only. Must agree or disagree."
    )
    assert not _looks_like_moderator_echo(
        "I think surveys show most participants exit within a year with net losses."
    )
