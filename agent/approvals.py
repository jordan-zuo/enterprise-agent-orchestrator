from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApprovalTicket(BaseModel):
    ticket_id: str
    action: str
    detail: str
    decided: bool = False
    approved: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class ApprovalQueue:
    """In-memory human-in-the-loop queue. Unknown tickets raise."""

    def __init__(self) -> None:
        self._tickets: dict[str, ApprovalTicket] = {}
        self._counter = 0

    def submit(
        self, action: str, detail: str, meta: dict[str, Any] | None = None
    ) -> str:
        self._counter += 1
        ticket_id = f"t-{self._counter:04d}"
        self._tickets[ticket_id] = ApprovalTicket(
            ticket_id=ticket_id,
            action=action,
            detail=detail,
            meta=dict(meta or {}),
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
