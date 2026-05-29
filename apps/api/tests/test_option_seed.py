import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.environment_ops import init_environment
from app.debate.orchestrator import (
    _closing_from_environment,
    _heuristic_options_from_context,
    _instant_default_closing,
)


OPEN_DEMO = """How do we build a product that customers actually love and will pay for?
And how do we survive long enough to scale it before running out of money?
"""


def test_heuristic_options_for_open_demo():
    opts = _heuristic_options_from_context(OPEN_DEMO)
    assert len(opts) >= 2
    titles = " ".join(o.title.lower() for o in opts)
    assert "love" in titles or "runway" in titles or "pmf" in titles


def test_closing_from_environment_uses_seeded_options():
    env = init_environment(OPEN_DEMO, rng_seed=1, mode="swarm")
    seeded = _heuristic_options_from_context(OPEN_DEMO)
    from app.debate.environment_ops import merge_options

    env = merge_options(env, seeded)
    closing = _closing_from_environment(env)
    assert len(closing.options) >= 2
    assert "Primary path from the debate" not in closing.options[0].title


def test_instant_default_only_when_no_env_options():
    closing = _instant_default_closing()
    assert closing.options[0].title == "Primary path from the debate"
