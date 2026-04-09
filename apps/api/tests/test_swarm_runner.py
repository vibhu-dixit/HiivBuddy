import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.debate.swarm_runner import run_swarm_session_stream


def _msg(content: str, reasoning: str | None = None) -> MagicMock:
    m = MagicMock()
    m.content = content
    m.reasoning_content = reasoning
    return m


def _resp(content: str) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock(message=_msg(content))]
    return r


CLOSING_JSON = json.dumps(
    {
        "options": [
            {"id": "0", "title": "Option A"},
            {"id": "1", "title": "Option B"},
        ],
        "votes": [
            {"agent_id": "optimist", "option_id": "0", "rationale": "r"},
            {"agent_id": "devils_advocate", "option_id": "0", "rationale": "r"},
            {"agent_id": "data_analyst", "option_id": "0", "rationale": "r"},
            {"agent_id": "risk_guru", "option_id": "0", "rationale": "r"},
            {"agent_id": "ethical_guardian", "option_id": "0", "rationale": "r"},
        ],
        "agent_stances": [
            {"agent_id": "optimist", "lean": "l", "confidence": 0.5, "note": ""},
            {"agent_id": "devils_advocate", "lean": "l", "confidence": 0.5, "note": ""},
            {"agent_id": "data_analyst", "lean": "l", "confidence": 0.5, "note": ""},
            {"agent_id": "risk_guru", "lean": "l", "confidence": 0.5, "note": ""},
            {"agent_id": "ethical_guardian", "lean": "l", "confidence": 0.5, "note": ""},
        ],
    },
)

SYNTH_JSON = json.dumps(
    {
        "summary": "Test summary.",
        "ranked_options": [
            {"title": "Option A", "score": 0.7, "rationale": "votes"},
        ],
        "risks": ["r1"],
        "next_steps": ["n1"],
    },
)


class _FakeLLM:
    llm_merge_system_into_user: bool | None = False
    llm_context_tokens: int = 8192

    def common_completion_kwargs(self) -> dict:
        return {"temperature": 0.5, "max_tokens": 1024}


def test_swarm_runner_one_utter_then_post_debate(monkeypatch):
    _mono_seq = [0.0, 0.0, 0.5, 1000.0]
    _mi = 0

    def fake_monotonic() -> float:
        nonlocal _mi
        if _mi < len(_mono_seq):
            v = _mono_seq[_mi]
            _mi += 1
            return v
        return 1_000_000.0

    monkeypatch.setattr("app.debate.swarm_runner.time.monotonic", fake_monotonic)

    calls: list[str] = []

    async def fake_create(**kwargs: object) -> MagicMock:
        messages = kwargs.get("messages") or []
        user = next(
            (m.get("content", "") for m in messages if m.get("role") == "user"),
            "",
        )
        if "Return your JSON decision now" in str(user):
            calls.append("swarm_turn")
            return _resp('{"action":"utter","text":"One test utterance."}')
        if "Return JSON only matching the system schema" in str(user):
            calls.append("closing")
            return _resp(CLOSING_JSON)
        if "Produce the final JSON report object now" in str(user):
            calls.append("synth")
            return _resp(SYNTH_JSON)
        calls.append("other")
        return _resp("{}")

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=fake_create)

    async def collect() -> list[dict]:
        events: list[dict] = []
        async for ev in run_swarm_session_stream(
            client,
            context="hello world xx",
            model="test-model",
            llm=_FakeLLM(),
            session_duration_sec=60,
            synth_env_snapshot=False,
            environment_rng_seed=42,
        ):
            events.append(ev)
        return events

    events = asyncio.run(collect())

    assert "swarm_turn" in calls
    assert "closing" in calls
    assert "synth" in calls
    types = [e["type"] for e in events]
    assert types[0] == "session_start"
    assert "agent_end" in types
    assert "vote_tally" in types
    assert events[-1]["type"] == "final_report"
