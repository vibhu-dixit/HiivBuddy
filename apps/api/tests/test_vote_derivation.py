import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.environment import ActionLogEntry, UtteranceEntry
from app.debate.environment_ops import init_environment, merge_options
from app.debate.orchestrator import _closing_from_environment, _heuristic_options_from_context
from app.debate.vote_derivation import pick_agent_vote_option


OPEN_DEMO = """How do we build a product that customers actually love and will pay for?
And how do we survive long enough to scale it before running out of money?
"""


def _env_with_options():
    env = init_environment(OPEN_DEMO, rng_seed=1, mode="swarm")
    opts = _heuristic_options_from_context(OPEN_DEMO)
    return merge_options(env, opts)


def test_devils_advocate_dissents_when_mostly_attacking_consensus():
    env = _env_with_options()
    allowed = set(env.options_by_id.keys())
    panel_pick = "2"
    log = [
        ActionLogEntry(global_step=1, agent_id="devils_advocate", action="attack_option", payload_summary="attack:2:-0.1"),
        ActionLogEntry(global_step=2, agent_id="devils_advocate", action="attack_option", payload_summary="attack:2:-0.1"),
        ActionLogEntry(global_step=3, agent_id="devils_advocate", action="attack_option", payload_summary="attack:2:-0.1"),
        ActionLogEntry(global_step=4, agent_id="optimist", action="support_option", payload_summary="support:2:+0.3"),
    ]
    env = env.model_copy(
        update={
            "option_support_scores": {"0": 0.5, "1": 0.5, "2": 1.0},
            "action_log": log,
        },
    )
    devil_vote = pick_agent_vote_option(env, "devils_advocate", allowed, panel_pick=panel_pick)
    assert devil_vote != "2"


def test_closing_votes_are_not_all_identical_when_agents_disagree():
    env = _env_with_options()
    log = [
        ActionLogEntry(global_step=1, agent_id="devils_advocate", action="attack_option", payload_summary="attack:2:-0.2"),
        ActionLogEntry(global_step=2, agent_id="devils_advocate", action="attack_option", payload_summary="attack:2:-0.2"),
        ActionLogEntry(global_step=3, agent_id="optimist", action="support_option", payload_summary="support:2:+0.3"),
        ActionLogEntry(global_step=4, agent_id="risk_guru", action="support_option", payload_summary="support:1:+0.3"),
        ActionLogEntry(global_step=5, agent_id="data_analyst", action="support_option", payload_summary="support:2:+0.2"),
        ActionLogEntry(global_step=6, agent_id="ethical_guardian", action="support_option", payload_summary="support:2:+0.2"),
    ]
    env = env.model_copy(
        update={
            "option_support_scores": {"0": 0.5, "1": 0.6, "2": 0.95},
            "action_log": log,
            "utterances": [
                UtteranceEntry(
                    step=1,
                    agent_id="devils_advocate",
                    text="We must pick a dominant priority instead of dual-track compromise.",
                ),
            ],
        },
    )
    closing = _closing_from_environment(env)
    vote_ids = [v.option_id for v in closing.votes]
    assert len(set(vote_ids)) >= 2
    assert any(v.agent_id == "devils_advocate" and v.option_id != "2" for v in closing.votes)
    assert any(v.rationale for v in closing.votes)


def test_build_report_from_votes_on_split():
    from app.debate.orchestrator import _build_report_from_votes

    report = _build_report_from_votes(
        context="Should we dual-track or pick one path?",
        id_to_title={"1": "Runway-first", "2": "Dual-track"},
        tallies={"1": 2, "2": 3},
        vote_records=[
            {"agent_id": "a", "name": "A", "option_id": "2", "rationale": ""},
            {"agent_id": "b", "name": "B", "option_id": "1", "rationale": ""},
        ],
        consensus_reached=True,
        winning_option_id="2",
        winning_title="Dual-track",
        threshold=3,
    )
    assert "Dual-track" in report.summary
    assert len(report.ranked_options) >= 2
    assert report.next_steps


def test_transcript_for_synth_truncates_long_debate():
    from app.debate.orchestrator import _transcript_for_synth

    long = "x" * 30_000
    out = _transcript_for_synth(long)
    assert len(out) < len(long)
    assert "omitted for synthesis" in out
