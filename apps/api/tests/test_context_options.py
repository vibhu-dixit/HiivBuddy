import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.context_options import parse_options_from_context, seed_environment_options_from_context
from app.debate.environment_ops import apply_action, init_environment
from app.debate.environment import SupportOptionAction


DEMO_CONTEXT = """We are a 12-person B2B SaaS company at $1.2M ARR.

Options we are weighing:
1) Build the integration to protect roughly $400k ARR
2) Offer a lighter workaround and protect the roadmap
3) Walk away and accept churn risk

Constraints: about 14 months of runway.
"""


def test_parse_demo_context_options():
    opts = parse_options_from_context(DEMO_CONTEXT)
    assert len(opts) == 3
    assert opts[0].id == "0"
    assert "integration" in opts[0].title.lower()
    assert opts[1].id == "1"
    assert opts[2].id == "2"


def test_seed_enables_support_option_during_swarm():
    env = init_environment(DEMO_CONTEXT, rng_seed=1, mode="swarm")
    env = seed_environment_options_from_context(env, DEMO_CONTEXT)
    r = apply_action(
        env,
        SupportOptionAction(agent_id="optimist", option_id="0", delta=0.1),
    )
    assert r.ok
    assert r.errors == ()
    assert r.env.option_support_scores["0"] > 0.5


def test_parse_requires_at_least_two_options():
    assert parse_options_from_context("Just one option:\n1) Only path") == []
