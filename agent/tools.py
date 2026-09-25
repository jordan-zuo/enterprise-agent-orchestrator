from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from agent.states import AgentState

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> set[str]:
    """Alphanumeric tokens with naive plural folding (clauses -> clause)."""
    out: set[str] = set()
    for token in _TOKEN_RE.findall(text.lower()):
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        out.add(token)
    return out


class RetrievalArgs(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=1, ge=1, le=5)

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be blank")
        return cleaned


class LedgerArgs(BaseModel):
    entry_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(default="AUD", min_length=1)
    source_doc: str = Field(min_length=1)


class RetrievalTool:
    """Keyword retrieval over a small in-memory corpus.

    Stand-in for the hybrid engine call. Deterministic, no network.
    """

    name = "retrieve"

    def __init__(self, documents: dict[str, str]) -> None:
        self._documents = dict(documents)

    def execute(self, state: AgentState, args: RetrievalArgs) -> str:
        query_terms = _terms(args.query)

        def _score(text: str) -> int:
            return len(query_terms & _terms(text))

        ranked = sorted(self._documents.items(), key=lambda item: _score(item[1]), reverse=True)
        top = [(doc_id, text) for doc_id, text in ranked[: args.top_k] if _score(text) > 0]
        if not top:
            return f"retrieve [{args.query}]: no matching document"
        return f"retrieve [{args.query}]: " + ", ".join(doc_id for doc_id, _ in top)

    def as_tool_fn(self, args: RetrievalArgs):
        def _fn(state: AgentState) -> str:
            return self.execute(state, args)

        return _fn


class LedgerWriteTool:
    """Append-only ledger. Sensitive: run behind the approval gate."""

    name = "ledger_write"

    def __init__(self) -> None:
        self.entries: list[LedgerArgs] = []

    def execute(self, state: AgentState, args: LedgerArgs) -> str:
        self.entries.append(args)
        return f"ledger_write: {args.entry_id} {args.amount:.2f} {args.currency}"

    def as_tool_fn(self, args: LedgerArgs):
        def _fn(state: AgentState) -> str:
            return self.execute(state, args)

        return _fn
