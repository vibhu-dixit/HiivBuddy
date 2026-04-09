"""In-memory debate environment models (swarm-ready; no I/O)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field

DEFAULT_ADVISOR_IDS: tuple[str, ...] = (
    "optimist",
    "devils_advocate",
    "data_analyst",
    "risk_guru",
    "ethical_guardian",
)


class EnvLimits(BaseModel):
    model_config = {"frozen": True}

    max_claims: int = Field(default=64, ge=1, le=10_000)
    max_edges: int = Field(default=128, ge=1, le=50_000)
    max_steps_per_session: int = Field(default=512, ge=1, le=1_000_000)
    max_utter_chars: int = Field(default=4000, ge=1, le=100_000)
    max_claim_text: int = Field(default=2000, ge=1, le=50_000)
    max_utterances_stored: int = Field(default=50, ge=1, le=500)
    max_action_log_entries: int = Field(default=40, ge=1, le=500)


class ContextRef(BaseModel):
    model_config = {"frozen": True}

    kind: Literal["inline"] = "inline"
    sha256: str
    char_len: int = Field(ge=0)


class DebateOption(BaseModel):
    model_config = {"frozen": True}

    id: str
    title: str


class ClaimRecord(BaseModel):
    model_config = {"frozen": True}

    id: str
    text: str
    agent_id: str | None = None
    source_step: int = Field(ge=1)
    linked_option_ids: tuple[str, ...] = Field(default_factory=tuple)


class EdgeRecord(BaseModel):
    model_config = {"frozen": True}

    id: str
    src_claim_id: str
    dst_claim_id: str
    rel: Literal["supports", "attacks", "relates"]


class AgentState(BaseModel):
    model_config = {"frozen": True}

    last_step_index: int = 0
    focus_option_id: str | None = None
    focus_claim_id: str | None = None
    notes: str = ""


class EnvHooks(BaseModel):
    model_config = {"frozen": True}

    steps_applied: int = 0
    utterances: int = 0
    passes: int = 0


class UtteranceEntry(BaseModel):
    model_config = {"frozen": True}

    step: int
    agent_id: str
    text: str


class ActionLogEntry(BaseModel):
    model_config = {"frozen": True}

    global_step: int = Field(ge=1)
    agent_id: str
    action: str
    payload_summary: str = ""
    errors: tuple[str, ...] = Field(default_factory=tuple)


class PassAction(BaseModel):
    model_config = {"frozen": True}

    action: Literal["pass"] = "pass"
    agent_id: str
    client_action_id: str | None = None


class UtterAction(BaseModel):
    model_config = {"frozen": True}

    action: Literal["utter"] = "utter"
    agent_id: str
    text: str
    turn_ref: int | None = None
    client_action_id: str | None = None


class SupportOptionAction(BaseModel):
    model_config = {"frozen": True}

    action: Literal["support_option"] = "support_option"
    agent_id: str
    option_id: str
    delta: float
    client_action_id: str | None = None


class AttackOptionAction(BaseModel):
    model_config = {"frozen": True}

    action: Literal["attack_option"] = "attack_option"
    agent_id: str
    option_id: str
    delta: float
    client_action_id: str | None = None


class ProposeClaimAction(BaseModel):
    model_config = {"frozen": True}

    action: Literal["propose_claim"] = "propose_claim"
    agent_id: str
    text: str
    option_ids: tuple[str, ...] = Field(default_factory=tuple)
    client_action_id: str | None = None


class LinkAction(BaseModel):
    model_config = {"frozen": True}

    action: Literal["link"] = "link"
    agent_id: str
    src_claim_id: str
    dst_claim_id: str
    rel: Literal["supports", "attacks", "relates"]
    client_action_id: str | None = None


AgentAction = Annotated[
    Union[
        PassAction,
        UtterAction,
        SupportOptionAction,
        AttackOptionAction,
        ProposeClaimAction,
        LinkAction,
    ],
    Field(discriminator="action"),
]


class DebateEnvironment(BaseModel):
    """Mutable snapshot container; use environment_ops.apply_action for validated transitions."""

    model_config = {"frozen": False}

    schema_version: int = 1
    session_id: str
    mode: Literal["classic", "swarm"] = "classic"
    step_index: int = 0
    rng_seed: int
    created_at_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    limits: EnvLimits = Field(default_factory=EnvLimits)
    context_ref: ContextRef
    options_by_id: dict[str, DebateOption] = Field(default_factory=dict)
    option_support_scores: dict[str, float] = Field(default_factory=dict)
    claims: dict[str, ClaimRecord] = Field(default_factory=dict)
    edges: list[EdgeRecord] = Field(default_factory=list)
    agent_state_by_id: dict[str, AgentState] = Field(default_factory=dict)
    hooks: EnvHooks = Field(default_factory=EnvHooks)
    utterances: list[UtteranceEntry] = Field(default_factory=list)
    action_log: list[ActionLogEntry] = Field(default_factory=list)
    next_edge_seq: int = 0
    next_claim_seq: int = 0


def hash_context(context_text: str) -> ContextRef:
    b = context_text.encode("utf-8")
    return ContextRef(sha256=hashlib.sha256(b).hexdigest(), char_len=len(context_text))


def new_session_id() -> str:
    return str(uuid4())
