from __future__ import annotations

from agent.tools import LedgerArgs

ELECTRICITY_BILL_TOTAL = 4049.18
ELECTRICITY_PARTS = {
    "peak_kwh": 12480,
    "peak_rate": 0.25,
    "peak_total": 3120.0,
    "offpeak_kwh": 3200,
    "offpeak_rate": 0.15,
    "offpeak_total": 480.0,
    "supply_days": 92,
    "supply_rate": 0.98,
    "supply_total": 90.16,
    "subtotal": 3690.16,
    "gst": 369.02,
    "solar_credit": 10.0,
    "total": 4049.18,
}
_TOL = 0.01


def recompute_electricity_bill() -> dict[str, float]:
    parts = dict(ELECTRICITY_PARTS)
    subtotal = parts["peak_total"] + parts["offpeak_total"] + parts["supply_total"]
    total = subtotal + parts["gst"] - parts["solar_credit"]
    return {"subtotal": round(subtotal, 2), "total": round(total, 2)}


def verify_electricity_bill(amount: float, tol: float = _TOL) -> bool:
    return abs(float(amount) - ELECTRICITY_BILL_TOTAL) <= tol


def _targets_lease7(entry_id: str) -> bool:
    norm = "".join(ch for ch in entry_id.lower() if ch.isalnum())
    return "lease7" in norm


def verify_ledger_math(args: LedgerArgs) -> tuple[bool, str]:
    if _targets_lease7(args.entry_id):
        if args.source_doc != "bill-q3-electricity":
            return (
                False,
                f"entry {args.entry_id} targets lease-7 account 99881 "
                f"but source {args.source_doc} does not carry it; "
                "retrieve the bill for lot 7 Sample Street account 99881",
            )
        if verify_electricity_bill(args.amount):
            return True, "math matches recomputed total"
        return (
            False,
            f"amount {args.amount:.2f} does not match recomputed bill total "
            f"{ELECTRICITY_BILL_TOTAL:.2f}",
        )
    if args.source_doc == "bill-q3-electricity":
        if verify_electricity_bill(args.amount):
            return True, "math matches recomputed total"
        return (
            False,
            f"amount {args.amount:.2f} does not match recomputed bill total "
            f"{ELECTRICITY_BILL_TOTAL:.2f}",
        )
    return True, "no known math for source; grounding only"
