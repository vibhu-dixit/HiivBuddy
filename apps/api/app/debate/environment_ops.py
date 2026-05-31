"""Pure transitions and serialization for DebateEnvironment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.debate.environment import (
    ActionLogEntry,
    AgentAction,
    AgentState,
    AttackOptionAction,
    ClaimRecord,
    DebateEnvironment,
    DebateOption,
    DEFAULT_ADVISOR_IDS,
    EdgeRecord,
    EnvHooks,
    EnvLimits,
    LinkAction,
    PassAction,
    ProposeClaimAction,
    SupportOptionAction,
    UtterAction,
    UtteranceEntry,
    hash_context,
    new_session_id,
)


@dataclass(frozen=True)
class ApplyResult:
    ok: bool
    env: DebateEnvironment
    errors: tuple[str, ...] = ()


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def init_environment(
    context_text: str,
    *,
    rng_seed: int,
    limits: EnvLimits | None = None,
    agent_ids: tuple[str, ...] | None = None,
    mode: str = "classic",
    session_id: str | None = None,
) -> DebateEnvironment:
    lim = limits or EnvLimits()
    ids = tuple(sorted(agent_ids or DEFAULT_ADVISOR_IDS))
    mode_norm: str = mode if mode in ("classic", "swarm") else "classic"
    agents = {aid: AgentState() for aid in ids}
    return DebateEnvironment(
        session_id=session_id or new_session_id(),
        mode=mode_norm,  # type: ignore[arg-type]
        step_index=0,
        rng_seed=int(rng_seed),
        limits=lim,
        context_ref=hash_context(context_text),
        agent_state_by_id=agents,
    )


def _trim_tail_utterances(env: DebateEnvironment, entry: UtteranceEntry) -> list[UtteranceEntry]:
    cap = env.limits.max_utterances_stored
    tail = [*env.utterances, entry]
    return tail[-cap:] if len(tail) > cap else tail


def _short_summary(s: str, n: int = 80) -> str:
    t = s.strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _summarize_applied_action(
    action: AgentAction,
    *,
    created_claim_id: str | None = None,
) -> tuple[str, str]:
    if isinstance(action, PassAction):
        return "pass", "pass"
    if isinstance(action, UtterAction):
        return "utter", _short_summary(action.text)
    if isinstance(action, SupportOptionAction):
        return "support_option", f"support:{action.option_id}:+{action.delta}"
    if isinstance(action, AttackOptionAction):
        return "attack_option", f"attack:{action.option_id}:-{action.delta}"
    if isinstance(action, ProposeClaimAction):
        return "propose_claim", f"claim:{created_claim_id or '?'}"
    if isinstance(action, LinkAction):
        return (
            "link",
            f"link:{action.src_claim_id}->{action.dst_claim_id}:{action.rel}",
        )
    return "unknown", "?"


def _append_action_log(
    env: DebateEnvironment,
    *,
    global_step: int,
    agent_id: str,
    kind: str,
    summary: str,
) -> DebateEnvironment:
    cap = env.limits.max_action_log_entries
    entry = ActionLogEntry(
        global_step=global_step,
        agent_id=agent_id,
        action=kind,
        payload_summary=summary,
    )
    tail = [*env.action_log, entry]
    if len(tail) > cap:
        tail = tail[-cap:]
    return env.model_copy(update={"action_log": tail})


def apply_action(env: DebateEnvironment, action: AgentAction) -> ApplyResult:
    if env.hooks.steps_applied >= env.limits.max_steps_per_session:
        return ApplyResult(False, env, ("max_steps_per_session",))

    if isinstance(action, PassAction):
        if action.agent_id not in env.agent_state_by_id:
            return ApplyResult(False, env, ("unknown_agent",))
        nxt = env.model_copy(deep=True)
        new_step = nxt.step_index + 1
        nxt.step_index = new_step
        st = nxt.agent_state_by_id[action.agent_id].model_copy(
            update={"last_step_index": new_step},
        )
        nxt.agent_state_by_id = {**nxt.agent_state_by_id, action.agent_id: st}
        nxt.hooks = nxt.hooks.model_copy(
            update={
                "steps_applied": nxt.hooks.steps_applied + 1,
                "passes": nxt.hooks.passes + 1,
            },
        )
        ka, sm = _summarize_applied_action(action)
        nxt = _append_action_log(
            nxt,
            global_step=new_step,
            agent_id=action.agent_id,
            kind=ka,
            summary=sm,
        )
        return ApplyResult(True, nxt, ())

    if isinstance(action, UtterAction):
        if action.agent_id not in env.agent_state_by_id:
            return ApplyResult(False, env, ("unknown_agent",))
        if len(action.text) > env.limits.max_utter_chars:
            return ApplyResult(False, env, ("utter_too_long",))
        nxt = env.model_copy(deep=True)
        new_step = nxt.step_index + 1
        nxt.step_index = new_step
        st = nxt.agent_state_by_id[action.agent_id].model_copy(
            update={"last_step_index": new_step},
        )
        nxt.agent_state_by_id = {**nxt.agent_state_by_id, action.agent_id: st}
        nxt.hooks = nxt.hooks.model_copy(
            update={
                "steps_applied": nxt.hooks.steps_applied + 1,
                "utterances": nxt.hooks.utterances + 1,
            },
        )
        nxt.utterances = _trim_tail_utterances(
            nxt,
            UtteranceEntry(step=new_step, agent_id=action.agent_id, text=action.text),
        )
        ka, sm = _summarize_applied_action(action)
        nxt = _append_action_log(
            nxt,
            global_step=new_step,
            agent_id=action.agent_id,
            kind=ka,
            summary=sm,
        )
        return ApplyResult(True, nxt, ())

    if isinstance(action, SupportOptionAction):
        if action.agent_id not in env.agent_state_by_id:
            return ApplyResult(False, env, ("unknown_agent",))
        oid = action.option_id.strip()
        if oid not in env.options_by_id:
            return ApplyResult(False, env, ("unknown_option",))
        nxt = env.model_copy(deep=True)
        new_step = nxt.step_index + 1
        nxt.step_index = new_step
        cur = float(nxt.option_support_scores.get(oid, 0.5))
        nxt.option_support_scores = {
            **nxt.option_support_scores,
            oid: _clamp01(cur + float(action.delta)),
        }
        st = nxt.agent_state_by_id[action.agent_id].model_copy(
            update={"last_step_index": new_step, "focus_option_id": oid},
        )
        nxt.agent_state_by_id = {**nxt.agent_state_by_id, action.agent_id: st}
        nxt.hooks = EnvHooks(
            steps_applied=nxt.hooks.steps_applied + 1,
            utterances=nxt.hooks.utterances,
            passes=nxt.hooks.passes,
        )
        ka, sm = _summarize_applied_action(action)
        nxt = _append_action_log(
            nxt,
            global_step=new_step,
            agent_id=action.agent_id,
            kind=ka,
            summary=sm,
        )
        return ApplyResult(True, nxt, ())

    if isinstance(action, AttackOptionAction):
        if action.agent_id not in env.agent_state_by_id:
            return ApplyResult(False, env, ("unknown_agent",))
        oid = action.option_id.strip()
        if oid not in env.options_by_id:
            return ApplyResult(False, env, ("unknown_option",))
        nxt = env.model_copy(deep=True)
        new_step = nxt.step_index + 1
        nxt.step_index = new_step
        cur = float(nxt.option_support_scores.get(oid, 0.5))
        nxt.option_support_scores = {
            **nxt.option_support_scores,
            oid: _clamp01(cur - float(action.delta)),
        }
        st = nxt.agent_state_by_id[action.agent_id].model_copy(
            update={"last_step_index": new_step},
        )
        nxt.agent_state_by_id = {**nxt.agent_state_by_id, action.agent_id: st}
        nxt.hooks = EnvHooks(
            steps_applied=nxt.hooks.steps_applied + 1,
            utterances=nxt.hooks.utterances,
            passes=nxt.hooks.passes,
        )
        ka, sm = _summarize_applied_action(action)
        nxt = _append_action_log(
            nxt,
            global_step=new_step,
            agent_id=action.agent_id,
            kind=ka,
            summary=sm,
        )
        return ApplyResult(True, nxt, ())

    if isinstance(action, ProposeClaimAction):
        if action.agent_id not in env.agent_state_by_id:
            return ApplyResult(False, env, ("unknown_agent",))
        text = action.text.strip()
        if len(text) > env.limits.max_claim_text:
            return ApplyResult(False, env, ("claim_text_too_long",))
        if len(env.claims) >= env.limits.max_claims:
            return ApplyResult(False, env, ("max_claims",))
        for oid in action.option_ids:
            if oid not in env.options_by_id:
                return ApplyResult(False, env, ("unknown_option_in_claim",))
        nxt = env.model_copy(deep=True)
        new_step = nxt.step_index + 1
        nxt.step_index = new_step
        seq = nxt.next_claim_seq + 1
        nxt.next_claim_seq = seq
        cid = f"c{new_step}_{seq}"
        claim = ClaimRecord(
            id=cid,
            text=text,
            agent_id=action.agent_id,
            source_step=new_step,
            linked_option_ids=tuple(action.option_ids),
        )
        nxt.claims = {**nxt.claims, cid: claim}
        st = nxt.agent_state_by_id[action.agent_id].model_copy(
            update={"last_step_index": new_step, "focus_claim_id": cid},
        )
        nxt.agent_state_by_id = {**nxt.agent_state_by_id, action.agent_id: st}
        nxt.hooks = EnvHooks(
            steps_applied=nxt.hooks.steps_applied + 1,
            utterances=nxt.hooks.utterances,
            passes=nxt.hooks.passes,
        )
        ka, sm = _summarize_applied_action(action, created_claim_id=cid)
        nxt = _append_action_log(
            nxt,
            global_step=new_step,
            agent_id=action.agent_id,
            kind=ka,
            summary=sm,
        )
        return ApplyResult(True, nxt, ())

    if isinstance(action, LinkAction):
        if action.agent_id not in env.agent_state_by_id:
            return ApplyResult(False, env, ("unknown_agent",))
        if action.src_claim_id == action.dst_claim_id:
            return ApplyResult(False, env, ("link_self_loop",))
        if action.src_claim_id not in env.claims or action.dst_claim_id not in env.claims:
            return ApplyResult(False, env, ("unknown_claim",))
        if len(env.edges) >= env.limits.max_edges:
            return ApplyResult(False, env, ("max_edges",))
        nxt = env.model_copy(deep=True)
        new_step = nxt.step_index + 1
        nxt.step_index = new_step
        eseq = nxt.next_edge_seq + 1
        nxt.next_edge_seq = eseq
        eid = f"e{new_step}_{eseq}"
        edge = EdgeRecord(
            id=eid,
            src_claim_id=action.src_claim_id,
            dst_claim_id=action.dst_claim_id,
            rel=action.rel,
        )
        nxt.edges = [*nxt.edges, edge]
        st = nxt.agent_state_by_id[action.agent_id].model_copy(update={"last_step_index": new_step})
        nxt.agent_state_by_id = {**nxt.agent_state_by_id, action.agent_id: st}
        nxt.hooks = EnvHooks(
            steps_applied=nxt.hooks.steps_applied + 1,
            utterances=nxt.hooks.utterances,
            passes=nxt.hooks.passes,
        )
        ka, sm = _summarize_applied_action(action)
        nxt = _append_action_log(
            nxt,
            global_step=new_step,
            agent_id=action.agent_id,
            kind=ka,
            summary=sm,
        )
        return ApplyResult(True, nxt, ())

    return ApplyResult(False, env, ("unknown_action",))


def snapshot_for_api(
    env: DebateEnvironment,
    *,
    max_claim_text_in_snapshot: int = 200,
    max_edges_in_snapshot: int = 64,
) -> dict[str, Any]:
    claims_out: list[dict[str, Any]] = []
    for c in env.claims.values():
        t = c.text if len(c.text) <= max_claim_text_in_snapshot else c.text[: max_claim_text_in_snapshot - 1] + "…"
        claims_out.append(
            {
                "id": c.id,
                "text": t,
                "agent_id": c.agent_id,
                "source_step": c.source_step,
                "linked_option_ids": list(c.linked_option_ids),
            },
        )
    claims_out.sort(key=lambda x: x["source_step"])

    edges_out = [
        {
            "id": e.id,
            "src_claim_id": e.src_claim_id,
            "dst_claim_id": e.dst_claim_id,
            "rel": e.rel,
        }
        for e in env.edges[:max_edges_in_snapshot]
    ]

    return {
        "schema_version": env.schema_version,
        "session_id": env.session_id,
        "mode": env.mode,
        "step_index": env.step_index,
        "rng_seed": env.rng_seed,
        "created_at_iso": env.created_at_iso,
        "context_ref": env.context_ref.model_dump(),
        "limits": env.limits.model_dump(),
        "options": {k: v.model_dump() for k, v in sorted(env.options_by_id.items())},
        "option_support_scores": dict(sorted(env.option_support_scores.items())),
        "claims": claims_out,
        "edges": edges_out,
        "agents": {
            k: v.model_dump() for k, v in sorted(env.agent_state_by_id.items())
        },
        "hooks": env.hooks.model_dump(),
        "utterances": [u.model_dump() for u in env.utterances],
        "action_log": [e.model_dump() for e in env.action_log],
    }


def merge_options(env: DebateEnvironment, options: list[DebateOption]) -> DebateEnvironment:
    """Register vote options and initialize scores to 0.5 when missing."""
    nxt = env.model_copy(deep=True)
    ob = dict(nxt.options_by_id)
    sc = dict(nxt.option_support_scores)
    for o in options:
        ob[o.id] = o
        sc.setdefault(o.id, 0.5)
    nxt.options_by_id = ob
    nxt.option_support_scores = sc
    return nxt
