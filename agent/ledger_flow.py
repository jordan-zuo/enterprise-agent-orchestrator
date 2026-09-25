from agent.approvals import ApprovalQueue
from agent.guardrails import assess_ledger
from agent.states import AgentState
from agent.tools import LedgerArgs, LedgerWriteTool


def guarded_ledger_write(
    state: AgentState,
    ledger: LedgerWriteTool,
    args: LedgerArgs,
    queue: ApprovalQueue,
) -> str:
    """Run the guardrail first. Small amounts execute at once.
    Large amounts pause behind a ticket and return the ticket id.
    """
    verdict = assess_ledger(args)
    if not verdict.needs_approval:
        return ledger.execute(state, args)
    ticket_id = queue.submit(action=ledger.name, detail=verdict.reason)
    state.status = "awaiting_approval"
    state.history.append(f"gated: {ticket_id} ({verdict.reason})")
    return ticket_id


def resume_after_approval(
    state: AgentState,
    ledger: LedgerWriteTool,
    args: LedgerArgs,
    queue: ApprovalQueue,
    ticket_id: str,
) -> str:
    ticket = queue.decide(ticket_id, True)
    if not ticket.approved:
        state.status = "failed"
        state.failure_reason = f"denied: {ticket_id}"
        return ticket_id
    event = ledger.execute(state, args)
    state.status = "done"
    return event
