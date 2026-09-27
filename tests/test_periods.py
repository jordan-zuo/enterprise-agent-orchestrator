from agent.approvals import ApprovalQueue
from agent.ledger_flow import guarded_ledger_write
from agent.periods import evidence_months, period_compatible, task_markers
from agent.states import AgentState
from agent.tools import LedgerArgs, LedgerWriteTool


def test_christmas_maps_to_december() -> None:
    assert task_markers("agl bill for christmas") == {"dec"}


def test_quarter_expands_to_months() -> None:
    assert task_markers("q3 bill") == {"jul", "aug", "sep"}


def test_christmas_task_rejects_april_bill() -> None:
    ledger, queue = LedgerWriteTool(), ApprovalQueue()
    args = LedgerArgs(entry_id="agl-xmas", amount=63.70, source_doc="bill-agl-apr23")
    state = AgentState(
        task="agl bill for christmas",
        history=[
            "retrieve [bill]: bill-agl-apr23 | Amount due 63.70 dollars Due date 23 Apr 2023"
        ],
    )
    event = guarded_ledger_write(state, ledger, args, queue)
    assert event.startswith("rejected:")
    assert len(ledger.entries) == 0


def test_lease_task_allows_matching_quarter() -> None:
    ledger, queue = LedgerWriteTool(), ApprovalQueue()
    args = LedgerArgs(
        entry_id="lease-7-q3", amount=4049.18, source_doc="bill-q3-electricity"
    )
    state = AgentState(
        task="reconcile against lease-7",
        history=[
            "retrieve [bill]: bill-q3-electricity | Amount due 4049.18 dollars Bill period 1 July to 30 September",
            "retrieve [lease]: lease-7 | Tenant account 99881",
        ],
    )
    event = guarded_ledger_write(state, ledger, args, queue)
    assert event.startswith("ledger_write:")
    assert len(ledger.entries) == 1


def test_plain_task_has_no_period_constraint() -> None:
    ok, _ = period_compatible(
        "reconcile the bill", "Amount due 63.70 Due date 23 Apr 2023"
    )
    assert ok is True
    assert evidence_months("Due date 23 Apr 2023") == {"apr"}
