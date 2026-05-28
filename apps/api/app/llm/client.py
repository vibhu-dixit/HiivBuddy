"""Single place we construct the OpenAI-compatible async client (no LiteLLM)."""

from functools import lru_cache
from typing import Any
from urllib.parse import urlparse, urlunparse

from openai import AsyncOpenAI
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Matches NVIDIA integrate OpenAI-compatible API (your sample).
NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _normalize_openai_base_url(url: str) -> str:
    """OpenAI SDK posts to {base_url}/chat/completions. Host-only URLs must include /v1 or the server returns 404."""
    u = url.strip().rstrip("/")
    p = urlparse(u)
    path = p.path or "/"
    if path == "/":
        return urlunparse((p.scheme, p.netloc, "/v1", "", "", ""))
    return u


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    nvidia_api_key: str | None = None
    openai_base_url: str | None = None

    # Same as your chat.completions.create(...) sample
    llm_temperature: float = 1.0
    llm_top_p: float = 1.0
    llm_max_tokens: int = 16384
    # Default when POST body omits `model` (env: LLM_DEFAULT_MODEL)
    llm_default_model: str = Field(
        default="stepfun-ai/step-3.5-flash",
        description="Default chat model id for debate when not specified in the request",
    )
    # Optional tier routing: when set, overrides the request `model` for high-volume debate turns
    # (classic primary + interjections; swarm JSON turns). Falls back to request model when unset.
    llm_debate_model: str | None = Field(default=None, alias="LLM_DEBATE_MODEL")
    # Optional tier routing: when set, overrides the request `model` for closing JSON, votes, Chief Synthesizer.
    llm_synth_model: str | None = Field(default=None, alias="LLM_SYNTH_MODEL")
    # Default off for normal completions; set NVIDIA_ENABLE_THINKING=true for models that use reasoning streams.
    nvidia_enable_thinking: bool | None = Field(default=None)
    # None = auto: Gemma and some OpenAI-compat routes reject role=system; merge into user (env: LLM_MERGE_SYSTEM_INTO_USER)
    llm_merge_system_into_user: bool | None = Field(default=None)
    # Used with estimated prompt size to cap max_tokens (OpenAI-compat: completion + prompt ≤ context).
    # Default 8192 matches many small-context endpoints; set LLM_CONTEXT_TOKENS=131072 (etc.) for long-context models.
    llm_context_tokens: int = Field(default=8192, ge=1024, le=2_000_000)
    # When "classic" or "swarm", overrides DebateRequest.session_mode (ops safety). "off" = use request.
    hiivbuddy_force_session_mode: str | None = Field(default=None, alias="HIIVBUDDY_FORCE_SESSION_MODE")

    @model_validator(mode="after")
    def _nvidia_defaults_and_key(self):
        nv = (self.nvidia_api_key or "").strip()
        oa = (self.openai_api_key or "").strip()
        if nv and self.openai_base_url is None:
            self.openai_base_url = NVIDIA_DEFAULT_BASE_URL
        if not nv and not oa:
            raise ValueError("Set OPENAI_API_KEY or NVIDIA_API_KEY in .env")
        if self.nvidia_enable_thinking is None:
            self.nvidia_enable_thinking = False
        fsm = (self.hiivbuddy_force_session_mode or "").strip().lower()
        if fsm not in ("", "off", "classic", "swarm"):
            self.hiivbuddy_force_session_mode = None
        elif fsm in ("", "off"):
            self.hiivbuddy_force_session_mode = None
        else:
            self.hiivbuddy_force_session_mode = fsm
        return self

    def resolved_api_key(self) -> str:
        key = (self.nvidia_api_key or "").strip() or (self.openai_api_key or "").strip()
        if not key:
            raise ValueError("Set OPENAI_API_KEY or NVIDIA_API_KEY in .env")
        return key

    def resolved_debate_model(self, request_model: str) -> str:
        """Model id for debate turns (streaming + interjections + swarm steps)."""
        d = (self.llm_debate_model or "").strip()
        return d if d else request_model

    def resolved_synth_model(self, request_model: str) -> str:
        """Model id for post-debate phases (votes, closing JSON, final report)."""
        d = (self.llm_synth_model or "").strip()
        return d if d else request_model

    def completion_extra_body(self) -> dict[str, Any] | None:
        if not self.nvidia_enable_thinking:
            return None
        # NVIDIA integrate: chat_template_kwargs for models that emit reasoning_content
        return {
            "chat_template_kwargs": {
                "enable_thinking": True,
                "clear_thinking": False,
            }
        }

    def common_completion_kwargs(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "temperature": self.llm_temperature,
            "top_p": self.llm_top_p,
            "max_tokens": self.llm_max_tokens,
        }
        extra = self.completion_extra_body()
        if extra:
            out["extra_body"] = extra
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_async_client() -> AsyncOpenAI:
    s = get_settings()
    kwargs: dict[str, Any] = {"api_key": s.resolved_api_key()}
    if s.openai_base_url:
        kwargs["base_url"] = _normalize_openai_base_url(s.openai_base_url)
    return AsyncOpenAI(**kwargs)
