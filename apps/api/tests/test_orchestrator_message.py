from unittest.mock import MagicMock

from app.debate.orchestrator import _first_assistant_message


def test_first_assistant_message_none_choices():
    resp = MagicMock()
    resp.choices = None
    assert _first_assistant_message(resp) is None


def test_first_assistant_message_empty_choices():
    resp = MagicMock()
    resp.choices = []
    assert _first_assistant_message(resp) is None


def test_first_assistant_message_ok():
    msg = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    assert _first_assistant_message(resp) is msg
