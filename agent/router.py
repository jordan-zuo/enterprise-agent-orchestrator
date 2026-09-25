from __future__ import annotations

from agent.states import AgentState, StepDecision

TERMINAL_STATES = ("done", "failed")


def route(state: AgentState, needs_approval: bool = False) -> StepDecision:
    """Pure routing function. No I/O, no model calls, fully unit-testable."""
    if state.status in TERMINAL_STATES:
        return StepDecision(next_node="terminal", detail=f"already {state.status}")
    if state.step_count >= state.max_steps:
        return StepDecision(
            next_node="terminal",
            detail=f"step ceiling reached ({state.step_count}/{state.max_steps})",
        )
    if needs_approval:
        return StepDecision(next_node="await_approval", detail="sensitive operation gated")
    return StepDecision(next_node="execute_tool", detail="proceed")
