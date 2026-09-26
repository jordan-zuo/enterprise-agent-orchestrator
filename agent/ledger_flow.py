from agent.approvals import ApprovalQueue
from agent.bill_math import verify_ledger_math
from agent.guardrails import assess_grounding, assess_ledger
from agent.states import AgentState
from agent.tools import LedgerArgs, LedgerWriteTool


def guarded_ledger_write(
    state: AgentState,
    ledger: LedgerWriteTool,
    args: LedgerArgs,
    queue: ApprovalQueue,
) -> str:
    """Run grounding and math first, then the money gate.

    Unquoted amounts and math mismatches become visible rejections
    the model sees next step. Small amounts execute at once.
    Large amounts pause behind a ticket and return the ticket id.
    """
    ok, reason = assess_grounding(args, list(state.history))
    if not ok:
        state.history.append(f"rejected: {reason}")
        return f"rejected: {reason}"
    math_ok, math_reason = verify_ledger_math(args)
    if not math_ok:
        state.history.append(f"rejected: {math_reason}")
        return f"rejected: {math_reason}"
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
    state.history.append(event)
    state.status = "done"
    return event
