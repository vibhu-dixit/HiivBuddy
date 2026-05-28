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
    user_visible_turn_line,
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


def test_user_visible_turn_line():
    r = SwarmTurnResponse(action="utter", text="We should ship the MVP first.")
    assert user_visible_turn_line(r, UtterAction(agent_id="a", text="We should ship the MVP first."))

    assert user_visible_turn_line(SwarmTurnResponse(action="pass"), PassAction(agent_id="a")) is None

    r_opt = SwarmTurnResponse(
        action="support_option", option_id="o0", delta=1.0, speech="option 1"
    )
    sup = swarm_response_to_agent_action(r_opt, "optimist")
    assert user_visible_turn_line(r_opt, sup) is None

    r_good = SwarmTurnResponse(
        action="support_option",
        option_id="o0",
        delta=1.0,
        speech="Option 1 fits our runway because we can validate demand in six weeks.",
    )
    sup2 = swarm_response_to_agent_action(r_good, "optimist")
    assert "runway" in (user_visible_turn_line(r_good, sup2) or "")
