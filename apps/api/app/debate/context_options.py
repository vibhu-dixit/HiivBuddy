"""Parse decision options from user context for swarm environment seeding."""

from __future__ import annotations

import re

from app.debate.environment import DebateEnvironment, DebateOption
from app.debate.environment_ops import merge_options

_OPTION_SECTION_RE = re.compile(
    r"^\s*(?:options?\s+we\s+are\s+weighing|options?|choices?|alternatives?)\s*:?\s*$",
    re.IGNORECASE,
)
_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)[\)\.]\s+(.+?)\s*$")
_STOP_SECTION_RE = re.compile(
    r"^\s*(?:constraints?|a good outcome|next steps|background|requirements?)\b",
    re.IGNORECASE,
)

_MAX_OPTION_TITLE = 200


def _clean_title(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw.strip())
    if len(t) > _MAX_OPTION_TITLE:
        t = t[: _MAX_OPTION_TITLE - 1].rstrip() + "…"
    return t


def _collect_numbered_block(lines: list[str], start: int) -> list[tuple[int, str]]:
    collected: list[tuple[int, str]] = []
    for line in lines[start:]:
        if not line.strip():
            if collected:
                break
            continue
        if _STOP_SECTION_RE.match(line):
            break
        m = _NUMBERED_LINE_RE.match(line)
        if not m:
            if collected:
                break
            continue
        num = int(m.group(1))
        title = _clean_title(m.group(2))
        if title:
            collected.append((num, title))
    return collected


def parse_options_from_context(context: str, *, max_options: int = 4) -> list[DebateOption]:
    """
    Extract 2–4 numbered decision options from free-form context text.
    Returns empty list if fewer than two options are found.
    """
    if not (context or "").strip():
        return []

    lines = context.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start_at = 0
    for i, line in enumerate(lines):
        if _OPTION_SECTION_RE.match(line):
            start_at = i + 1
            break

    block = _collect_numbered_block(lines, start_at)
    if len(block) < 2:
        block = _collect_numbered_block(lines, 0)

    if len(block) < 2:
        return []

    block.sort(key=lambda x: x[0])
    seen_titles: set[str] = set()
    out: list[DebateOption] = []
    for _num, title in block:
        if len(out) >= max_options:
            break
        key = title.casefold()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(DebateOption(id=str(len(out)), title=title))
    return out if len(out) >= 2 else []


def seed_environment_options_from_context(
    env: DebateEnvironment,
    context_text: str,
) -> DebateEnvironment:
    """Register parsed options so swarm support/attack/propose_claim actions validate during debate."""
    opts = parse_options_from_context(context_text)
    if len(opts) < 2:
        return env
    return merge_options(env, opts)
