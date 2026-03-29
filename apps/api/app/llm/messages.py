"""OpenAI-compatible chat message shaping (some models reject role=system)."""

from typing import Any

from app.llm.client import Settings


def merge_system_into_user(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Concatenate system prompt(s) into the first user message; drop system role."""
    systems: list[str] = []
    rest: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "system":
            c = m.get("content")
            if isinstance(c, str) and c.strip():
                systems.append(c.strip())
        else:
            rest.append(m)
    if not systems:
        return messages
    prefix = "\n\n".join(systems)
    if rest and rest[0].get("role") == "user":
        first = dict(rest[0])
        uc = first.get("content", "")
        if not isinstance(uc, str):
            uc = str(uc)
        first["content"] = f"{prefix}\n\n---\n\n{uc}"
        return [first] + rest[1:]
    return [{"role": "user", "content": prefix}] + rest


def model_prefers_merged_system(model_id: str) -> bool:
    """Heuristic: models that commonly error with 'System role not supported' on some gateways."""
    m = (model_id or "").lower()
    return "gemma" in m or m.startswith("google/") or "/gemma" in m


def should_merge_system(llm: Settings, model_id: str) -> bool:
    if llm.llm_merge_system_into_user is not None:
        return bool(llm.llm_merge_system_into_user)
    return model_prefers_merged_system(model_id)


def prepare_chat_messages(
    messages: list[dict[str, Any]],
    model_id: str,
    llm: Settings,
) -> list[dict[str, Any]]:
    if should_merge_system(llm, model_id):
        return merge_system_into_user(messages)
    return messages
