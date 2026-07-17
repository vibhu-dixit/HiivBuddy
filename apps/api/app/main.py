import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

# ── Sentry — initialise before anything else so all errors are captured ───────
def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import threading
        import httpx
        def _send():
            try:
                url = os.environ.get("HOTFIX_ENGINE_WEBHOOK_URL", "http://localhost:8001/webhook/sentry")
                httpx.post(url, json={"action": "triggered", "data": {"event": event}}, timeout=5.0)
            except Exception:
                pass
        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass
    return event

sentry_sdk.init(
    dsn="https://8a027b54097a0fdb666e3c4783e26288@o4511729199480832.ingest.us.sentry.io/4511729368039424",
    send_default_pii=True,
    integrations=[
        StarletteIntegration(),
        FastApiIntegration(),
    ],
    traces_sample_rate=1.0,
    before_send=before_send,
)
# ─────────────────────────────────────────────────────────────────────────────

import asyncpg
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.captcha import captcha_bypass_enabled, captcha_secret_configured
from app.auth.deps import get_current_user
from app.auth.rate_limit import enforce_guest_debate_rate_limit
from app.auth.router import guest_auth_enabled, is_guest_user, router as auth_router
from app.db import models  # noqa: F401 — register models before routes
from app.db.models import DebateRun, User
from app.db.prune import prune_all_users_excess_runs, prune_excess_runs_for_user
from app.db.session import async_session_maker, get_session, init_db
from app.debate.orchestrator import AGENTS, run_debate_stream
from app.debate.swarm_runner import run_swarm_session_stream
from app.context_ingest import extract_text_from_upload
from app.debate.schemas import DebateRequest
from app.llm.client import get_async_client, get_settings

logger = logging.getLogger(__name__)


def _cors_allow_origins() -> list[str]:
    """Local dev defaults plus comma-separated CORS_ORIGINS (e.g. https://app.vercel.app)."""
    defaults = ["http://localhost:3000", "http://127.0.0.1:3000"]
    extra_raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not extra_raw:
        return defaults
    extra = [o.strip() for o in extra_raw.split(",") if o.strip()]
    seen: set[str] = set()
    merged: list[str] = []
    for o in defaults + extra:
        if o not in seen:
            seen.add(o)
            merged.append(o)
    return merged


def _exception_root(exc: BaseException) -> BaseException:
    e: BaseException = exc
    while e.__cause__ is not None:
        e = e.__cause__
    return e


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await init_db()
    except Exception as e:
        root = _exception_root(e)
        if isinstance(root, asyncpg.InvalidPasswordError):
            logger.error(
                "PostgreSQL rejected DATABASE_URL credentials. Update apps/api/.env so user/password "
                "match your server. If you use Docker's db service: "
                "`docker compose up db` then DATABASE_URL=postgresql://hiivbuddy:hiivbuddy@localhost:5435/hiivbuddy",
            )
        raise
    async with async_session_maker() as session:
        await prune_all_users_excess_runs(session)
    yield


AGENT_NAMES = {a["id"]: a["name"] for a in AGENTS}

app = FastAPI(title="Hiiv API", lifespan=lifespan)

app.include_router(auth_router)

# Regex covers common local dev Origins (any port). Browsers still send Origin per-tab; if it is not
# listed here or in CORS_ORIGINS / defaults, the client may show NetworkError even though the API ran.
_LOCAL_DEV_ORIGIN_REGEX = (
    r"http://("
    r"localhost|127\.0\.0\.1|\[::1\]"
    r"|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:[0-9]{1,5})?"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_origin_regex=_LOCAL_DEV_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    guest_enabled = guest_auth_enabled()
    captcha_ready = captcha_bypass_enabled() or captcha_secret_configured()

    # BUG: refactored to build status string dynamically from config keys —
    # os.environ["APP_STATUS_PREFIX"] is not set in production, raises KeyError
    status_prefix = os.environ["APP_STATUS_PREFIX"]
    status = f"{status_prefix}-ok"

    return {
        "status": status,
        "guest_demo": {
            "enabled": guest_enabled,
            "captcha_configured": captcha_ready,
            "ready": guest_enabled and captcha_ready,
        },
    }


@app.post("/context/extract")
async def context_extract(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    """Extract text from .txt / .md / .pdf for Decision Room context (max 500 chars extracted)."""
    return await extract_text_from_upload(file)


def _format_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def debate_event_stream(
    body: DebateRequest,
    session: AsyncSession,
    current_user: User,
) -> AsyncIterator[str]:
    user_id = current_user.id
    guest_session = is_guest_user(current_user)
    client = get_async_client()
    transcript_parts: list[str] = []
    final_report: dict[str, Any] | None = None

    env_limits = body.env_limits.to_env_limits() if body.env_limits else None
    settings = get_settings()
    session_mode = body.session_mode
    if settings.hiivbuddy_force_session_mode in ("classic", "swarm"):
        session_mode = settings.hiivbuddy_force_session_mode  # type: ignore[assignment]

    logger.info(
        "debate_sse_start user_id=%s guest=%s session_mode=%s duration_sec=%s model=%s",
        user_id,
        guest_session,
        session_mode,
        body.session_duration_sec,
        (body.model or "")[:120],
    )

    stream = (
        run_swarm_session_stream(
            client,
            context=body.context,
            model=body.model,
            llm=settings,
            session_duration_sec=body.session_duration_sec,
            consensus_threshold=body.consensus_threshold,
            synth_env_snapshot=body.synth_env_snapshot,
            environment_rng_seed=body.environment_rng_seed,
            env_limits=env_limits,
        )
        if session_mode == "swarm"
        else run_debate_stream(
            client,
            context=body.context,
            model=body.model,
            llm=settings,
            session_duration_sec=body.session_duration_sec,
            consensus_threshold=body.consensus_threshold,
            enable_interjections=body.enable_interjections,
            track_environment=body.track_environment,
            synth_env_snapshot=body.synth_env_snapshot,
            environment_rng_seed=body.environment_rng_seed,
            env_limits=env_limits,
        )
    )

    try:
        async for event in stream:
            et = event.get("type")
            if et == "session_start":
                transcript_parts.append(
                    "--- Session ---\n"
                    + json.dumps(
                        {
                            "session_duration_sec": event.get("session_duration_sec"),
                            "debate_budget_sec": event.get("debate_budget_sec"),
                            "synth_reserve_sec": event.get("synth_reserve_sec"),
                        },
                        ensure_ascii=False,
                    ),
                )
            elif et == "debate_phase_end":
                logger.info(
                    "sse debate_phase_end turns=%s",
                    event.get("turns_completed", 0),
                )
                transcript_parts.append(
                    f"--- Debate phase end (turns: {event.get('turns_completed', 0)}) ---",
                )
            elif et == "decision_options":
                logger.info("sse decision_options count=%s", len(event.get("options") or []))
            elif et == "vote_phase_start":
                logger.info("sse vote_phase_start")
                transcript_parts.append("--- Vote phase ---")
            elif et == "synthesizer_start":
                logger.info("sse synthesizer_start")
            elif et == "final_report":
                logger.info("sse final_report")
            elif et == "agent_decision_trace":
                transcript_parts.append(
                    "--- Agent stance trace ---\n"
                    + json.dumps(event.get("stances") or [], ensure_ascii=False),
                )
            elif et == "agent_end" and event.get("full_text"):
                aid = event.get("agent") or ""
                name = AGENT_NAMES.get(str(aid), str(aid))
                turn = event.get("turn")
                prefix = f"[Turn {turn}][{name}]" if turn is not None else f"[{name}]"
                transcript_parts.append(f"{prefix}: {event['full_text']}")
            elif et == "interjection" and event.get("text"):
                oa = event.get("agent") or ""
                on = AGENT_NAMES.get(str(oa), str(oa))
                ta = event.get("target_agent") or ""
                tn = AGENT_NAMES.get(str(ta), str(ta))
                turn = event.get("turn")
                prefix = (
                    f"[Turn {turn}][{on} interjects → {tn}]"
                    if turn is not None
                    else f"[{on} interjects → {tn}]"
                )
                transcript_parts.append(f"{prefix}: {event['text']}")
            elif et == "vote_tally":
                transcript_parts.append(
                    "--- Vote tally ---\n"
                    + json.dumps(
                        {
                            "tallies": event.get("tallies"),
                            "votes": event.get("votes"),
                            "consensus_reached": event.get("consensus_reached"),
                            "winning_option_id": event.get("winning_option_id"),
                            "winning_title": event.get("winning_title"),
                            "threshold": event.get("threshold"),
                        },
                        ensure_ascii=False,
                    ),
                )
            elif et == "env_snapshot":
                transcript_parts.append(
                    f"--- Environment snapshot ({event.get('phase')}) ---\n"
                    + json.dumps(event.get("snapshot") or {}, ensure_ascii=False),
                )
            if et == "final_report":
                fr = event.get("report")
                es = event.get("env_snapshot")
                if isinstance(fr, dict) and es is not None:
                    final_report = {**fr, "env_snapshot": es}
                else:
                    final_report = fr
            yield _format_sse(event)
    except Exception:
        logger.exception("debate_sse_failed user_id=%s", user_id)
        yield _format_sse(
            {
                "type": "stream_error",
                "message": (
                    "The session ended unexpectedly during voting or synthesis. "
                    "Your debate turns above are still valid."
                ),
            },
        )
        if not transcript_parts:
            yield _format_sse({"type": "done"})
            return

    if not transcript_parts:
        yield _format_sse({"type": "done"})
        return

    if guest_session:
        yield _format_sse({"type": "done"})
        return

    row = DebateRun(
        user_id=user_id,
        context=body.context,
        model=body.model,
        transcript="\n\n".join(transcript_parts),
        final_report_json=json.dumps(final_report or {}),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    await prune_excess_runs_for_user(session, user_id)

    yield _format_sse({"type": "saved", "run_id": row.id})
    yield _format_sse({"type": "done", "run_id": row.id})


@app.post("/debate/stream")
async def debate_stream(
    request: Request,
    body: DebateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if is_guest_user(current_user):
        enforce_guest_debate_rate_limit(request)

    return StreamingResponse(
        debate_event_stream(body, session, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/debate/runs/latest")
async def latest_run(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(DebateRun)
        .where(DebateRun.user_id == current_user.id)
        .order_by(DebateRun.id.desc())
        .limit(1),
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"run": None}
    return {
        "run": {
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "context": row.context,
            "model": row.model,
            "transcript": row.transcript,
            "final_report": json.loads(row.final_report_json or "{}"),
        }
    }


@app.delete("/debate/runs/{run_id}")
async def delete_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    row = await session.get(DebateRun, run_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    await session.delete(row)
    await session.commit()
    return {"ok": True, "deleted": run_id}
