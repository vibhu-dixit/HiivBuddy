"""Multi-agent debate + vote consensus + Chief Synthesizer. Core product logic."""

import asyncio
import hashlib
import json
import logging
import random
import re
import time
from collections import defaultdict
from typing import Any, AsyncIterator

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.debate.environment import DebateEnvironment, DebateOption, EnvLimits
from app.debate.environment_adapter import (
    apply_classic_interjection,
    apply_classic_utter,
    apply_vote_supports,
    merge_vote_options,
)
from app.debate.context_options import parse_options_from_context
from app.debate.environment_ops import init_environment, merge_options, snapshot_for_api
from app.debate.schemas import (
    AgentStanceItem,
    AgentVoteResponse,
    ClosingPhaseResponse,
    ClosingVoteItem,
    FinalReport,
    RankedOption,
    SYNTH_API_TIMEOUT_SEC,
    SYNTH_RESERVE_SEC,
    MIN_DEBATE_TURN_SEC,
    OPTION_SEED_MAX_SEC,
    VoteOptionItem,
    VoteOptionsResponse,
)
from app.llm.client import Settings
from app.llm.messages import prepare_chat_messages

logger = logging.getLogger(__name__)


def _delta_content_piece(delta: Any) -> str:
    """Normalize OpenAI-style `delta.content` (str, or list of text parts) to a single string."""
    c = getattr(delta, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for part in c:
            if isinstance(part, dict):
                t = part.get("text")
                if isinstance(t, str):
                    parts.append(t)
                elif isinstance(part.get("content"), str):
                    parts.append(part["content"])
            else:
                t = getattr(part, "text", None)
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return str(c) if c else ""


def _debate_environment_seed(context: str, explicit: int | None) -> int:
    if explicit is not None:
        return int(explicit) & 0x7FFFFFFF
    digest = hashlib.sha256(context.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _synth_raw_from_assistant_message(msg: Any) -> str:
    """NVIDIA thinking models often return empty `content` and put JSON in `reasoning_content`."""

    def _strip_md_fences(s: str) -> str:
        t = (s or "").strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
        if m:
            return m.group(1).strip()
        return t

    c = getattr(msg, "content", None)
    if isinstance(c, str) and c.strip():
        return _strip_md_fences(c)
    r = getattr(msg, "reasoning_content", None)
    if isinstance(r, str) and r.strip():
        return _strip_md_fences(r)
    return "{}"


def _first_assistant_message(resp: Any) -> Any | None:
    """Return the first assistant message, or None if the provider returned no choices."""
    choices = getattr(resp, "choices", None)
    if not choices:
        logger.warning(
            "LLM completion missing choices model=%s id=%s",
            getattr(resp, "model", None),
            getattr(resp, "id", None),
        )
        return None
    try:
        return choices[0].message
    except (AttributeError, IndexError, TypeError):
        logger.warning("LLM completion choices[0] unusable", exc_info=True)
        return None


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


def _parse_json_to_model(raw: str, model_cls: type[BaseModel]) -> BaseModel:
    candidates: list[str] = []
    if raw.strip():
        candidates.append(raw.strip())
    ext = _extract_json_object(raw)
    if ext and ext not in candidates:
        candidates.append(ext)
    last_err: Exception | None = None
    for cand in candidates:
        try:
            return model_cls.model_validate_json(cand)
        except Exception as e:
            last_err = e
        try:
            return model_cls.model_validate(json.loads(cand))
        except Exception as e:
            last_err = e
    raise last_err if last_err else ValueError(f"Could not parse {model_cls.__name__}")


def _parse_final_report(raw: str) -> FinalReport:
    out = _parse_json_to_model(raw, FinalReport)
    assert isinstance(out, FinalReport)
    return out


def _normalize_vote_options(parsed: VoteOptionsResponse) -> list[VoteOptionItem]:
    """Force sequential ids 0..n-1 so votes and tallies stay consistent."""
    return [
        VoteOptionItem(id=str(i), title=o.title.strip()[:500])
        for i, o in enumerate(parsed.options)
    ]


AGENTS: list[dict[str, str]] = [
    {
        "id": "optimist",
        "name": "Optimist",
        "system": (
            "You are the Optimist. Highlight upside, opportunities, and best-case outcomes. "
            "Be specific to the user's context. Do not hedge into a full balance sheet; lean positive."
        ),
    },
    {
        "id": "devils_advocate",
        "name": "Devil's Advocate",
        "system": (
            "You are the Devil's Advocate. Challenge assumptions, surface hidden flaws, "
            "and argue against the most obvious path. Be constructive, not cynical."
        ),
    },
    {
        "id": "data_analyst",
        "name": "Data Analyst",
        "system": (
            "You are the Data Analyst. Ask what we'd need to measure, what metrics matter, "
            "and what evidence would change the decision. Prefer clarity over jargon."
        ),
    },
    {
        "id": "risk_guru",
        "name": "Risk Guru",
        "system": (
            "You are the Risk Guru. Enumerate downside scenarios, tail risks, and mitigation ideas. "
            "Prioritize likelihood × impact."
        ),
    },
    {
        "id": "ethical_guardian",
        "name": "Ethical Guardian",
        "system": (
            "You are the Ethical Guardian. Call out stakeholders, fairness, and long-term reputation. "
            "Flag ethical tension without moralizing."
        ),
    },
]

SYNTH_SYSTEM = """You are the Chief Synthesizer for Hiiv.
You receive the decision context, full timed debate transcript, an anonymous vote tally per advisor, and a compact per-advisor stance trace (lean + confidence).
Return ONLY valid JSON (no markdown) with keys:
- summary: string (executive overview, 3-5 sentences). Mention whether a 3/5 (or configured threshold) consensus was reached and on which option if so; if not, say the panel was split.
- ranked_options: array of { "title": string, "score": number 0-1, "rationale": string } (2-4 options). Align top-ranked option with the vote winner when consensus exists.
- risks: array of short strings (top risks)
- next_steps: array of concrete next actions
Use the stance trace to weight disagreements and uncertainty; scores should reflect consensus strength and fit to stated goals."""


CLOSING_SYSTEM = """You extract closing decision data from a timed debate transcript.
Return ONLY valid JSON with keys:
- options: array of 2-4 objects {"id":"0","title":"short label"}, ids "0","1","2","3" in order. Titles must be distinct and reflect main forks.
- votes: array of exactly 5 objects, one per advisor id in [optimist, devils_advocate, data_analyst, risk_guru, ethical_guardian], each {"agent_id","option_id","rationale"} (one short sentence rationale).
- agent_stances: array of exactly 5 objects, same agent_ids, each {"agent_id","lean":"short phrase","confidence":number 0-1,"note":"optional"}
confidence reflects how firm the advisor is; lean summarizes their current recommendation direction."""


INTERJECTION_SYSTEM_ADDENDUM = (
    " Interjection: at most two sentences, spoken dialogue only—respond as you would at the table. "
    "Do not quote instructions or summarize the prompt. If nothing to add, output exactly PASS alone."
)

# Primary turns: natural speech; post-processing strips meta (see _clean_primary_spoken_text).
PRIMARY_DEBATE_SYSTEM_ADDENDUM = (
    " You are speaking aloud at a conference table, not writing an essay. "
    "At most three sentences, no bullets. "
    "Speak in first person; jump straight into substance—do not quote moderator cues, rubric lines, "
    "or narrate your role. Address other advisors by name when you respond to them."
)


def _interjection_content_only(msg: Any) -> str:
    """Interjections must never use reasoning/thinking channels — only public speech."""
    c = getattr(msg, "content", None)
    if isinstance(c, str) and c.strip():
        return c.strip()
    return ""


def _is_degenerate_repetitive_output(text: str) -> bool:
    """True for token loops, template spam, or severe mojibake (some NVIDIA models)."""
    t = (text or "").strip()
    if len(t) < 24:
        return False
    low = t.lower()
    if low.count("we answered") >= 3:
        return True
    if low.count("answered:") >= 5:
        return True
    if low.count("answered answered") >= 2:
        return True
    # Repeated bracket / template sludge (common in bad completions)
    if t.count("Суди") >= 2 or t.count("Sędziowie") >= 2:
        return True
    if t.count("�") >= 2 or t.count("\ufffd") >= 2:
        return True
    # Same 10–80 char chunk repeated many times (repetition loops)
    if re.search(r"(.{10,80})\1{2,}", t, flags=re.DOTALL):
        return True
    # Extremely low symbol diversity in a long string
    if len(t) > 200:
        sample = t[:400]
        if len(set(sample)) < 18:
            return True
    return False


_MOD_ECHO_PHRASES_SCRUB = (
    "must be in-character",
    "spoken dialogue only",
    "build on prior turns",
    "respond to others by name",
    "stress-test one main argument",
    "output: at most three sentences",
    "no meta commentary",
    "the instruction at the bottom",
    "we must not restate moderator",
    "we must not quote prompts",
    "we need to give initial stance",
    "i don't have access to the exact text",
    "i don't have access to",
    "risk guru (just now): must ",
    "data analyst (just now): build on",
    "the user gave a long context",
    # Past user-message cues models echoed into speech
    "jump in:",
    "name another advisor",
    "build on the thread:",
    "bottom line:",
    "then instruction",
    "begin with \"i think\"",
    "do not repeat or quote",
    "max three short sentences",
    "round: opening",
    "round: reply",
    "round: recommendation",
    "round: extend",
    "the user provided",
    "we are in a conversation where",
    "turn 1:",
    "turn 2:",
    "the user has pasted",
)


def _scrub_transcript_tail_for_prompt(text: str, *, max_chars: int = 12000) -> str:
    """Drop lines that are clearly moderator/instruction echoes so later turns do not amplify them."""
    if not (text or "").strip():
        return ""
    banned = tuple(s.lower() for s in _MOD_ECHO_PHRASES_SCRUB)
    kept: list[str] = []
    for line in text.splitlines():
        low = line.strip().lower()
        if not low:
            continue
        if any(b in low for b in banned):
            continue
        if low.startswith("we need to ") and any(
            x in low for x in ("instruction", "output", "respond as", "produce")
        ):
            continue
        kept.append(line.rstrip())
    out = "\n".join(kept).strip()
    if len(out) > max_chars:
        out = "…\n" + out[-max_chars:].lstrip()
    return out


def _looks_like_moderator_echo(text: str) -> bool:
    """Nemotron-class models often parrot our rules back; treat as non-speech."""
    low = (text or "").lower().strip()
    if not low:
        return False
    if any(p in low for p in _MOD_ECHO_PHRASES_SCRUB):
        return True
    if "must build on" in low and "prior turns" in low and len(low) < 500:
        return True
    if low.startswith("we need to give ") and "sentence" in low:
        return True
    if "let me think about the" in low and "role" in low and len(low) < 400:
        return True
    if "please read the following faq" in low:
        return True
    if "jump in" in low and "advisor" in low and len(low) < 700:
        return True
    if "the debate so far" in low and "turn" in low and len(low) > 400:
        return True
    return False


def _is_near_duplicate_primary(prev: str, cur: str) -> bool:
    """Drop a turn that largely repeats the last primary speech (common model stutter)."""
    a = (prev or "").strip().lower()
    b = (cur or "").strip().lower()
    if len(a) < 32 or len(b) < 32:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 48 and shorter in longer:
        return True
    return False


def _strip_transcript_artifacts(text: str) -> str:
    """Remove pasted transcript markers some models echo into content."""
    t = text or ""
    t = re.sub(r"\[Turn\s*\d+\]\s*\[[^\]\n]{1,120}\]:\s*", "", t, flags=re.IGNORECASE)
    return t.strip()


def _clean_primary_spoken_text(text: str) -> str:
    """Drop planning noise: optional slice after 'I think', else drop meta-looking paragraphs."""
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    key = "i think"
    idx = low.find(key)
    if idx >= 0:
        return t[idx:].strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n+", t) if p.strip()]
    if not paras:
        return t
    if len(paras) == 1:
        p0 = paras[0]
        return "" if _looks_like_moderator_echo(p0) else p0
    kept = [p for p in paras if not _looks_like_moderator_echo(p)]
    if kept:
        return "\n\n".join(kept).strip()
    return paras[-1]


def _normalize_spoken_line(text: str, max_sentences: int) -> str:
    """Strip transcript junk, drop meta preambles, then cap sentence count."""
    t = _strip_transcript_artifacts((text or "").strip())
    t = _clean_primary_spoken_text(t)
    return _trim_to_max_sentences(t, max_sentences)


def _salvage_quoted_speech(text: str) -> str | None:
    """Longest quoted span that looks like table speech, not rubric."""
    best: str | None = None
    for m in re.finditer(r'"([^"]{18,800})"', text or "", re.DOTALL):
        inner = " ".join(m.group(1).strip().split())
        if not inner or _is_degenerate_repetitive_output(inner) or _looks_like_moderator_echo(inner):
            continue
        if best is None or len(inner) > len(best):
            best = inner
    return best


def _short_interjection_kwargs(base_kw: dict[str, Any]) -> dict[str, Any]:
    """Smaller completions; drop thinking extras so interjections stay quick and on-format."""
    out = dict(base_kw)
    cap = min(160, int(out.get("max_tokens", 16384)))
    out["max_tokens"] = cap
    out.pop("extra_body", None)
    return out


def _is_pass_interjection(text: str) -> bool:
    first = (text or "").strip().splitlines()
    if not first:
        return True
    line0 = first[0].strip().upper()
    return line0 == "PASS" or line0.startswith("PASS ")


def _clean_interjection(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    lines = t.splitlines()
    if lines and lines[0].strip().upper().startswith("PASS"):
        lines = lines[1:]
    return "\n".join(lines).strip()


async def _interjection_reply(
    client: AsyncOpenAI,
    *,
    model: str,
    kw: dict[str, Any],
    llm: Settings,
    context: str,
    transcript_tail: str,
    speaker: dict[str, str],
    last_text: str,
    other: dict[str, str],
    turn_index: int,
) -> str | None:
    """One advisor responds to the last primary speech; returns None on failure or PASS."""
    ctx_short = (context or "").strip().replace("\r\n", "\n")
    if len(ctx_short) > 700:
        ctx_short = ctx_short[:697].rstrip() + "…"
    tail = _scrub_transcript_tail_for_prompt(
        (transcript_tail or "").strip().replace("\r\n", "\n"),
        max_chars=4500,
    )
    if len(tail) > 4500:
        tail = "…\n" + tail[-4500:].lstrip()
    last_s = (last_text or "").strip()
    if len(last_s) > 1200:
        last_s = last_s[:1197].rstrip() + "…"
    user = (
        f"Situation:\n{ctx_short}\n\n"
        f"Thread:\n{tail}\n\n"
        f"{speaker['name']} (just now): {last_s}\n\n"
        f"You are {other['name']}. In at most two short sentences, add one factual correction or new fact "
        f"that responds to what they just said—spoken dialogue only. "
        f"If you have nothing to add, reply with exactly the word PASS on its own line. "
        f"Do not restate the moderator rules, do not quote prompts, and do not repeat {speaker['name']}'s wording."
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=prepare_chat_messages(
                [
                    {
                        "role": "system",
                        "content": f"{other['system']}{INTERJECTION_SYSTEM_ADDENDUM}",
                    },
                    {"role": "user", "content": user},
                ],
                model,
                llm,
            ),
            **kw,
        )
        msg = _first_assistant_message(resp)
        if msg is None:
            return None
        raw = _interjection_content_only(msg)
    except Exception:
        return None
    if not raw or _is_pass_interjection(raw):
        return None
    cleaned = _clean_interjection(raw)
    cleaned = _normalize_spoken_line(cleaned, 2)
    if not cleaned.strip():
        alt = _salvage_quoted_speech(raw)
        if alt:
            cleaned = _normalize_spoken_line(alt, 2)
    if not cleaned or re.match(r"^(PASS|NO\s*INTERRUPTION)\b", cleaned, re.I):
        return None
    if _is_degenerate_repetitive_output(cleaned):
        return None
    if _looks_like_moderator_echo(cleaned):
        return None
    return cleaned


def _trim_to_max_sentences(text: str, max_sentences: int = 3) -> str:
    """Keep first N sentences (rough split on . ! ?)."""
    if not text or max_sentences <= 0:
        return (text or "").strip()
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences]).strip()


def _primary_debate_kwargs(base_kw: dict[str, Any]) -> dict[str, Any]:
    """Short replies: cap tokens for ~3 sentences; disable thinking so planning stays out of `content`."""
    out = dict(base_kw)
    cap = min(420, int(out.get("max_tokens", 16384)))
    out["max_tokens"] = cap
    # NVIDIA-style CoT often leaks into visible `content` or encourages rubric-style answers.
    out.pop("extra_body", None)
    return out


def _approx_prompt_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough input token estimate (~4 chars/token) plus small overhead; conservative for max_tokens capping."""
    n = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            n += max(1, len(c) // 4)
        else:
            n += 100
    return n + 32 * len(messages)


def _completion_kw_for_messages(
    base_kw: dict[str, Any],
    messages: list[dict[str, Any]],
    llm: Settings,
    desired_max: int,
) -> dict[str, Any]:
    """Cap max_tokens so prompt + completion stays within llm_context_tokens (provider rejects if too large)."""
    raw = _approx_prompt_tokens(messages)
    est_in = int(raw * 1.1) + 64
    buffer = 128
    avail = llm.llm_context_tokens - est_in - buffer
    if avail < 1:
        avail = 1
    cap = min(int(base_kw.get("max_tokens", desired_max)), desired_max, avail)
    out = dict(base_kw)
    out["max_tokens"] = max(1, cap)
    return out


def _debate_deadline_elapsed(t0: float, debate_budget_sec: float) -> bool:
    return (time.monotonic() - t0) >= debate_budget_sec


def _timed_debate_user_block(turn_index: int) -> str:
    """Minimal turn cue only—constraints live in system messages so models do not quote rubric lines aloud."""
    if turn_index <= 1:
        return "Round: opening."
    if turn_index <= 5:
        return "Round: reply to another advisor by name."
    if turn_index % 5 == 0:
        return "Round: state your recommendation and what would change your mind."
    return "Round: extend or challenge the thread."


def _closing_votes_to_records(
    parsed: ClosingPhaseResponse,
    allowed_ids: set[str],
) -> list[dict[str, str]]:
    """Normalize batched votes to the same shape as the old sequential flow."""
    by_agent: dict[str, ClosingVoteItem] = {v.agent_id: v for v in parsed.votes}
    vote_records: list[dict[str, str]] = []
    fallback_id = min(allowed_ids, key=lambda x: int(x)) if allowed_ids else "0"
    for agent in AGENTS:
        v = by_agent.get(agent["id"])
        if v is None:
            oid = fallback_id
            rationale = ""
        else:
            oid = (v.option_id or "").strip()
            rationale = (v.rationale or "")[:300]
            if oid not in allowed_ids:
                try:
                    cand = str(int(float(oid)))
                    if cand in allowed_ids:
                        oid = cand
                    else:
                        oid = fallback_id
                except (ValueError, TypeError):
                    oid = fallback_id
        vote_records.append(
            {
                "agent_id": agent["id"],
                "name": agent["name"],
                "option_id": oid,
                "rationale": rationale,
            }
        )
    return vote_records


def _stance_list_to_trace(stances: list[AgentStanceItem]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in stances:
        name = next((a["name"] for a in AGENTS if a["id"] == s.agent_id), s.agent_id)
        out.append(
            {
                "agent_id": s.agent_id,
                "name": name,
                "lean": (s.lean or "")[:400],
                "confidence": float(s.confidence),
                "note": (s.note or "")[:400],
            }
        )
    return out


OPTIONS_FALLBACK_SYSTEM = """You extract discrete decision options for a panel vote.
Return ONLY valid JSON: {"options": [{"id":"0","title":"short label"}, ...]}
Use 2 to 4 options, ids "0","1","2","3" in order. Titles must be mutually distinct and reflect main forks from the debate."""

OPTIONS_SEED_SYSTEM = """You prepare a founder decision session before a panel debate.
Given a brief (questions or narrative), propose 2-4 distinct strategic paths the advisors should argue about and later vote on.
Return ONLY valid JSON: {"options":[{"id":"0","title":"concrete path under 100 chars"}, ...]}
Use ids "0","1","2","3" in order. Titles must be specific decision forks—not placeholders like "primary path" or "option A"."""

_DEFAULT_VOTE_OPTIONS = [
    VoteOptionItem(id="0", title="Primary path from the debate"),
    VoteOptionItem(id="1", title="Alternative path from the debate"),
]


def _synth_model_candidates(llm: Settings, request_model: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for candidate in (
        llm.resolved_synth_model(request_model),
        llm.resolved_debate_model(request_model),
        (request_model or "").strip(),
        getattr(llm, "llm_default_model", "") or "",
    ):
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


async def _create_json_completion(
    client: AsyncOpenAI,
    *,
    models: list[str],
    messages: list[dict[str, Any]],
    llm: Settings,
    max_tokens: int = 4096,
) -> tuple[str, Any]:
    base_kw = llm.common_completion_kwargs()
    last_exc: Exception | None = None
    for model_id in models:
        try:
            resp = await client.chat.completions.create(
                model=model_id,
                response_format={"type": "json_object"},
                messages=messages,
                **_completion_kw_for_messages(base_kw, messages, llm, max_tokens),
            )
            return model_id, resp
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM json completion failed model=%s: %s", model_id, exc)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No LLM model configured for synthesis")


def _seconds_until(deadline: float | None) -> float:
    if deadline is None:
        return float("inf")
    return max(0.0, deadline - time.monotonic())


def _instant_default_closing() -> ClosingPhaseResponse:
    default_stances = [
        AgentStanceItem(agent_id=a["id"], lean="unknown", confidence=0.0, note="")
        for a in AGENTS
    ]
    vote_items = [
        ClosingVoteItem(agent_id=a["id"], option_id="0", rationale="")
        for a in AGENTS
    ]
    return ClosingPhaseResponse(
        options=list(_DEFAULT_VOTE_OPTIONS),
        votes=vote_items,
        agent_stances=default_stances,
    )


def _heuristic_options_from_context(context: str) -> list[DebateOption]:
    """Offline fallback when option-seed LLM fails (demo-friendly)."""
    lower = context.lower()
    if any(k in lower for k in ("love", "pay", "runway", "money", "scale", "customer")):
        return [
            DebateOption(id="0", title="Love-first: retention and NPS before scaling"),
            DebateOption(id="1", title="Runway-first: revenue and unit economics before growth"),
            DebateOption(id="2", title="Dual-track: PMF iteration with strict cash guardrails"),
        ]
    return [
        DebateOption(id="0", title="Aggressive path on the stated opportunity"),
        DebateOption(id="1", title="Conservative path preserving runway and focus"),
    ]


async def ensure_session_options(
    client: AsyncOpenAI,
    *,
    context: str,
    model: str,
    llm: Settings,
    env: DebateEnvironment,
) -> tuple[DebateEnvironment, list[DebateOption]]:
    """Parse numbered options from the brief, or generate them before debate starts."""
    parsed = parse_options_from_context(context)
    if len(parsed) >= 2:
        merged = merge_options(env, parsed)
        logger.info("option_seed_parsed_from_context count=%d", len(parsed))
        return merged, parsed

    seed_models = _synth_model_candidates(llm, model)
    seed_user = (
        f"Decision brief:\n{context.strip()}\n\n"
        "Return JSON with an options array (2-4 distinct strategic paths) now."
    )
    seed_msgs = prepare_chat_messages(
        [
            {"role": "system", "content": OPTIONS_SEED_SYSTEM},
            {"role": "user", "content": seed_user},
        ],
        seed_models[0],
        llm,
    )
    try:
        _, resp = await asyncio.wait_for(
            _create_json_completion(
                client,
                models=seed_models,
                messages=seed_msgs,
                llm=llm,
                max_tokens=512,
            ),
            timeout=float(OPTION_SEED_MAX_SEC),
        )
        msg = _first_assistant_message(resp)
        if msg is not None:
            raw = _synth_raw_from_assistant_message(msg)
            vo = _parse_json_to_model(raw, VoteOptionsResponse)
            normalized = _normalize_vote_options(vo)
            opts = [DebateOption(id=o.id, title=o.title) for o in normalized[:4]]
            if len(opts) >= 2:
                merged = merge_options(env, opts)
                logger.info("option_seed_llm count=%d", len(opts))
                return merged, opts
    except asyncio.TimeoutError:
        logger.warning("option_seed_llm_timed_out budget_sec=%s", OPTION_SEED_MAX_SEC)
    except Exception:
        logger.warning("option_seed_llm_failed", exc_info=True)

    fallback = _heuristic_options_from_context(context)
    merged = merge_options(env, fallback)
    logger.info("option_seed_heuristic count=%d", len(fallback))
    return merged, fallback


def _closing_from_environment(se: DebateEnvironment | None) -> ClosingPhaseResponse:
    """Votes from debate: each advisor's last focused option, else panel-wide support leader."""
    if se is None or len(se.options_by_id) < 2:
        return _instant_default_closing()

    vote_opts = sorted(
        [VoteOptionItem(id=o.id, title=o.title) for o in se.options_by_id.values()],
        key=lambda x: int(x.id) if x.id.isdigit() else 99,
    )
    allowed = {o.id for o in vote_opts}
    panel_pick = vote_opts[0].id
    if se.option_support_scores:
        panel_pick = max(
            allowed,
            key=lambda k: float(se.option_support_scores.get(k, 0.5)),
        )

    default_stances = [
        AgentStanceItem(agent_id=a["id"], lean="unknown", confidence=0.0, note="")
        for a in AGENTS
    ]
    vote_items: list[ClosingVoteItem] = []
    for a in AGENTS:
        aid = a["id"]
        st = se.agent_state_by_id.get(aid)
        oid = st.focus_option_id if st and st.focus_option_id in allowed else panel_pick
        vote_items.append(ClosingVoteItem(agent_id=aid, option_id=oid, rationale=""))

    return ClosingPhaseResponse(
        options=vote_opts,
        votes=vote_items,
        agent_stances=default_stances,
    )


def _closing_from_context(context: str) -> ClosingPhaseResponse:
    """Instant vote phase from parsed context options — no LLM (preserves synth budget)."""
    parsed_opts = parse_options_from_context(context)
    if len(parsed_opts) < 2:
        return _instant_default_closing()

    vote_opts = [
        VoteOptionItem(id=str(i), title=o.title)
        for i, o in enumerate(parsed_opts[:4])
    ]
    n = len(vote_opts)
    default_stances = [
        AgentStanceItem(agent_id=a["id"], lean="unknown", confidence=0.0, note="")
        for a in AGENTS
    ]
    vote_items = [
        ClosingVoteItem(
            agent_id=a["id"],
            option_id=str(i % n),
            rationale="",
        )
        for i, a in enumerate(AGENTS)
    ]
    return ClosingPhaseResponse(
        options=vote_opts,
        votes=vote_items,
        agent_stances=default_stances,
    )


async def _parse_closing_from_llm(
    client: AsyncOpenAI,
    *,
    synth_models: list[str],
    closing_msgs: list[dict[str, Any]],
    llm: Settings,
) -> tuple[str, ClosingPhaseResponse]:
    synth_model, closing_resp = await _create_json_completion(
        client,
        models=synth_models,
        messages=closing_msgs,
        llm=llm,
    )
    closing_msg = _first_assistant_message(closing_resp)
    if closing_msg is None:
        raise ValueError("LLM response missing choices")
    closing_raw = _synth_raw_from_assistant_message(closing_msg)
    parsed = _parse_json_to_model(closing_raw, ClosingPhaseResponse)
    assert isinstance(parsed, ClosingPhaseResponse)
    return synth_model, parsed


async def run_post_debate_phases(
    client: AsyncOpenAI,
    *,
    context: str,
    transcript: str,
    model: str,
    llm: Settings,
    consensus_threshold: int,
    session_env_box: list[DebateEnvironment | None],
    synth_env_snapshot: bool,
    effective_track: bool,
    session_deadline: float | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Vote extraction, tally, Chief Synthesizer — shared by classic and structured swarm."""
    t_post0 = time.monotonic()
    threshold = max(1, min(5, consensus_threshold))
    synth_models = _synth_model_candidates(llm, model)
    synth_model = synth_models[0]
    se = session_env_box[0]

    logger.info("post_debate_start vote_phase_begin")

    yield {"type": "vote_phase_start"}

    t_vote0 = time.monotonic()
    parsed_closing = _closing_from_environment(se)
    vote_phase_sec = time.monotonic() - t_vote0
    logger.info(
        "vote_phase_from_debate elapsed_sec=%.3f options=%d",
        vote_phase_sec,
        len(parsed_closing.options),
    )

    vote_opts = _normalize_vote_options(VoteOptionsResponse(options=parsed_closing.options))
    allowed_ids = {o.id for o in vote_opts}
    opt_payload = [{"id": o.id, "title": o.title} for o in vote_opts]
    yield {"type": "vote_options", "options": opt_payload}

    vote_records = _closing_votes_to_records(parsed_closing, allowed_ids)
    if effective_track and se is not None:
        se = merge_vote_options(se, list(vote_opts))
        se = apply_vote_supports(se, vote_records, n_agents=len(AGENTS))
        session_env_box[0] = se
    stance_trace = _stance_list_to_trace(parsed_closing.agent_stances)
    yield {"type": "agent_decision_trace", "stances": stance_trace}

    for vr in vote_records:
        yield {
            "type": "vote_cast",
            "agent": vr["agent_id"],
            "name": vr["name"],
            "option_id": vr["option_id"],
            "rationale": vr["rationale"],
        }

    counts: dict[str, int] = defaultdict(int)
    for vr in vote_records:
        counts[vr["option_id"]] += 1

    winning_option_id: str | None = None
    consensus_reached = False
    if counts:
        best_count = max(counts.values())
        winners = [k for k, v in counts.items() if v == best_count]
        if len(winners) == 1 and best_count >= threshold:
            winning_option_id = winners[0]
            consensus_reached = True

    id_to_title = {o.id: o.title for o in vote_opts}
    tallies = {k: counts[k] for k in sorted(counts.keys(), key=lambda x: int(x) if x.isdigit() else 99)}

    yield {
        "type": "vote_tally",
        "tallies": tallies,
        "votes": vote_records,
        "consensus_reached": consensus_reached,
        "winning_option_id": winning_option_id,
        "winning_title": id_to_title.get(winning_option_id or "", ""),
        "threshold": threshold,
    }

    se = session_env_box[0]
    if effective_track and se is not None:
        yield {
            "type": "env_snapshot",
            "phase": "post_vote",
            "snapshot": snapshot_for_api(
                se,
                max_claim_text_in_snapshot=160,
                max_edges_in_snapshot=48,
            ),
        }

    yield {"type": "synthesizer_start"}

    vote_total_sec = time.monotonic() - t_post0
    logger.info(
        "synthesizer_start vote_phase_total_sec=%.2f synth_timeout_sec=%s",
        vote_total_sec,
        SYNTH_API_TIMEOUT_SEC,
    )

    vote_summary = json.dumps(
        {
            "tallies": tallies,
            "consensus_reached": consensus_reached,
            "winning_option_id": winning_option_id,
            "winning_title": id_to_title.get(winning_option_id or "", ""),
            "threshold_at_least": threshold,
            "per_agent_votes": vote_records,
        },
        ensure_ascii=False,
    )
    stance_summary = json.dumps(stance_trace, ensure_ascii=False)

    synth_user = (
        f"Decision context:\n{context}\n\n"
        f"Full debate transcript:\n{transcript}\n\n"
        f"Vote summary (JSON):\n{vote_summary}\n\n"
        f"Agent stance trace (JSON):\n{stance_summary}\n\n"
    )
    se = session_env_box[0]
    if synth_env_snapshot and se is not None:
        env_snap_txt = json.dumps(
            snapshot_for_api(
                se,
                max_claim_text_in_snapshot=200,
                max_edges_in_snapshot=64,
            ),
            ensure_ascii=False,
        )
        synth_user += f"Environment snapshot (JSON):\n{env_snap_txt}\n\n"
    synth_user += "Produce the final JSON report object now."

    synth_msgs = prepare_chat_messages(
        [
            {"role": "system", "content": SYNTH_SYSTEM},
            {"role": "user", "content": synth_user},
        ],
        synth_model,
        llm,
    )

    win_title = id_to_title.get(winning_option_id or "", "Options")
    base_ranked = [
        RankedOption(
            title=win_title,
            score=0.5,
            rationale="Fallback while the full report was unavailable.",
        )
    ]

    try:
        t_synth0 = time.monotonic()
        synth_timeout = min(float(SYNTH_API_TIMEOUT_SEC), _seconds_until(session_deadline))
        logger.info("synthesizer_llm_begin timeout_sec=%.2f", synth_timeout)
        if synth_timeout <= 0:
            raise asyncio.TimeoutError("no time left for synthesizer")
        _, resp = await asyncio.wait_for(
            _create_json_completion(
                client,
                models=synth_models,
                messages=synth_msgs,
                llm=llm,
                max_tokens=2048,
            ),
            timeout=synth_timeout,
        )
        synth_llm_sec = time.monotonic() - t_synth0
        logger.info("synthesizer_llm_done elapsed_sec=%.2f", synth_llm_sec)
    except asyncio.TimeoutError:
        synth_llm_sec = time.monotonic() - t_synth0
        logger.warning(
            "synthesizer_llm_timeout elapsed_sec=%.2f limit=%.2f",
            synth_llm_sec,
            synth_timeout,
        )
        report = FinalReport(
            summary=(
                "The Chief Synthesizer hit the server time limit while generating the report. "
                "Votes and transcript above are still valid."
            ),
            ranked_options=base_ranked,
            risks=[
                "Structured report timed out—use the vote tally and transcript as the source of truth."
            ],
            next_steps=[
                "Retry (or pick a faster model / shorter debate) if this happens often.",
            ],
        )
    except Exception:
        logger.warning("Chief Synthesizer API call failed", exc_info=True)
        report = FinalReport(
            summary=(
                "The Chief Synthesizer request did not complete (API or network error). "
                "See transcript and votes above."
            ),
            ranked_options=base_ranked,
            risks=["Final narrative unavailable—provider or connectivity may be at fault."],
            next_steps=["Retry when the API is responsive; check keys and model availability."],
        )
    else:
        try:
            msg = _first_assistant_message(resp)
            if msg is None:
                raise ValueError("LLM response missing choices")
            raw = _synth_raw_from_assistant_message(msg)
            report = _parse_final_report(raw)
        except Exception:
            logger.warning("Chief Synthesizer returned unparseable JSON", exc_info=True)
            report = FinalReport(
                summary=(
                    "The Chief Synthesizer returned output we could not parse into the report format. "
                    "Use the transcript and votes above."
                ),
                ranked_options=base_ranked,
                risks=["Report JSON was invalid or incomplete—panel discussion remains usable."],
                next_steps=["Re-run the debate or retry; if it recurs, try another model."],
            )

    se = session_env_box[0]
    env_snap_final = None
    if se is not None and (effective_track or synth_env_snapshot):
        env_snap_final = snapshot_for_api(
            se,
            max_claim_text_in_snapshot=200,
            max_edges_in_snapshot=64,
        )
    final_payload: dict[str, Any] = {"type": "final_report", "report": report.model_dump()}
    if env_snap_final is not None:
        final_payload["env_snapshot"] = env_snap_final
    post_total_sec = time.monotonic() - t_post0
    logger.info(
        "final_report_ready post_debate_total_sec=%.2f (vote+synth)",
        post_total_sec,
    )
    yield final_payload


async def run_debate_stream(
    client: AsyncOpenAI,
    *,
    context: str,
    model: str,
    llm: Settings,
    session_duration_sec: int = 120,
    consensus_threshold: int = 3,
    enable_interjections: bool = True,
    track_environment: bool = False,
    synth_env_snapshot: bool = False,
    environment_rng_seed: int | None = None,
    env_limits: EnvLimits | None = None,
) -> AsyncIterator[dict[str, Any]]:
    total_sec = max(60, min(600, session_duration_sec))
    debate_budget_sec = max(0.0, float(total_sec - SYNTH_RESERVE_SEC))
    t0 = time.monotonic()
    transcript = ""
    base_kw = llm.common_completion_kwargs()
    primary_kw = _primary_debate_kwargs(base_kw)
    debate_model = llm.resolved_debate_model(model)

    yield {
        "type": "session_start",
        "session_duration_sec": total_sec,
        "debate_budget_sec": debate_budget_sec,
        "synth_reserve_sec": SYNTH_RESERVE_SEC,
    }

    session_deadline = t0 + float(total_sec)

    effective_track = track_environment
    need_env = effective_track or synth_env_snapshot
    limits = env_limits or EnvLimits()
    seed = _debate_environment_seed(context, environment_rng_seed)
    session_env: DebateEnvironment | None
    if need_env:
        session_env = init_environment(
            context,
            rng_seed=seed,
            limits=limits,
            mode="classic",
        )
    else:
        session_env = None

    n_agents = len(AGENTS)
    rotation_order = list(AGENTS)
    random.shuffle(rotation_order)
    rr = 0
    turn_index = 0
    last_primary_speech = ""
    while not _debate_deadline_elapsed(t0, debate_budget_sec):
        if debate_budget_sec - (time.monotonic() - t0) < MIN_DEBATE_TURN_SEC:
            logger.info(
                "debate_phase_stop insufficient_turn_budget remaining_sec=%.2f",
                debate_budget_sec - (time.monotonic() - t0),
            )
            break
        agent = rotation_order[rr % n_agents]
        rr += 1
        turn_index += 1
        yield {
            "type": "agent_start",
            "agent": agent["id"],
            "name": agent["name"],
            "turn": turn_index,
        }

        # Plain prose only — labeled headers like "Decision context:" get echoed into speech by models.
        user_parts: list[str] = [context.strip()]
        if transcript.strip():
            user_parts.append(_scrub_transcript_tail_for_prompt(transcript))
        user_content = "\n\n".join(user_parts) + "\n\n" + _timed_debate_user_block(turn_index)

        stream = await client.chat.completions.create(
            model=debate_model,
            stream=True,
            messages=prepare_chat_messages(
                [
                    {
                        "role": "system",
                        "content": f"{agent['system']}{PRIMARY_DEBATE_SYSTEM_ADDENDUM}",
                    },
                    {"role": "user", "content": user_content},
                ],
                debate_model,
                llm,
            ),
            **primary_kw,
        )

        full = ""
        full_reasoning = ""
        async for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            if len(chunk.choices) == 0 or getattr(chunk.choices[0], "delta", None) is None:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                full_reasoning += reasoning
                yield {"type": "reasoning_token", "agent": agent["id"], "text": reasoning}
            piece = _delta_content_piece(delta)
            if piece:
                full += piece
                yield {"type": "token", "agent": agent["id"], "text": piece}

        raw = _strip_transcript_artifacts((full or "").strip())
        # Some NVIDIA / thinking routes stream visible speech only in reasoning_content; primary kwargs
        # disable extra_body but providers may still omit content — salvage from reasoning for display.
        if not raw and (full_reasoning or "").strip():
            raw = _strip_transcript_artifacts(full_reasoning.strip())

        full_trimmed = _normalize_spoken_line(raw, 3)
        if not full_trimmed.strip() or len(full_trimmed.strip()) < 12:
            alt = _salvage_quoted_speech(full) or _salvage_quoted_speech(full_reasoning or "")
            if alt:
                full_trimmed = _normalize_spoken_line(alt, 3)
        if _is_degenerate_repetitive_output(full_trimmed):
            q = _salvage_quoted_speech(full or "")
            if q and not _is_degenerate_repetitive_output(_normalize_spoken_line(q, 3)):
                full_trimmed = _normalize_spoken_line(q, 3)
            else:
                full_trimmed = ""
        if _is_degenerate_repetitive_output(full_trimmed):
            full_trimmed = ""
        if _looks_like_moderator_echo(full_trimmed):
            full_trimmed = ""
        # Last resort when content is empty but reasoning exists: short in-character salvage only.
        if not (full_trimmed or "").strip() and (full_reasoning or "").strip():
            fr = full_reasoning.strip()
            cand = _normalize_spoken_line(fr, 4).strip()
            if (
                cand
                and len(cand) >= 24
                and not _looks_like_moderator_echo(cand)
                and len(cand) <= 900
            ):
                full_trimmed = cand
        if last_primary_speech and _is_near_duplicate_primary(last_primary_speech, full_trimmed):
            full_trimmed = ""
        if (full_trimmed or "").strip():
            last_primary_speech = full_trimmed.strip()
        yield {
            "type": "agent_end",
            "agent": agent["id"],
            "turn": turn_index,
            "full_text": full_trimmed,
            "reasoning_text": full_reasoning or None,
        }
        transcript += f"\n\n[Turn {turn_index}][{agent['name']}]: {full_trimmed}\n"
        if effective_track and session_env is not None:
            session_env = apply_classic_utter(
                session_env,
                agent_id=agent["id"],
                text=full_trimmed,
                turn_ref=turn_index,
            )

        if enable_interjections and not _debate_deadline_elapsed(t0, debate_budget_sec):
            others = [a for a in AGENTS if a["id"] != agent["id"]]
            ij_kw = _short_interjection_kwargs(base_kw)
            raw_tail = transcript[-6000:] if len(transcript) > 6000 else transcript
            tail = _scrub_transcript_tail_for_prompt(raw_tail, max_chars=6000)

            async def _wrap_interj(
                other: dict[str, str],
                *,
                sp: dict[str, str] = agent,
                lt: str = full_trimmed,
                ti: int = turn_index,
            ) -> tuple[dict[str, str], str | None]:
                try:
                    t = await _interjection_reply(
                        client,
                        model=debate_model,
                        kw=ij_kw,
                        llm=llm,
                        context=context,
                        transcript_tail=tail,
                        speaker=sp,
                        last_text=lt,
                        other=other,
                        turn_index=ti,
                    )
                    return (other, t)
                except Exception:
                    return (other, None)

            ij_futs = [asyncio.create_task(_wrap_interj(o)) for o in others]
            for ij_fut in asyncio.as_completed(ij_futs):
                other, snippet = await ij_fut
                if not snippet:
                    continue
                yield {
                    "type": "interjection",
                    "agent": other["id"],
                    "name": other["name"],
                    "target_agent": agent["id"],
                    "target_name": agent["name"],
                    "turn": turn_index,
                    "text": snippet,
                }
                transcript += (
                    f"\n[Turn {turn_index}][{other['name']} interjects → {agent['name']}]: {snippet}\n"
                )
                if effective_track and session_env is not None:
                    session_env = apply_classic_interjection(
                        session_env,
                        agent_id=other["id"],
                        text=snippet,
                        turn_ref=turn_index,
                    )

    if effective_track and session_env is not None:
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
        session_deadline=t0 + total_sec,
    ):
        yield ev
