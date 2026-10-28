from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ApprovalTicket(BaseModel):
    ticket_id: str
    action: str
    detail: str
    decided: bool = False
    approved: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ApprovalQueue:
    """In-memory human-in-the-loop queue. Unknown tickets raise."""

    def __init__(self) -> None:
        self._tickets: dict[str, ApprovalTicket] = {}

    def submit(
        self,
        action: str,
        detail: str,
        meta: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> str:
        # Tickets must stay unique across runs because the store keys on
        # ticket_id globally. A per-queue counter would collide.
        ticket_id = f"t-{uuid.uuid4().hex[:12]}"
        self._tickets[ticket_id] = ApprovalTicket(
            ticket_id=ticket_id,
            action=action,
            detail=detail,
            meta=dict(meta or {}),
            evidence=dict(evidence or {}),
        )
        return ticket_id

    def decide(self, ticket_id: str, approved: bool) -> ApprovalTicket:
        try:
            ticket = self._tickets[ticket_id]
        except KeyError:
            raise KeyError(f"unknown approval ticket: {ticket_id}") from None
        ticket.decided = True
        ticket.approved = approved
        return ticket

    def pending(self) -> list[ApprovalTicket]:
        return [t for t in self._tickets.values() if not t.decided]
