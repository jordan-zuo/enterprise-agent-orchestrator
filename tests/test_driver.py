import pytest

from agent.driver import ModelDecision, decide
from agent.states import AgentState


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **kwargs) -> _FakeCompletion:
        assert kwargs["temperature"] == 0
        assert kwargs["max_tokens"] == 200
        return _FakeCompletion(self._content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(content)})()


def test_valid_decision_parses() -> None:
    client = _FakeClient('{"action": "retrieve", "args": {"query": "rent"}, "reason": "need clause"}')
    decision = decide(AgentState(task="t"), client, "test-model")
    assert decision == ModelDecision(action="retrieve", args={"query": "rent"}, reason="need clause")


def test_non_json_raises() -> None:
    with pytest.raises(ValueError, match="did not return JSON"):
        decide(AgentState(task="t"), _FakeClient("just do things"), "test-model")


def test_unknown_action_raises() -> None:
    with pytest.raises(ValueError, match="unknown action"):
        decide(AgentState(task="t"), _FakeClient('{"action": "teleport"}'), "test-model")
