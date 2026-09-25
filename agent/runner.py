from __future__ import annotations

from typing import Any

from agent.approvals import ApprovalQueue
from agent.driver import decide
from agent.ledger_flow import guarded_ledger_write, resume_after_approval
from agent.router import route
from agent.states import AgentState
from agent.tools import LedgerArgs, LedgerWriteTool, RetrievalArgs, RetrievalTool


def run_with_model(
    state: AgentState,
    client: Any,
    model: str,
    retrieval: RetrievalTool,
    ledger: LedgerWriteTool,
    queue: ApprovalQueue,
    auto_approve: bool = False,
) -> AgentState:
    """Model proposes, graph disposes. Ceiling and gates always enforced."""
    state.status = "running"
    while True:
        terminal = route(state)
        if terminal.next_node == "terminal":
            if state.status == "running":
                state.status = "done"
            return state
        decision = decide(state, client, model)
        state.step_count += 1
        if decision.action == "finish":
            state.status = "done"
            state.history.append(f"finish: {decision.reason}")
            return state
        if decision.action == "retrieve":
            args = RetrievalArgs(**decision.args)
            state.history.append(retrieval.execute(state, args))
        elif decision.action == "ledger_write":
            args = LedgerArgs(**decision.args)
            out = guarded_ledger_write(state, ledger, args, queue)
            if state.status == "awaiting_approval":
                if not auto_approve:
                    return state
                resume_after_approval(state, ledger, args, queue, out)
        elif decision.action == "request_approval":
            state.status = "awaiting_approval"
            state.history.append(f"gated: {decision.reason}")
            return state
        if state.step_count >= state.max_steps:
            return state
