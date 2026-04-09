import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.swarm_scheduler import init_speech_counts, pick_next_agent_swarm


def test_pick_next_prefers_min_count():
    agents = [
        {"id": "a", "name": "A"},
        {"id": "b", "name": "B"},
    ]
    rng = random.Random(123)
    sc = init_speech_counts(agents)
    first = pick_next_agent_swarm(agents, rng, sc)
    sc[first["id"]] += 1
    second = pick_next_agent_swarm(agents, rng, sc)
    assert second["id"] != first["id"]
