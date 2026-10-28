"""A bill quotes many true numbers; only the payable one may be posted.

The failure these pin: "post the bill with the highest solar export" posted
114.87 for Jane's bill, which is that bill's total before a 35.00 payment.
114.87 is printed on the document, so the quote check passed, and nobody
owed 114.87.
"""

import pytest
from fastapi.testclient import TestClient

import scripts.api as api
from agent import store
from agent.approvals import ApprovalQueue
from agent.guardrails import assess_due_amount, stated_due_amount
from agent.ledger_flow import guarded_ledger_write
from agent.states import AgentState, Evidence
from agent.tools import LedgerArgs, LedgerWriteTool

JANE_BILL = (
    "Retailer electricity tax invoice. Account number 123456. "
    "Name Jane Citizen. Supply charge 31 days at 1.02 dollars per day "
    "totaling 31.62 dollars. Peak usage 515 kWh at 0.29 dollars per kWh "
    "totaling 149.35 dollars. GST 10 percent totaling 18.77 dollars. "
    "Solar exports feed-in tariff 463 kWh at 0.09 dollars per kWh "
    "totaling 41.67 dollars credit. Usage discount 15 percent totaling "
    "25.76 dollars credit. Government energy rebate totaling 24.20 "
    "dollars credit. Total bill 114.87 dollars, that is 114 dollars 87 "
    "cents. Payment received 15 March 2022 totaling 35.00 dollars credit. "
    "Total due 79.87 dollars, that is 79 dollars 87 cents. Due date "
    "27 April 2022."
)

ORIGIN_BILL = (
    "Account No: 900 000 000 000 Total\nAmount Due:\n$13,376.47\n"
    "Due Date*:\n05 Nov 15\nMR ALEX CARTER\n"
    "Total electricity charges (ind. discounts and rebates)\n$13,248.22\n"
    "Total amount due\n$13,376.47"
)


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB", str(tmp_path / "t.db"))
    store.init_db()
    return str(tmp_path / "t.db")


@pytest.mark.parametrize(
    "text, expected",
    [
        (JANE_BILL, 79.87),
        ("Amount due 63.70 dollars, that is 63 dollars 70 cents.", 63.70),
        ("Amount Due = $63.70", 63.70),
        ("Your amount due is\n$79.87\ndue on\n27 April 2022", 79.87),
        (ORIGIN_BILL, 13376.47),
        ("Amount due\nDue date\nAGL Sales Pty Ltd ABN 88 090 538 337", None),
        ("Solar export 463 kWh at 0.09 dollars per kWh", None),
    ],
)
def test_stated_due_amount_reads_the_payable_figure(text, expected) -> None:
    assert stated_due_amount(text) == expected


def _jane_args(amount: float) -> LedgerArgs:
    return LedgerArgs(
        entry_id="jane-mar22",
        amount=amount,
        source_doc="bill-retailer-mar22",
    )


def test_total_bill_is_not_the_amount_due() -> None:
    state = AgentState(
        task="post the person bill with the highest solar export",
        evidence=[Evidence(doc_id="bill-retailer-mar22", text=JANE_BILL)],
    )
    ledger, queue = LedgerWriteTool(), ApprovalQueue()

    out = guarded_ledger_write(state, ledger, _jane_args(114.87), queue)

    assert out.startswith("rejected:")
    assert "114.87 is not what is payable" in out
    assert "79.87 due" in out
    assert ledger.entries == []


def test_amount_due_posts() -> None:
    state = AgentState(
        task="post the person bill with the highest solar export",
        evidence=[Evidence(doc_id="bill-retailer-mar22", text=JANE_BILL)],
    )
    ledger, queue = LedgerWriteTool(), ApprovalQueue()

    out = guarded_ledger_write(state, ledger, _jane_args(79.87), queue)

    assert out == "ledger_write: bill-retailer-mar22 79.87 AUD"
    assert len(ledger.entries) == 1


def test_origin_amount_due_still_matches() -> None:
    args = LedgerArgs(
        entry_id="alex-bill",
        amount=13376.47,
        source_doc="origin-standing-bill-modified-alexcarter",
    )
    evidence = [
        Evidence(
            doc_id="origin-standing-bill-modified-alexcarter", text=ORIGIN_BILL
        )
    ]
    assert assess_due_amount(args, evidence) == (
        True,
        "matches the 13376.47 the document says is due",
    )


def test_document_without_a_payable_figure_falls_back_to_the_quote() -> None:
    args = LedgerArgs(entry_id="j-1", amount=10.0, source_doc="note")
    evidence = [Evidence(doc_id="note", text="Amount owing is unclear this month.")]
    ok, reason = assess_due_amount(args, evidence)
    assert ok is True
    assert "no stated amount due" in reason


def test_approval_cannot_bypass_the_amount_due_check(isolated_db) -> None:
    """The human gate re-validates, so an approval cannot wave through 114.87."""
    run_id = store.create_run("jane")
    store.submit_approval(
        "t-amount",
        run_id,
        "ledger_write",
        "amount exceeds approval threshold",
        {
            "entry_id": "jane-mar22",
            "amount": 114.87,
            "currency": "AUD",
            "source_doc": "bill-retailer-mar22",
        },
        evidence={
            "task": "post the highest solar export bill",
            "citations": [{"doc_id": "bill-retailer-mar22", "text": JANE_BILL}],
            "checks": {},
        },
    )
    client = TestClient(api.app)

    res = client.post("/approvals/t-amount/decide", json={"approved": True})

    assert res.status_code == 422
    assert "79.87" in res.json()["detail"]
    assert store.list_ledger() == []
