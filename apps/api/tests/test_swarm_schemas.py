import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from app.debate.environment import PassAction, UtterAction
from app.debate.swarm_schemas import (
    SwarmTurnResponse,
    parse_swarm_turn_response,
    swarm_response_to_agent_action,
    transcript_line_for_turn,
)


def test_parse_utter():
    r = parse_swarm_turn_response('{"action":"utter","text":"Hello world"}')
    assert r.action == "utter"
    a = swarm_response_to_agent_action(r, "optimist")
    assert isinstance(a, UtterAction)
    assert a.text == "Hello world"


def test_parse_action_type_alias():
    r = parse_swarm_turn_response('{"action_type":"pass"}')
    assert r.action == "pass"


def test_invalid_then_raises():
    with pytest.raises(ValueError):
        parse_swarm_turn_response("not json")


def test_transcript_line():
    r = SwarmTurnResponse(action="utter", text="Hi")
    u = UtterAction(agent_id="a", text="Hi")
    assert transcript_line_for_turn(r, u) == "Hi"

    r2 = SwarmTurnResponse(action="pass")
    assert transcript_line_for_turn(r2, PassAction(agent_id="a")) == "(pass)"
