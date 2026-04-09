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

from app.debate.environment import DebateEnvironment, EnvLimits
from app.debate.environment_adapter import (
    apply_classic_interjection,
    apply_classic_utter,
    apply_vote_supports,
    merge_vote_options,
)
from app.debate.environment_ops import init_environment, snapshot_for_api
from app.debate.schemas import (
    AgentStanceItem,
    AgentVoteResponse,
    ClosingPhaseResponse,
    ClosingVoteItem,
    FinalReport,
    RankedOption,
    SYNTH_API_TIMEOUT_SEC,
    SYNTH_RESERVE_SEC,
    VoteOptionItem,
    VoteOptionsResponse,
)
from app.llm.client import Settings
from app.llm.messages import prepare_chat_messages

logger = logging.getLogger(__name__)


def _debate_environment_seed(context: str, explicit: int | None) -> int:
    if explicit is not None:
        return int(explicit) & 0x7FFFFFFF
    digest = hashlib.sha256(context.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _synth_raw_from_assistant_message(msg: Any) -> str:
    """NVIDIA thinking models often return empty `content` and put JSON in `reasoning_content`."""
    c = msg.content
    if isinstance(c, str) and c.strip():
        return c.strip()
    r = getattr(msg, "reasoning_content", None)
    if isinstance(r, str) and r.strip():
        return r.strip()
    return "{}"


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

SYNTH_SYSTEM = """You are the Chief Synthesizer for HiivBuddy.
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
    " Interjection: output ONLY 1–2 sentences you would say aloud—one short paragraph, no title. "
    "Forbidden: 'We need to respond as', 'Let's reconstruct', 'The user', role instructions, or quoting the prompt. "
    "If nothing to add, output exactly PASS alone."
)

# Primary turns: models (esp. with chain-of-thought) often paraphrase the user prompt or plan aloud.
PRIMARY_DEBATE_SYSTEM_ADDENDUM = (
    " You are speaking aloud at a conference table, not writing an essay or a rubric. "
    "Output ONLY what you would say in one breath: at most three sentences, no bullets. "
    "Do not plan, outline, or say what you will argue. Do not quote or restate the moderator instructions. "
    "Do not preface with meta like 'We need to', 'I'll pick', 'Probably', 'Given that', or 'As [role], we could'. "
    "Start directly with your substance; if you address another advisor, use their role name naturally (e.g. 'Optimist, …')."
)


def _interjection_content_only(msg: Any) -> str:
    """Interjections must never use reasoning/thinking channels — only public speech."""
    c = getattr(msg, "content", None)
    if isinstance(c, str) and c.strip():
        return c.strip()
    return ""


def _paragraph_is_instruction_leak(p: str) -> bool:
    """Drop model meta about the prompt (common with chain-of-thought in content)."""
    pl = p.lower()
    if "act as" in pl and "advisor" in pl:
        return True
    leaks = (
        "the user wants",
        "the user asked",
        "user wants me",
        "keep it to at most",
        "two short sentences",
        "avoid repeating their",
        "something material or correct",
        "only add something",
        "given the instructions",
        "as an ai",
        "as a language model",
        "the user request",
        "user request:",
        "you are the optimist",
        "you are the devil's advocate",
        "you are the data analyst",
        "you are the risk guru",
        "you are the ethical guardian",
        "highlight upside, opportunities",
        "challenge assumptions",
    )
    return any(s in pl for s in leaks)


def _paragraph_is_planning_meta(p: str) -> bool:
    """Heuristic: rubric / planning / prompt echo — not spoken dialogue."""
    pl = p.lower().strip()
    if not pl:
        return False
    if _paragraph_is_instruction_leak(p):
        return True
    needles = (
        "we are we",
        "we need to pick",
        "we need to respond",
        "we need to respond as",
        "we need to choose",
        "we need to decide",
        "we need to speak",
        "respond as ",
        "to respond as ",
        "pick a participant",
        "don't have optimist",
        "don't have devil's",
        "don't have ethical",
        "no optimist's actual",
        "infer they'd",
        "infer they would",
        "as they'd be speaking",
        "speaking now (turn",
        "presumably would argue",
        "we could respond to",
        "we'll disagree",
        "we'll agree",
        "probably optimist",
        "probably the optimist",
        "probably devil's",
        "let's consider context:",
        "let's reconstruct",
        "initial context:",
        "that's one sentence",
        "that's two sentence",
        "make sure no bullet",
        "above is how",
        "thus, we could say",
        "thus we could say",
        "so we could say:",
        "consider:",
        "do we agree, disagree",
        "we should speak only",
        "otherwise pass",
        "as dialogue only",
        "reply with exactly pass",
        "reply with exactly",
        "interjects →",
        "for some reason they",
        "they echoed",
        "weird placeholder",
        "data analyst might add",
        "[turn ",
        "actually turn ",
    )
    return any(n in pl for n in needles)


def _strip_transcript_artifacts(text: str) -> str:
    """Remove pasted transcript markers some models echo into content."""
    t = text or ""
    t = re.sub(r"\[Turn\s*\d+\]\s*\[[^\]\n]{1,120}\]:\s*", "", t, flags=re.IGNORECASE)
    return t.strip()


def _salvage_quoted_speech(text: str) -> str | None:
    """Use longest quoted span that looks like real table speech, not rubric."""
    best: str | None = None
    for m in re.finditer(r'"([^"]{18,800})"', text or "", re.DOTALL):
        inner = " ".join(m.group(1).strip().split())
        if not inner or _text_still_meta_ridden(inner) or _paragraph_is_planning_meta(inner):
            continue
        if best is None or len(inner) > len(best):
            best = inner
    return best


def _text_still_meta_ridden(text: str) -> bool:
    """True if stripped text is still mostly rubric (drop interjection)."""
    low = (text or "").lower().strip()
    if not low:
        return True
    hard = (
        "we need to respond as",
        "we are we",
        "the user request",
        "you are the optimist",
        "let's reconstruct",
        "initial context:",
        "[turn ",
    )
    return any(h in low for h in hard)


def _strip_primary_speech_meta(text: str) -> str:
    """Drop rubric / planning paragraphs anywhere in main debate turns."""
    t = _strip_transcript_artifacts((text or "").strip())
    if not t:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n+", t) if p.strip()]
    if not paras:
        paras = [t]
    kept = [
        p
        for p in paras
        if not _paragraph_is_planning_meta(p) and not _paragraph_is_instruction_leak(p)
    ]
    out = "\n\n".join(kept).strip()
    if not out:
        out = _strip_interjection_meta(t)
    if not out:
        return ""
    lines = out.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if _paragraph_is_planning_meta(line) and len(line) < 500:
            i += 1
            continue
        break
    return "\n".join(lines[i:]).strip() or out


def _strip_interjection_meta(text: str) -> str:
    """Remove rubric / planning paragraphs and leading junk from interjections."""
    t = _strip_transcript_artifacts((text or "").strip())
    if not t:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n+", t) if p.strip()]
    kept = [
        p
        for p in paras
        if not _paragraph_is_instruction_leak(p) and not _paragraph_is_planning_meta(p)
    ]
    out = "\n\n".join(kept).strip()
    if not out:
        return ""
    lines = out.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        low = line.lower()
        if line.startswith(("Okay,", "Ok,", "Well,", "So,")) and any(
            x in low for x in ("user wants", "user asked", "need to", "should", "instructions", "act as")
        ):
            i += 1
            continue
        if _paragraph_is_instruction_leak(line) and len(line) < 400:
            i += 1
            continue
        if _paragraph_is_planning_meta(line) and len(line) < 500:
            i += 1
            continue
        break
    return "\n".join(lines[i:]).strip()


def _short_interjection_kwargs(base_kw: dict[str, Any]) -> dict[str, Any]:
    """Smaller completions; drop thinking extras so interjections stay quick and on-format."""
    out = dict(base_kw)
    cap = min(220, int(out.get("max_tokens", 16384)))
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
    tail = (transcript_tail or "").strip().replace("\r\n", "\n")
    if len(tail) > 4500:
        tail = "…\n" + tail[-4500:].lstrip()
    last_s = (last_text or "").strip()
    if len(last_s) > 1200:
        last_s = last_s[:1197].rstrip() + "…"
    user = (
        f"Situation:\n{ctx_short}\n\n"
        f"Thread:\n{tail}\n\n"
        f"{speaker['name']} (just now): {last_s}\n\n"
        f"You are {other['name']}. In ≤2 spoken sentences, correct or add one fact—or first line only: PASS. "
        f"No meta. No 'we need to respond as'. Do not repeat {speaker['name']}."
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
        raw = _interjection_content_only(resp.choices[0].message)
    except Exception:
        return None
    if not raw or _is_pass_interjection(raw):
        return None
    cleaned = _clean_interjection(raw)
    cleaned = _strip_interjection_meta(cleaned)
    if _text_still_meta_ridden(cleaned):
        alt = _salvage_quoted_speech(raw)
        if alt:
            cleaned = _trim_to_max_sentences(alt, 2)
    if not cleaned or re.match(r"^(PASS|NO\s*INTERRUPTION)\b", cleaned, re.I):
        return None
    if _paragraph_is_instruction_leak(cleaned) or _text_still_meta_ridden(cleaned):
        return None
    return cleaned


DEBATE_OUTPUT_RULES = (
    "\n\nOutput: at most three sentences of in-character speech. No bullet lists. "
    "Speak only as your role—no meta-commentary, no describing your plan, no references to instructions or 'the user'."
)


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
    if turn_index <= 1:
        return (
            "This is your first turn in this timed session. Give your initial stance in at most three sentences. "
            "State what you lean toward and the main reason, in character."
            + DEBATE_OUTPUT_RULES
        )
    if turn_index <= 5:
        return (
            "Read the debate so far. In at most three sentences, respond to at least one other participant BY NAME "
            "(e.g. Optimist, Devil's Advocate). Agree, disagree, or refine one point with a concrete reason."
            + DEBATE_OUTPUT_RULES
        )
    if turn_index % 5 == 0:
        return (
            "In at most three sentences, state your bottom-line recommendation and what evidence would change your mind."
            + DEBATE_OUTPUT_RULES
        )
    return (
        "In at most three sentences, build on prior turns; respond to others by name; stress-test one main argument."
        + DEBATE_OUTPUT_RULES
    )


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
) -> AsyncIterator[dict[str, Any]]:
    """Vote extraction, tally, Chief Synthesizer — shared by classic and structured swarm."""
    threshold = max(1, min(5, consensus_threshold))
    base_kw = llm.common_completion_kwargs()
    se = session_env_box[0]

    yield {"type": "vote_phase_start"}

    closing_user = (
        f"Decision context:\n{context}\n\nFull debate transcript:\n{transcript}\n"
        "Return JSON only matching the system schema (options, votes, agent_stances)."
    )
    parsed_closing: ClosingPhaseResponse | None = None
    try:
        closing_msgs = prepare_chat_messages(
            [
                {"role": "system", "content": CLOSING_SYSTEM},
                {"role": "user", "content": closing_user},
            ],
            model,
            llm,
        )
        closing_resp = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=closing_msgs,
            **_completion_kw_for_messages(base_kw, closing_msgs, llm, 4096),
        )
        closing_raw = _synth_raw_from_assistant_message(closing_resp.choices[0].message)
        parsed_closing = _parse_json_to_model(closing_raw, ClosingPhaseResponse)
    except Exception:
        parsed_closing = None

    if parsed_closing is None:
        opts_user = (
            f"Decision context:\n{context}\n\nFull debate transcript:\n{transcript}\n"
            'Return JSON only with shape {"options":[{"id":"0","title":"..."},...]} (2-4 options).'
        )
        opt_msgs = prepare_chat_messages(
            [
                {"role": "system", "content": OPTIONS_FALLBACK_SYSTEM},
                {"role": "user", "content": opts_user},
            ],
            model,
            llm,
        )
        opt_resp = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=opt_msgs,
            **_completion_kw_for_messages(base_kw, opt_msgs, llm, 4096),
        )
        opt_raw = _synth_raw_from_assistant_message(opt_resp.choices[0].message)
        vote_opts_fb = _normalize_vote_options(_parse_json_to_model(opt_raw, VoteOptionsResponse))
        allowed_ids_fb = {o.id for o in vote_opts_fb}
        opts_lines = "\n".join(f"  id={o.id}: {o.title}" for o in vote_opts_fb)

        async def _one_vote(agent: dict[str, str]) -> ClosingVoteItem:
            vote_user = (
                f"Decision context:\n{context}\n\nDebate summary is in the transcript you do not need to repeat.\n"
                f"Voting options:\n{opts_lines}\n\n"
                f"You are {agent['name']}. Vote for exactly ONE option by its id (0, 1, 2, …). "
                "Return JSON only: "
                '{"option_id":"<id as string>","rationale":"<one short sentence>"}'
            )
            vote_msgs = prepare_chat_messages(
                [
                    {"role": "system", "content": agent["system"]},
                    {"role": "user", "content": vote_user},
                ],
                model,
                llm,
            )
            vresp = await client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=vote_msgs,
                **_completion_kw_for_messages(base_kw, vote_msgs, llm, 4096),
            )
            vraw = _synth_raw_from_assistant_message(vresp.choices[0].message)
            vparsed = _parse_json_to_model(vraw, AgentVoteResponse)
            assert isinstance(vparsed, AgentVoteResponse)
            oid = (vparsed.option_id or "").strip()
            if oid not in allowed_ids_fb:
                try:
                    cand = str(int(float(oid)))
                    if cand in allowed_ids_fb:
                        oid = cand
                    else:
                        oid = min(allowed_ids_fb, key=lambda x: int(x))
                except (ValueError, TypeError):
                    oid = min(allowed_ids_fb, key=lambda x: int(x))
            return ClosingVoteItem(
                agent_id=agent["id"],
                option_id=oid,
                rationale=(vparsed.rationale or "")[:300],
            )

        vote_items = await asyncio.gather(*[_one_vote(a) for a in AGENTS])
        default_stances = [
            AgentStanceItem(agent_id=a["id"], lean="unknown", confidence=0.0, note="")
            for a in AGENTS
        ]
        parsed_closing = ClosingPhaseResponse(
            options=vote_opts_fb,
            votes=list(vote_items),
            agent_stances=default_stances,
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
        model,
        llm,
    )
    synth_kw = _completion_kw_for_messages(base_kw, synth_msgs, llm, 4096)

    win_title = id_to_title.get(winning_option_id or "", "Options")
    base_ranked = [
        RankedOption(
            title=win_title,
            score=0.5,
            rationale="Fallback while the full report was unavailable.",
        )
    ]

    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=synth_msgs,
                **synth_kw,
            ),
            timeout=float(SYNTH_API_TIMEOUT_SEC),
        )
    except asyncio.TimeoutError:
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
            msg = resp.choices[0].message
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

    yield {
        "type": "session_start",
        "session_duration_sec": total_sec,
        "debate_budget_sec": debate_budget_sec,
        "synth_reserve_sec": SYNTH_RESERVE_SEC,
    }

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
    while not _debate_deadline_elapsed(t0, debate_budget_sec):
        agent = rotation_order[rr % n_agents]
        rr += 1
        turn_index += 1
        yield {
            "type": "agent_start",
            "agent": agent["id"],
            "name": agent["name"],
            "turn": turn_index,
        }

        user_content = f"Decision context:\n{context}\n\n"
        if transcript.strip():
            user_content += f"Debate so far:\n{transcript}\n"
        user_content += _timed_debate_user_block(turn_index)

        stream = await client.chat.completions.create(
            model=model,
            stream=True,
            messages=prepare_chat_messages(
                [
                    {
                        "role": "system",
                        "content": f"{agent['system']}{PRIMARY_DEBATE_SYSTEM_ADDENDUM}",
                    },
                    {"role": "user", "content": user_content},
                ],
                model,
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
            if getattr(delta, "content", None) is not None:
                piece = delta.content or ""
                full += piece
                yield {"type": "token", "agent": agent["id"], "text": piece}

        cleaned = _strip_primary_speech_meta(full)
        full_trimmed = _trim_to_max_sentences(cleaned, 3)
        if _text_still_meta_ridden(full_trimmed) or len(full_trimmed.strip()) < 12:
            alt = _salvage_quoted_speech(full)
            if alt:
                full_trimmed = _trim_to_max_sentences(alt, 3)
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
            tail = transcript[-6000:] if len(transcript) > 6000 else transcript

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
                        model=model,
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
    ):
        yield ev
