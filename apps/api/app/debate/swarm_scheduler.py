"""Decentralized speaker selection for swarm debate mode."""

from __future__ import annotations

import random
from typing import Any


def pick_next_agent_swarm(
    agents: list[dict[str, str]],
    rng: random.Random,
    speech_count: dict[str, int],
) -> dict[str, str]:
    """Pick an advisor with minimal speech_count; break ties uniformly at random."""
    m = min(speech_count[a["id"]] for a in agents)
    pool: list[dict[str, str]] = [a for a in agents if speech_count[a["id"]] == m]
    return rng.choice(pool)


def init_speech_counts(agents: list[dict[str, Any]]) -> dict[str, int]:
    return {a["id"]: 0 for a in agents}
