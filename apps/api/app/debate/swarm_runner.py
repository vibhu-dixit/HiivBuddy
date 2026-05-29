"""Structured JSON swarm session: observation -> LLM -> apply_action; then shared vote/synth."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

import random
from openai import AsyncOpenAI

from app.debate.environment import EnvLimits
from app.debate.environment_ops import apply_action, init_environment, snapshot_for_api
from app.debate.observation import ObservationConfig, build_observation
from app.debate.orchestrator import (
    AGENTS,
    _completion_kw_for_messages,
    _debate_environment_seed,
    _first_assistant_message,
    _synth_raw_from_assistant_message,
    ensure_session_options,
    run_post_debate_phases,
)
from app.debate.schemas import MIN_DEBATE_TURN_SEC, SYNTH_RESERVE_SEC
from app.debate.swarm_scheduler import init_speech_counts, pick_next_agent_swarm
from app.debate.swarm_schemas import (
    SWARM_JSON_RULES,
    SwarmTurnResponse,
    parse_swarm_turn_response,
    swarm_response_to_agent_action,
    transcript_line_for_turn,
    user_visible_turn_line,
)
from app.debate.environment import AgentAction, PassAction
from app.llm.client import Settings
from app.llm.messages import prepare_chat_messages

logger = logging.getLogger("app.debate.swarm")


async def run_swarm_session_stream(
    client: AsyncOpenAI,
    *,
    context: str,
    model: str,
    llm: Settings,
    session_duration_sec: int = 120,
    consensus_threshold: int = 3,
    synth_env_snapshot: bool = False,
    environment_rng_seed: int | None = None,
    env_limits: EnvLimits | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Swarm with non-streaming JSON turns. Interjections are not used (sequential structured steps).
    """
    total_sec = max(60, min(600, session_duration_sec))
    debate_budget_sec = max(0.0, float(total_sec - SYNTH_RESERVE_SEC))
    transcript = ""
    base_kw = llm.common_completion_kwargs()
    debate_model = llm.resolved_debate_model(model)
    effective_track = True

    yield {
        "type": "session_start",
        "session_duration_sec": total_sec,
        "debate_budget_sec": debate_budget_sec,
        "synth_reserve_sec": SYNTH_RESERVE_SEC,
    }

    limits = env_limits or EnvLimits()
    seed = _debate_environment_seed(context, environment_rng_seed)
    session_env = init_environment(
        context,
        rng_seed=seed,
        limits=limits,
        mode="swarm",
    )
    session_env, session_options = await ensure_session_options(
        client,
        context=context,
        model=model,
        llm=llm,
        env=session_env,
    )
    yield {
        "type": "decision_options",
        "options": [{"id": o.id, "title": o.title} for o in session_options],
    }

    t0 = time.monotonic()
    session_deadline = t0 + float(total_sec)
    rng = random.Random(seed)
    speech_count = init_speech_counts(AGENTS)
    obs_config = ObservationConfig()
    turn_index = 0
    max_speaker_attempts = len(AGENTS)

    while (time.monotonic() - t0) < debate_budget_sec:
        if debate_budget_sec - (time.monotonic() - t0) < MIN_DEBATE_TURN_SEC:
            logger.info(
                "swarm_debate_stop insufficient_turn_budget remaining_sec=%.2f",
                debate_budget_sec - (time.monotonic() - t0),
            )
            break
        visible_line: str | None = None
        visible_agent: dict[str, Any] | None = None

        for _attempt in range(max_speaker_attempts):
            if (time.monotonic() - t0) >= debate_budget_sec:
                break

            agent = pick_next_agent_swarm(AGENTS, rng, speech_count)
            speech_count[agent["id"]] = speech_count[agent["id"]] + 1

            remaining = int(debate_budget_sec - (time.monotonic() - t0))
            obs = build_observation(
                session_env,
                agent_id=agent["id"],
                agent_display_name=agent["name"],
                context_text=context,
                debate_seconds_remaining=max(0, remaining),
                config=obs_config,
            )
            user_body = json.dumps(obs, ensure_ascii=False) + "\n\nReturn your JSON decision now."
            sys_content = f"{agent['system']}{SWARM_JSON_RULES}"
            msgs = prepare_chat_messages(
                [
                    {"role": "system", "content": sys_content},
                    {"role": "user", "content": user_body},
                ],
                debate_model,
                llm,
            )
            kw = _completion_kw_for_messages(base_kw, msgs, llm, 2048)

            t_llm = time.monotonic()
            parsed: SwarmTurnResponse | None = None
            retry_count = 0
            turn_cap = max(2.0, debate_budget_sec - (time.monotonic() - t0) - 0.5)
            try:
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=debate_model,
                        response_format={"type": "json_object"},
                        messages=msgs,
                        **kw,
                    ),
                    timeout=turn_cap,
                )
                msg0 = _first_assistant_message(resp)
                if msg0 is None:
                    parsed = None
                else:
                    raw0 = _synth_raw_from_assistant_message(msg0)
                    try:
                        parsed = parse_swarm_turn_response(raw0)
                    except Exception as e1:
                        retry_count = 1
                        repair = (
                            f"Your previous output was invalid: {e1}. "
                            "Return ONLY one JSON object with a valid \"action\" and required fields."
                        )
                        msgs2 = prepare_chat_messages(
                            [
                                {"role": "system", "content": sys_content},
                                {"role": "user", "content": user_body},
                                {"role": "user", "content": repair},
                            ],
                            debate_model,
                            llm,
                        )
                        kw2 = _completion_kw_for_messages(base_kw, msgs2, llm, 2048)
                        retry_cap = max(2.0, debate_budget_sec - (time.monotonic() - t0) - 0.5)
                        resp2 = await asyncio.wait_for(
                            client.chat.completions.create(
                                model=debate_model,
                                response_format={"type": "json_object"},
                                messages=msgs2,
                                **kw2,
                            ),
                            timeout=retry_cap,
                        )
                        msg1 = _first_assistant_message(resp2)
                        if msg1 is None:
                            parsed = None
                        else:
                            raw1 = _synth_raw_from_assistant_message(msg1)
                            try:
                                parsed = parse_swarm_turn_response(raw1)
                            except Exception as e2:
                                logger.warning(
                                    "swarm JSON parse failed after retry",
                                    extra={
                                        "session_id": session_env.session_id,
                                        "agent_id": agent["id"],
                                        "turn_idx": turn_index,
                                        "errors": str(e2),
                                        "retry_count": retry_count,
                                    },
                                )
                                parsed = None
            except asyncio.TimeoutError:
                logger.warning(
                    "swarm turn timed out agent=%s cap_sec=%.1f",
                    agent["id"],
                    turn_cap,
                )
                parsed = None
            except Exception:
                logger.warning("swarm LLM call failed", exc_info=True)
                parsed = None

            latency_ms = (time.monotonic() - t_llm) * 1000.0

            if parsed is None:
                action: AgentAction = PassAction(agent_id=agent["id"])
                log_action = "pass"
            else:
                try:
                    action = swarm_response_to_agent_action(parsed, agent["id"])
                    log_action = parsed.action
                except Exception as e:
                    logger.warning(
                        "swarm map to action failed",
                        extra={
                            "session_id": session_env.session_id,
                            "agent_id": agent["id"],
                            "turn_idx": turn_index,
                            "errors": str(e),
                        },
                    )
                    action = PassAction(agent_id=agent["id"])
                    parsed = SwarmTurnResponse(action="pass")
                    log_action = "pass"

            display_parsed = parsed or SwarmTurnResponse(action="pass")
            applied_final: AgentAction = action

            result = apply_action(session_env, action)
            if not result.ok:
                logger.warning(
                    "swarm apply_action failed; falling back to pass",
                    extra={
                        "session_id": session_env.session_id,
                        "agent_id": agent["id"],
                        "turn_idx": turn_index,
                        "action": log_action,
                        "apply_ok": False,
                        "errors": result.errors,
                        "latency_ms": round(latency_ms, 1),
                        "retry_count": retry_count,
                    },
                )
                result = apply_action(session_env, PassAction(agent_id=agent["id"]))
                applied_final = PassAction(agent_id=agent["id"])
                display_parsed = SwarmTurnResponse(action="pass")

            if not result.ok:
                logger.error(
                    "swarm pass fallback failed",
                    extra={"session_id": session_env.session_id, "agent_id": agent["id"]},
                )
                return

            session_env = result.env
            line = transcript_line_for_turn(display_parsed, applied_final)
            visible_line = user_visible_turn_line(display_parsed, applied_final)

            logger.debug(
                "swarm turn",
                extra={
                    "session_id": session_env.session_id,
                    "agent_id": agent["id"],
                    "turn_idx": turn_index,
                    "action": log_action,
                    "apply_ok": True,
                    "visible": visible_line is not None,
                    "latency_ms": round(latency_ms, 1),
                    "retry_count": retry_count,
                },
            )

            transcript += f"\n\n[{agent['name']}]: {line}\n"

            if visible_line:
                visible_agent = agent
                break

        if not visible_line or not visible_agent:
            continue

        turn_index += 1
        yield {
            "type": "agent_start",
            "agent": visible_agent["id"],
            "name": visible_agent["name"],
            "turn": turn_index,
        }
        yield {
            "type": "agent_end",
            "agent": visible_agent["id"],
            "turn": turn_index,
            "full_text": visible_line,
            "reasoning_text": None,
        }

    yield {
        "type": "env_snapshot",
        "phase": "debate_end",
        "snapshot": snapshot_for_api(
            session_env,
            max_claim_text_in_snapshot=120,
            max_edges_in_snapshot=32,
        ),
    }

    yield {"type": "debate_phase_end", "turns_completed": turn_index}

    debate_elapsed = time.monotonic() - t0
    logger.info(
        "debate_phase_end turns=%s elapsed_sec=%.2f budget_sec=%.2f reserve_sec=%s overrun_sec=%.2f",
        turn_index,
        debate_elapsed,
        debate_budget_sec,
        SYNTH_RESERVE_SEC,
        max(0.0, debate_elapsed - debate_budget_sec),
    )

    async for ev in run_post_debate_phases(
        client,
        context=context,
        transcript=transcript,
        model=model,
        llm=llm,
        consensus_threshold=consensus_threshold,
        session_env_box=[session_env],
        synth_env_snapshot=synth_env_snapshot,
        effective_track=effective_track,
        session_deadline=session_deadline,
    ):
        yield ev
