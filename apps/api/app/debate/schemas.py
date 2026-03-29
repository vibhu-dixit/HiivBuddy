from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


SYNTH_RESERVE_SEC = 30


def _default_chat_model() -> str:
    from app.llm.client import get_settings

    return get_settings().llm_default_model


class DebateRequest(BaseModel):
    context: str = Field(..., min_length=10, description="User decision context")
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
