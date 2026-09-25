from __future__ import annotations

from pydantic import BaseModel

from agent.tools import LedgerArgs

APPROVAL_THRESHOLD = 10_000.0


class GuardrailVerdict(BaseModel):
    allowed: bool
    needs_approval: bool
    reason: str


def assess_ledger(args: LedgerArgs) -> GuardrailVerdict:
    if args.amount > APPROVAL_THRESHOLD:
        return GuardrailVerdict(
            allowed=True,
            needs_approval=True,
            reason=f"amount {args.amount:.2f} exceeds approval threshold {APPROVAL_THRESHOLD:.2f}",
        )
    return GuardrailVerdict(allowed=True, needs_approval=False, reason="within policy")
