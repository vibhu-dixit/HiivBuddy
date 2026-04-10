"""Guards against chain-of-thought / rubric text in visible debate lines."""

from app.debate.orchestrator import (
    _keep_first_non_meta_sentences,
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
