import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.environment import SupportOptionAction
from app.debate.environment_adapter import (
    apply_classic_utter,
    apply_vote_supports,
    merge_vote_options,
)
from app.debate.environment_ops import apply_action, init_environment
from app.debate.schemas import VoteOptionItem


def test_merge_options_and_votes_shift_scores():
    env = init_environment("context " * 5, rng_seed=1)
    env = merge_vote_options(
        env,
        [
            VoteOptionItem(id="0", title="A"),
            VoteOptionItem(id="1", title="B"),
        ],
    )
    assert env.option_support_scores["0"] == 0.5
    votes = [
        {"agent_id": "optimist", "name": "Optimist", "option_id": "0", "rationale": ""},
        {"agent_id": "data_analyst", "name": "Data", "option_id": "0", "rationale": ""},
    ]
    env2 = apply_vote_supports(env, votes, n_agents=5)
    assert env2.option_support_scores["0"] > 0.5


def test_apply_classic_utter_increments_step():
    env = init_environment("x" * 20, rng_seed=0)
    env2 = apply_classic_utter(env, agent_id="optimist", text="hello", turn_ref=1)
    assert env2.step_index == 1
    assert len(env2.utterances) == 1


def test_support_after_merge():
    env = init_environment("ctx", rng_seed=0)
    env = merge_vote_options(env, [VoteOptionItem(id="0", title="Opt")])
    r = apply_action(env, SupportOptionAction(agent_id="optimist", option_id="0", delta=0.1))
    assert r.ok
    assert r.env.option_support_scores["0"] > 0.5
