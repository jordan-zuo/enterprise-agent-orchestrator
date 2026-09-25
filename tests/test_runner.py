import pytest

from agent.approvals import ApprovalQueue
from agent.runner import run_with_model
from agent.states import AgentState
from agent.tools import LedgerWriteTool, RetrievalTool


class _ScriptedClient:
    """Replays canned decisions in order, then says finish."""

    def __init__(self, script: list[dict]) -> None:
        self._script = list(script)
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        if self._script:
            payload = self._script.pop(0)
        else:
            payload = {"action": "finish", "args": {}, "reason": "nothing left"}
        import json

        content = json.dumps(payload)
        return type(
            "Completion",
            (),
            {"choices": [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]},
        )()


DOCS = {"lease-7": "recovery clause submetered electricity one hundred percent"}


def test_model_run_completes_retrieve_then_finish() -> None:
    client = _ScriptedClient(
        [
            {"action": "retrieve", "args": {"query": "recovery clause"}, "reason": "find clause"},
            {"action": "finish", "args": {}, "reason": "have what is needed"},
        ]
    )
    state = run_with_model(
        AgentState(task="t", max_steps=5),
        client,
        "test",
        RetrievalTool(DOCS),
        LedgerWriteTool(),
        ApprovalQueue(),
    )
    assert state.status == "done"
    assert any("lease-7" in event for event in state.history)


def test_model_run_pauses_for_big_ledger_write() -> None:
    client = _ScriptedClient(
        [{"action": "ledger_write", "args": {"entry_id": "j-9", "amount": 99999, "source_doc": "d"}, "reason": "post"}]
    )
    state = run_with_model(
        AgentState(task="t", max_steps=5),
        client,
        "test",
        RetrievalTool(DOCS),
        LedgerWriteTool(),
        ApprovalQueue(),
    )
    assert state.status == "awaiting_approval"


def test_exhaustion_marks_failed_not_running() -> None:
    client = _ScriptedClient(
        [{"action": "retrieve", "args": {"query": "rent"}, "reason": "loop"}] * 10
    )
    state = run_with_model(
        AgentState(task="t", max_steps=3),
        client,
        "test",
        RetrievalTool(DOCS),
        LedgerWriteTool(),
        ApprovalQueue(),
    )
    assert state.status == "failed"
    assert "ceiling" in state.failure_reason
    assert state.history[-1].startswith("exhausted:")


def test_model_run_bad_args_become_feedback_not_crash() -> None:
    client = _ScriptedClient(
        [
            {"action": "ledger_write", "args": {"entry_id": "", "amount": -1}, "reason": "bad"},
            {"action": "finish", "args": {}, "reason": "giving up cleanly"},
        ]
    )
    state = run_with_model(
        AgentState(task="t", max_steps=5),
        client,
        "test",
        RetrievalTool(DOCS),
        LedgerWriteTool(),
        ApprovalQueue(),
    )
    assert state.status == "done"
    assert any(event.startswith("rejected:") for event in state.history)
