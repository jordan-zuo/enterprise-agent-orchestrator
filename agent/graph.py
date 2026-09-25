from __future__ import annotations

from collections.abc import Callable

from agent.router import TERMINAL_STATES, route
from agent.states import AgentState

# A tool receives the state and returns an event string for the history log.
# It raises on failure. The graph never swallows tool errors silently.
ToolFn = Callable[[AgentState], str]


def run(state: AgentState, tool: ToolFn, needs_approval: bool = False) -> AgentState:
    state.status = "running"
    while True:
        decision = route(state, needs_approval=needs_approval)
        if decision.next_node == "terminal":
            if state.status == "running":
                state.status = "done"
            return state
        if decision.next_node == "await_approval":
            state.status = "awaiting_approval"
            state.history.append("gated: awaiting approval")
            return state
        # execute_tool: let tool exceptions propagate (fail-loud).
        event = tool(state)
        state.step_count += 1
        state.history.append(event)
        if state.status in TERMINAL_STATES:
            return state
