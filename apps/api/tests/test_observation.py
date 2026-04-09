import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.environment import DebateOption
from app.debate.environment_ops import apply_action, init_environment, merge_options
from app.debate.environment import ProposeClaimAction
from app.debate.observation import ObservationConfig, build_observation, trim_context_for_observation


def test_trim_context_head_tail():
    long = "a" * 1500 + "MIDDLE" + "b" * 800
    out = trim_context_for_observation(long, max_chars=2000, head=1200, tail=600)
    assert "MIDDLE" in out or len(out) <= 2000
    assert "[…trimmed…]" in out


def test_claims_order_newest_first():
    env = init_environment("x" * 20, rng_seed=0)
    env = merge_options(env, [DebateOption(id="0", title="A")])
    e = apply_action(
        env,
        ProposeClaimAction(agent_id="optimist", text="first claim", option_ids=("0",)),
    ).env
    e = apply_action(
        e,
        ProposeClaimAction(agent_id="data_analyst", text="second claim", option_ids=()),
    ).env
    obs = build_observation(
        e,
        agent_id="optimist",
        agent_display_name="Optimist",
        context_text="decision context here",
        debate_seconds_remaining=99,
        config=ObservationConfig(claims_top_k=5, claim_text_max=160),
    )
    ids = [c["id"] for c in obs["claims_top_k"]]
    assert len(ids) == 2
    steps = [c["source_step"] for c in obs["claims_top_k"]]
    assert steps == sorted(steps, reverse=True)
    assert all(c["rank_basis"] == "recency" for c in obs["claims_top_k"])


def test_options_sorted_by_score():
    env = init_environment("ctx", rng_seed=0)
    env = merge_options(
        env,
        [
            DebateOption(id="0", title="Low"),
            DebateOption(id="1", title="High"),
        ],
    )
    env = env.model_copy(
        update={"option_support_scores": {"0": 0.2, "1": 0.9}},
    )
    obs = build_observation(
        env,
        agent_id="optimist",
        agent_display_name="O",
        context_text="c",
        debate_seconds_remaining=1,
    )
    assert obs["options"][0]["id"] == "1"
    assert obs["options"][1]["id"] == "0"
