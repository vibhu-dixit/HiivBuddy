"""Structured JSON one-shot response for swarm agents (maps to AgentAction)."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.debate.environment import (
    AgentAction,
    AttackOptionAction,
    LinkAction,
    PassAction,
    ProposeClaimAction,
    SupportOptionAction,
    UtterAction,
)

SWARM_JSON_RULES = (
    " You must output ONLY a single JSON object (no markdown). "
    "Keys: required \"action\" as one of: pass, utter, support_option, attack_option, propose_claim, link. "
    "Include only the payload fields needed for that action. "
    "Optional: \"speech\" (short public line, max ~400 chars for transcript when action is not utter), "
    "\"rationale_internal\" (max 300 chars, not shown to users). "
    "For utter: required \"text\" (what you say). "
    "For support_option/attack_option: \"option_id\", \"delta\" (number). "
    "For propose_claim: \"text\"; optional \"option_ids\" array. "
    "For link: \"src_claim_id\", \"dst_claim_id\", \"rel\" in supports|attacks|relates. "
    "Use only option and claim ids from the observation. If unsure, use action pass."
)


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


class SwarmTurnResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal[
        "pass",
        "utter",
        "support_option",
        "attack_option",
        "propose_claim",
        "link",
    ]
    text: str | None = None
    turn_ref: int | None = None
    option_id: str | None = None
    delta: float | None = None
    option_ids: list[str] | None = None
    src_claim_id: str | None = None
    dst_claim_id: str | None = None
    rel: Literal["supports", "attacks", "relates"] | None = None
    speech: str | None = None
    rationale_internal: str | None = None

    @field_validator("speech", mode="after")
    @classmethod
    def _clip_speech(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s[:400] if len(s) > 400 else s

    @field_validator("rationale_internal", mode="after")
    @classmethod
    def _clip_rat(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s[:300] if len(s) > 300 else s

    @model_validator(mode="after")
    def _payload_matches_action(self) -> SwarmTurnResponse:
        a = self.action
        if a == "pass":
            return self
        if a == "utter":
            if not (self.text and self.text.strip()):
                raise ValueError("utter requires non-empty text")
            return self
        if a in ("support_option", "attack_option"):
            if not (self.option_id and str(self.option_id).strip()):
                raise ValueError(f"{a} requires option_id")
            if self.delta is None:
                raise ValueError(f"{a} requires delta")
            return self
        if a == "propose_claim":
            if not (self.text and self.text.strip()):
                raise ValueError("propose_claim requires text")
            return self
        if a == "link":
            if not (self.src_claim_id and self.dst_claim_id and self.rel):
                raise ValueError("link requires src_claim_id, dst_claim_id, rel")
            return self
        return self


def parse_swarm_turn_response(raw: str) -> SwarmTurnResponse:
    raw = (raw or "").strip()
    candidates: list[str] = []
    if raw:
        candidates.append(raw)
    ext = _extract_json_object(raw)
    if ext and ext not in candidates:
        candidates.append(ext)
    last: Exception | None = None
    for cand in candidates:
        try:
            return SwarmTurnResponse.model_validate_json(cand)
        except Exception as e:
            last = e
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                # tolerate action_type alias
                if "action_type" in data and "action" not in data:
                    data = {**data, "action": data.pop("action_type")}
                return SwarmTurnResponse.model_validate(data)
        except Exception as e:
            last = e
    raise ValueError(f"Invalid swarm JSON: {last}")


def swarm_response_to_agent_action(resp: SwarmTurnResponse, agent_id: str) -> AgentAction:
    a = resp.action
    if a == "pass":
        return PassAction(agent_id=agent_id)
    if a == "utter":
        return UtterAction(
            agent_id=agent_id,
            text=(resp.text or "").strip(),
            turn_ref=resp.turn_ref,
        )
    if a == "support_option":
        return SupportOptionAction(
            agent_id=agent_id,
            option_id=(resp.option_id or "").strip(),
            delta=float(resp.delta or 0),
        )
    if a == "attack_option":
        return AttackOptionAction(
            agent_id=agent_id,
            option_id=(resp.option_id or "").strip(),
            delta=float(resp.delta or 0),
        )
    if a == "propose_claim":
        oids = tuple(resp.option_ids or ())
        return ProposeClaimAction(
            agent_id=agent_id,
            text=(resp.text or "").strip(),
            option_ids=oids,
        )
    if a == "link":
        return LinkAction(
            agent_id=agent_id,
            src_claim_id=(resp.src_claim_id or "").strip(),
            dst_claim_id=(resp.dst_claim_id or "").strip(),
            rel=resp.rel or "relates",
        )
    return PassAction(agent_id=agent_id)


def transcript_line_for_turn(resp: SwarmTurnResponse, applied: AgentAction) -> str:
    if isinstance(applied, UtterAction):
        return applied.text.strip()
    if resp.speech and resp.speech.strip():
        return resp.speech.strip()
    if isinstance(applied, PassAction):
        return "(pass)"
    if isinstance(applied, ProposeClaimAction):
        return f"(propose_claim) {applied.text.strip()[:200]}"
    if isinstance(applied, (SupportOptionAction, AttackOptionAction)):
        return f"({applied.action}) option {applied.option_id}"
    if isinstance(applied, LinkAction):
        return f"(link) {applied.src_claim_id} → {applied.dst_claim_id}"
    return f"({resp.action})"
