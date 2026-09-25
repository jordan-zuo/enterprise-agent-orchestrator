import pytest

from agent.approvals import ApprovalQueue
from agent.guardrails import assess_ledger
from agent.ledger_flow import guarded_ledger_write, resume_after_approval
from agent.states import AgentState
from agent.tools import LedgerArgs, LedgerWriteTool


def _args(amount: float = 100.0) -> LedgerArgs:
    return LedgerArgs(entry_id="j-1", amount=amount, source_doc="q3")


def test_small_amount_executes_at_once() -> None:
    ledger, queue, state = LedgerWriteTool(), ApprovalQueue(), AgentState(task="t")
    event = guarded_ledger_write(state, ledger, _args(100.0), queue)
    assert event.startswith("ledger_write:")
    assert state.status == "pending"
    assert queue.pending() == []


def test_large_amount_gates_behind_ticket() -> None:
    ledger, queue, state = LedgerWriteTool(), ApprovalQueue(), AgentState(task="t")
    ticket_id = guarded_ledger_write(state, ledger, _args(50_000.0), queue)
    assert ticket_id.startswith("t-")
    assert state.status == "awaiting_approval"
    assert len(ledger.entries) == 0
    assert len(queue.pending()) == 1


def test_approval_resumes_and_writes() -> None:
    ledger, queue, state = LedgerWriteTool(), ApprovalQueue(), AgentState(task="t")
    ticket_id = guarded_ledger_write(state, ledger, _args(50_000.0), queue)
    event = resume_after_approval(state, ledger, _args(50_000.0), queue, ticket_id)
    assert event.startswith("ledger_write:")
    assert state.status == "done"
    assert len(ledger.entries) == 1


def test_unknown_ticket_raises() -> None:
    queue = ApprovalQueue()
    with pytest.raises(KeyError, match="unknown approval ticket"):
        queue.decide("t-9999", True)


def test_threshold_boundary() -> None:
    assert assess_ledger(_args(10_000.0)).needs_approval is False
    assert assess_ledger(_args(10_000.01)).needs_approval is True
