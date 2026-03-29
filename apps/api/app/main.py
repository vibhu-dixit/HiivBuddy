import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models  # noqa: F401 — register models before routes
from app.db.models import DebateRun
from app.db.session import get_session, init_db
from app.debate.orchestrator import AGENTS, run_debate_stream
from app.debate.schemas import DebateRequest
from app.llm.client import get_async_client, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


AGENT_NAMES = {a["id"]: a["name"] for a in AGENTS}

app = FastAPI(title="HiivBuddy API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _format_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def debate_event_stream(
    body: DebateRequest,
    session: AsyncSession,
) -> AsyncIterator[str]:
    client = get_async_client()
    transcript_parts: list[str] = []
    final_report: dict[str, Any] | None = None

    async for event in run_debate_stream(
        client,
        context=body.context,
        model=body.model,
        llm=get_settings(),
        session_duration_sec=body.session_duration_sec,
        consensus_threshold=body.consensus_threshold,
        enable_interjections=body.enable_interjections,
    ):
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
            transcript_parts.append(
                f"--- Debate phase end (turns: {event.get('turns_completed', 0)}) ---",
            )
        elif et == "agent_decision_trace":
            transcript_parts.append(
                "--- Agent stance trace ---\n"
                + json.dumps(event.get("stances") or [], ensure_ascii=False),
            )
        elif et == "vote_phase_start":
            transcript_parts.append("--- Vote phase ---")
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
        if et == "final_report":
            final_report = event.get("report")
        yield _format_sse(event)

    row = DebateRun(
        context=body.context,
        model=body.model,
        transcript="\n\n".join(transcript_parts),
        final_report_json=json.dumps(final_report or {}),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    yield _format_sse({"type": "saved", "run_id": row.id})
    yield _format_sse({"type": "done", "run_id": row.id})


@app.post("/debate/stream")
async def debate_stream(
    body: DebateRequest,
    session: AsyncSession = Depends(get_session),
):
    return StreamingResponse(
        debate_event_stream(body, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/debate/runs/latest")
async def latest_run(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(DebateRun).order_by(DebateRun.id.desc()).limit(1))
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
