"""Debate API request defaults and validation."""

from app.debate.schemas import DebateRequest


def test_debate_request_defaults_swarm_mode():
    r = DebateRequest(context="x" * 10)
    assert r.session_mode == "swarm"


def test_debate_request_accepts_classic_explicit():
    r = DebateRequest(context="y" * 10, session_mode="classic")
    assert r.session_mode == "classic"
