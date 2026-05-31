"""Derive per-advisor votes from debate environment (support/attack history + persona)."""

from __future__ import annotations

import re
from collections import defaultdict

from app.debate.environment import DebateEnvironment

# Default advisor ids — keep aligned with orchestrator.AGENTS
DEFAULT_AGENT_IDS: tuple[str, ...] = (
    "optimist",
    "devils_advocate",
    "data_analyst",
    "risk_guru",
    "ethical_guardian",
)

_SUPPORT_RE = re.compile(r"^support:(?P<oid>[^:]+):\+(?P<delta>[\d.]+)$")
_ATTACK_RE = re.compile(r"^attack:(?P<oid>[^:]+):-(?P<delta>[\d.]+)$")
_OPTION_MENTION_RE = re.compile(
    r"\boption\s*(?P<id>\d+)\b|\b(?:option|path)\s*(?P<id2>\d+)\b",
    re.IGNORECASE,
)


def net_option_scores_for_agent(
    env: DebateEnvironment,
    agent_id: str,
    allowed: set[str],
) -> dict[str, float]:
    """Cumulative support (+) and attack (-) deltas per option from the action log."""
    scores: dict[str, float] = defaultdict(float)
    for entry in env.action_log:
        if entry.agent_id != agent_id:
            continue
        summary = (entry.payload_summary or "").strip()
        m = _SUPPORT_RE.match(summary)
        if m:
            oid = m.group("oid")
            if oid in allowed:
                scores[oid] += float(m.group("delta"))
            continue
        m = _ATTACK_RE.match(summary)
        if m:
            oid = m.group("oid")
            if oid in allowed:
                scores[oid] -= float(m.group("delta"))
    return dict(scores)


def _infer_option_from_utterances(
    env: DebateEnvironment,
    agent_id: str,
    allowed: set[str],
) -> str | None:
    """Parse explicit option mentions from this agent's spoken lines."""
    mentions: dict[str, int] = defaultdict(int)
    for u in env.utterances:
        if u.agent_id != agent_id:
            continue
        text = u.text.lower()
        for m in _OPTION_MENTION_RE.finditer(text):
            oid = (m.group("id") or m.group("id2") or "").strip()
            if oid in allowed:
                mentions[oid] += 1
        for oid in allowed:
            title = env.options_by_id.get(oid)
            if not title:
                continue
            # Short title fragments (first two words) for fuzzy match
            frag = " ".join(title.title.lower().split()[:3])
            if len(frag) >= 8 and frag in text:
                mentions[oid] += 1
    if not mentions:
        return None
    return max(mentions.keys(), key=lambda k: mentions[k])


def _panel_pick(env: DebateEnvironment, allowed: set[str], fallback: str) -> str:
    if env.option_support_scores:
        return max(
            allowed,
            key=lambda k: float(env.option_support_scores.get(k, 0.5)),
        )
    return fallback


def _lowest_panel_option(env: DebateEnvironment, allowed: set[str], *, exclude: str | None) -> str:
    candidates = [o for o in allowed if o != exclude] or list(allowed)
    return min(candidates, key=lambda k: float(env.option_support_scores.get(k, 0.5)))


def _title_match_option(env: DebateEnvironment, allowed: set[str], *keywords: str) -> str | None:
    for oid in sorted(allowed, key=lambda x: int(x) if x.isdigit() else 99):
        title = env.options_by_id.get(oid)
        if not title:
            continue
        lower = title.title.lower()
        if all(kw in lower for kw in keywords):
            return oid
    return None


def pick_agent_vote_option(
    env: DebateEnvironment,
    agent_id: str,
    allowed: set[str],
    *,
    panel_pick: str,
) -> str:
    """
    Each advisor gets an individual vote from their support/attack record, speech, or persona.
    Devil's Advocate is nudged toward dissent when their history shows attacks on the consensus.
    """
    net = net_option_scores_for_agent(env, agent_id, allowed)

    if net:
        best_score = max(net.values())
        leaders = [oid for oid, s in net.items() if s == best_score]
        pick = leaders[0] if len(leaders) == 1 else min(leaders, key=lambda x: int(x) if x.isdigit() else 99)

        if agent_id == "devils_advocate" and pick == panel_pick:
            attacks_on_panel = 0
            for e in env.action_log:
                if e.agent_id != agent_id:
                    continue
                m = _ATTACK_RE.match((e.payload_summary or "").strip())
                if m and m.group("oid") == panel_pick:
                    attacks_on_panel += 1
            if attacks_on_panel > 0:
                dissent = {k: v for k, v in net.items() if k != panel_pick}
                if dissent:
                    alt_score = max(dissent.values())
                    alt_leaders = [k for k, v in dissent.items() if v == alt_score]
                    pick = alt_leaders[0]
                else:
                    pick = _lowest_panel_option(env, allowed, exclude=panel_pick)

        return pick

    inferred = _infer_option_from_utterances(env, agent_id, allowed)
    if inferred is not None:
        if agent_id == "devils_advocate" and inferred == panel_pick:
            return _lowest_panel_option(env, allowed, exclude=panel_pick)
        return inferred

    if agent_id == "devils_advocate":
        return _lowest_panel_option(env, allowed, exclude=panel_pick)
    if agent_id == "risk_guru":
        conservative = _title_match_option(env, allowed, "runway")
        if conservative:
            return conservative
    if agent_id == "optimist":
        return panel_pick

    st = env.agent_state_by_id.get(agent_id)
    if st and st.focus_option_id in allowed:
        return st.focus_option_id

    return panel_pick


def vote_rationale_for_agent(
    env: DebateEnvironment,
    agent_id: str,
    option_id: str,
) -> str:
    opt = env.options_by_id.get(option_id)
    label = opt.title if opt else f"option {option_id}"
    for u in reversed(env.utterances):
        if u.agent_id == agent_id and u.text.strip():
            snippet = u.text.strip()
            if len(snippet) > 140:
                snippet = snippet[:137] + "…"
            return f"{label}: {snippet}"
    return f"Vote for {label}."
