from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.context_ingest import MAX_CONTEXT_CHARS


# Subtracted from debate time so the session clock leaves room for closing + synthesis.
SYNTH_RESERVE_SEC = 30
# Within the reserve: max wall time for vote extraction before Chief Synthesizer must start.
CLOSING_VOTE_MAX_SEC = 18
# Minimum seconds reserved for the Chief Synthesizer call within SYNTH_RESERVE_SEC.
SYNTH_MIN_SEC = 10
# Do not start a new debate LLM turn when less than this remains on the debate budget.
MIN_DEBATE_TURN_SEC = 6
# Max wall time to generate decision options when the brief has no numbered list.
OPTION_SEED_MAX_SEC = 12
# Hard limit for the Chief Synthesizer HTTP call (`asyncio.wait_for`); capped by session deadline at runtime.
SYNTH_API_TIMEOUT_SEC = 90


def _default_chat_model() -> str:
    from app.llm.client import get_settings

    return get_settings().llm_default_model


class EnvLimitsPayload(BaseModel):
    """Caps for in-memory DebateEnvironment; mirrors app.debate.environment.EnvLimits."""

    max_claims: int = Field(default=64, ge=1, le=10_000)
    max_edges: int = Field(default=128, ge=1, le=50_000)
    max_steps_per_session: int = Field(default=512, ge=1, le=1_000_000)
    max_utter_chars: int = Field(default=4000, ge=1, le=100_000)
    max_claim_text: int = Field(default=2000, ge=1, le=50_000)
    max_utterances_stored: int = Field(default=50, ge=1, le=500)
    max_action_log_entries: int = Field(default=40, ge=1, le=500)

    def to_env_limits(self):
        from app.debate.environment import EnvLimits

        return EnvLimits.model_validate(self.model_dump())


class DebateRequest(BaseModel):
    context: str = Field(
        ...,
        min_length=10,
        max_length=MAX_CONTEXT_CHARS,
        description="User decision context",
    )
    model: str = Field(
        default_factory=_default_chat_model,
        description="Chat model id (defaults to LLM_DEFAULT_MODEL from API .env)",
    )
    session_duration_sec: int = Field(
        default=120,
        ge=60,
        le=600,
        description="Total session length in seconds; last 30s reserved for Chief Synthesizer",
    )
    consensus_threshold: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Votes needed on one option to count as consensus (of 5 agents)",
    )
    enable_interjections: bool = Field(
        default=True,
        description="After each main speaker, other advisors may interject in parallel (PASS if no objection)",
    )
    session_mode: Literal["classic", "swarm"] = Field(
        default="swarm",
        validation_alias=AliasChoices("session_mode", "debate_mode"),
        serialization_alias="session_mode",
        description="classic: streaming lap debate; swarm: structured JSON turns + shared env",
    )
    track_environment: bool = Field(
        default=False,
        description="When true, maintain DebateEnvironment during classic debate (utterances + votes)",
    )
    synth_env_snapshot: bool = Field(
        default=False,
        description="When true, append compact environment JSON to the Chief Synthesizer user message",
    )
    environment_rng_seed: int | None = Field(
        default=None,
        ge=0,
        le=2_147_483_647,
        description="Deterministic seed for environment + swarm scheduling; derived from context if null",
    )
    env_limits: EnvLimitsPayload | None = Field(
        default=None,
        description="Override default DebateEnvironment limits",
    )


class RankedOption(BaseModel):
    title: str
    score: float = Field(ge=0, le=1)
    rationale: str


class FinalReport(BaseModel):
    summary: str
    ranked_options: list[RankedOption]
    risks: list[str]
    next_steps: list[str]


class VoteOptionItem(BaseModel):
    id: str
    title: str


class VoteOptionsResponse(BaseModel):
    options: list[VoteOptionItem] = Field(min_length=2, max_length=4)


class AgentVoteResponse(BaseModel):
    """LLMs often omit option_id or use alternate keys; orchestrator falls back if still missing."""

    model_config = ConfigDict(extra="ignore")

    option_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "option_id",
            "vote",
            "choice",
            "selected_option_id",
            "selected_option",
            "option",
        ),
    )
    rationale: str = ""

    @field_validator("option_id", mode="before")
    @classmethod
    def _option_id_coerce(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class ClosingVoteItem(BaseModel):
    agent_id: str
    option_id: str
    rationale: str = ""


class AgentStanceItem(BaseModel):
    """Backend-only per-advisor stance snapshot for the synthesizer (may be emitted once for UI/debug)."""

    agent_id: str
    lean: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    note: str = ""


class ClosingPhaseResponse(BaseModel):
    """Single batched JSON for options, votes, and stance signals before synthesis."""

    options: list[VoteOptionItem] = Field(min_length=2, max_length=4)
    votes: list[ClosingVoteItem] = Field(min_length=1, max_length=10)
    agent_stances: list[AgentStanceItem] = Field(min_length=1, max_length=10)
