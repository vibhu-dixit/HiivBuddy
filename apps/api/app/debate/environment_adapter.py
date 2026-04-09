"""Map classic debate events into DebateEnvironment actions."""

from __future__ import annotations

from typing import Any

from app.debate.environment import DebateOption, SupportOptionAction, UtterAction
from app.debate.environment_ops import apply_action, merge_options
from app.debate.schemas import VoteOptionItem


def apply_classic_utter(
    env,
    *,
    agent_id: str,
    text: str,
    turn_ref: int | None,
):
    from app.debate.environment import DebateEnvironment

    if not isinstance(env, DebateEnvironment):
        raise TypeError("env must be DebateEnvironment")
    r = apply_action(
        env,
        UtterAction(agent_id=agent_id, text=text, turn_ref=turn_ref),
    )
    return r.env if r.ok else env


def apply_classic_interjection(
    env,
    *,
    agent_id: str,
    text: str,
    turn_ref: int | None,
):
    return apply_classic_utter(env, agent_id=agent_id, text=text, turn_ref=turn_ref)


def merge_vote_options(env, options: list[VoteOptionItem]):
    dopts = [DebateOption(id=o.id, title=o.title) for o in options]
    return merge_options(env, dopts)


def apply_vote_supports(env, vote_records: list[dict[str, Any]], *, n_agents: int):
    """Each vote adds 1/n_agents to that option's support score (clamped in apply_action)."""
    delta = 1.0 / float(max(1, n_agents))
    e = env
    for vr in vote_records:
        aid = str(vr.get("agent_id") or "")
        oid = str(vr.get("option_id") or "")
        if not aid or not oid:
            continue
        r = apply_action(e, SupportOptionAction(agent_id=aid, option_id=oid, delta=delta))
        e = r.env if r.ok else e
    return e
