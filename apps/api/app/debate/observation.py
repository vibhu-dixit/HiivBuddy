"""Per-agent observations for structured swarm turns (pure, no I/O)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.debate.environment import DebateEnvironment


class ObservationConfig(BaseModel):
    model_config = {"frozen": True}

    claims_top_k: int = Field(default=12, ge=1, le=100)
    claim_text_max: int = Field(default=160, ge=20, le=2000)
    context_max_chars: int = Field(default=2000, ge=200, le=100_000)
    context_head: int = Field(default=1200, ge=100, le=50_000)
    context_tail: int = Field(default=600, ge=50, le=50_000)
    action_log_max_entries: int = Field(default=24, ge=1, le=200)


def trim_context_for_observation(
    context_text: str,
    *,
    max_chars: int = 2000,
    head: int = 1200,
    tail: int = 600,
) -> str:
    if len(context_text) <= max_chars:
        return context_text
    h = min(head, max_chars // 2 + 200)
    t = min(tail, max_chars - h - 40)
    if h + t + 40 > max_chars:
        t = max(0, max_chars - h - 40)
    mid = "\n\n[…trimmed…]\n\n"
    return context_text[:h] + mid + context_text[-t:]


def build_observation(
    env: DebateEnvironment,
    *,
    agent_id: str,
    agent_display_name: str,
    context_text: str,
    debate_seconds_remaining: int,
    config: ObservationConfig | None = None,
) -> dict[str, Any]:
    cfg = config or ObservationConfig()
    ctx = trim_context_for_observation(
        context_text,
        max_chars=cfg.context_max_chars,
        head=cfg.context_head,
        tail=cfg.context_tail,
    )

    options_list: list[dict[str, Any]] = []
    for oid, opt in sorted(env.options_by_id.items(), key=lambda x: x[0]):
        sc = float(env.option_support_scores.get(oid, 0.5))
        options_list.append({"id": opt.id, "title": opt.title, "support_score": sc})
    options_list.sort(key=lambda x: (-x["support_score"], x["id"]))

    claims_raw = list(env.claims.values())
    claims_raw.sort(key=lambda c: (-c.source_step, c.id))
    top = claims_raw[: cfg.claims_top_k]
    cm = cfg.claim_text_max
    claims_top_k: list[dict[str, Any]] = []
    for c in top:
        txt = c.text if len(c.text) <= cm else c.text[: cm - 1] + "…"
        claims_top_k.append(
            {
                "id": c.id,
                "text": txt,
                "agent_id": c.agent_id,
                "source_step": c.source_step,
                "linked_option_ids": list(c.linked_option_ids),
                "rank_basis": "recency",
                "relevance_score": None,
            },
        )

    log_tail = env.action_log[-cfg.action_log_max_entries :]
    action_log = [
        {
            "step": e.global_step,
            "agent_id": e.agent_id,
            "action": e.action,
            "summary": e.payload_summary,
        }
        for e in reversed(log_tail)
    ]

    st = env.agent_state_by_id.get(agent_id)
    your_state = st.model_dump() if st else {}

    return {
        "schema_version": 1,
        "session": {
            "session_id": env.session_id,
            "mode": env.mode,
            "step_index": env.step_index,
            "debate_seconds_remaining": max(0, int(debate_seconds_remaining)),
            "you_are": {"agent_id": agent_id, "name": agent_display_name},
        },
        "user_context": ctx,
        "options": options_list,
        "claims_top_k": claims_top_k,
        "action_log": action_log,
        "your_state": your_state,
        "relevance": {
            "enabled": False,
            "claim_ids": [],
            "note": "RAG ranking not enabled in v1",
        },
    }
