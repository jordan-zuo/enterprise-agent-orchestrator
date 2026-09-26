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


def _history_text(history: list[str]) -> str:
    return "\n".join(history)


def is_quoted(amount: float, history: list[str]) -> bool:
    return f"{float(amount):.2f}" in _history_text(history)


def is_source_seen(source_doc: str, history: list[str]) -> bool:
    return source_doc in _history_text(history)


def assess_grounding(args: LedgerArgs, history: list[str]) -> tuple[bool, str]:
    if not is_source_seen(args.source_doc, history):
        return False, (
            f"source {args.source_doc} absent from history; "
            "retrieve it first and quote its total"
        )
    if not is_quoted(args.amount, history):
        return False, (
            f"amount {args.amount:.2f} absent from history; "
            "retrieve the bill first and quote its total instead of inventing"
        )
    return True, "grounded"
