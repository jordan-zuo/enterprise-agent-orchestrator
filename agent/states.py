from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, PrivateAttr

# (kind, body, data) -> None. The runner calls this as each step happens so
# the API can persist and stream it immediately instead of batching.
EventSink = Callable[[str, str, dict[str, Any]], None]


class Evidence(BaseModel):
    """A retrieved passage. The only source that can justify a ledger amount.

    Kept separate from ``history`` because history also carries rejections,
    and rejection text must never become evidence for a retry.
    """

    doc_id: str
    text: str
    query: str = ""


class AgentState(BaseModel):
    task: str
    step_count: int = 0
    max_steps: int = 10
    history: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal[
        "pending", "running", "awaiting_approval", "done", "failed", "cancelled"
    ] = "pending"
    failure_reason: str = ""
    # A task that asks for a posting is not finished until one lands, or the
    # bill is confirmed as already posted.
    posted: bool = False
    settled: bool = False
    finish_nudged: bool = False

    _sink: EventSink | None = PrivateAttr(default=None)

    def stream_to(self, sink: EventSink | None) -> "AgentState":
        """Attach a live sink. Without one, ``log`` simply records history."""
        self._sink = sink
        return self

    def emit(self, kind: str, body: str, data: dict[str, Any] | None = None) -> None:
        """Push an event that is not part of the model-visible history."""
        if self._sink is not None:
            self._sink(kind, body, dict(data or {}))

    def log(
        self,
        body: str,
        kind: str = "step",
        data: dict[str, Any] | None = None,
    ) -> str:
        """Record a step once, in both the replay lane and the live lane.

        ``kind`` and ``data`` are decided here, at the source, so nothing
        downstream has to reverse-engineer a prefixed string.
        """
        self.history.append(body)
        if self._sink is not None:
            self._sink(kind, body, dict(data or {}))
        return body


class StepDecision(BaseModel):
    next_node: Literal["execute_tool", "await_approval", "terminal"]
    detail: str = ""
