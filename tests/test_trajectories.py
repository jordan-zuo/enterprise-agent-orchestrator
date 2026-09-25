import pytest

from agent.graph import run
from agent.states import AgentState


def _ok_tool(state: AgentState) -> str:
    if state.step_count >= 2:
        state.status = "done"
        return "task complete"
    return f"step {state.step_count + 1} done"


def _stubborn_tool(state: AgentState) -> str:
    # Never finishes on its own. The step ceiling must stop it.
    return "no progress"


def _boom_tool(state: AgentState) -> str:
    raise RuntimeError("tool exploded")


def test_happy_path_terminates_done() -> None:
    final = run(AgentState(task="demo", max_steps=10), _ok_tool)
    assert final.status == "done"
    assert final.step_count == 3


def test_stubborn_tool_hits_ceiling_not_infinity() -> None:
    final = run(AgentState(task="demo", max_steps=5), _stubborn_tool)
    assert final.status == "done"
    assert final.step_count == 5
    assert len(final.history) == 5


def test_tool_errors_raise_loudly() -> None:
    with pytest.raises(RuntimeError, match="tool exploded"):
        run(AgentState(task="demo"), _boom_tool)


def test_approval_gate_pauses() -> None:
    final = run(AgentState(task="demo"), _ok_tool, needs_approval=True)
    assert final.status == "awaiting_approval"
    assert final.step_count == 0
