from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

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
    context = f"{retrieval.describe()} Ledger rules: {LedgerWriteTool.RULES}."
    last_move: str | None = None
    while True:
        if state.status == "running" and state.step_count >= state.max_steps:
            state.status = "failed"
            state.failure_reason = "step ceiling exhausted without completion"
            state.history.append("exhausted: step ceiling reached")
            return state
        terminal = route(state)
        if terminal.next_node == "terminal":
            if state.status == "running":
                state.status = "done"
            return state
        decision = decide(state, client, model, context=context)
        move = decision.action + ":" + json.dumps(decision.args, sort_keys=True)
        if move == last_move:
            state.status = "failed"
            state.failure_reason = "repeated ineffective action"
            state.history.append(f"repeated: {move}")
            return state
        last_move = move
        state.step_count += 1
        if decision.action == "finish":
            state.status = "done"
            state.history.append(f"finish: {decision.reason}")
            return state
        try:
            if decision.action == "retrieve":
                args = RetrievalArgs(**decision.args)
                state.history.append(retrieval.execute(state, args))
            elif decision.action == "ledger_write":
                args = LedgerArgs(**decision.args)
                out = guarded_ledger_write(state, ledger, args, queue)
                if out.startswith("rejected:"):
                    pass
                elif state.status == "awaiting_approval":
                    if not auto_approve:
                        return state
                    resume_after_approval(state, ledger, args, queue, out)
                else:
                    state.history.append(out)
            elif decision.action == "request_approval":
                state.status = "awaiting_approval"
                state.history.append(f"gated: {decision.reason}")
                return state
        except ValidationError as exc:
            # Bad arguments become history the model sees next iteration,
            # not a crash. The step ceiling bounds repeated failures.
            # Anything else still propagates.
            state.history.append(f"rejected: {exc.errors()[0]['msg']}")
        if state.status in ("done", "failed", "awaiting_approval"):
            return state
