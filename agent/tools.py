from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from agent.states import AgentState

_TOKEN_RE = re.compile(r"[a-z0-9]+")


_SYNONYMS = {
    "electricity": {"power", "energy"},
    "power": {"electricity", "energy"},
    "energy": {"electricity", "power"},
}


def _terms(text: str) -> set[str]:
    """Alphanumeric tokens with naive plural folding (clauses -> clause).

    Small synonym fan-out for the energy domain so a bill saying power
    still matches a query saying electricity and the reverse holds.
    """
    out: set[str] = set()
    for token in _TOKEN_RE.findall(text.lower()):
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        out.add(token)
    for token in list(out):
        if token in _SYNONYMS:
            out |= _SYNONYMS[token]
    return out


class RetrievalArgs(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=2, ge=1, le=5)

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
    Queries are plain words. There is no SQL, no database, no tables.
    Returns doc ids plus evidence snippets so amounts stay quotable.
    """

    name = "retrieve"

    def __init__(self, documents: dict[str, str]) -> None:
        self._documents = dict(documents)

    def describe(self) -> str:
        ids = ", ".join(sorted(self._documents))
        return f"keyword search over documents [{ids}]. Ask with plain words. Returns id plus text snippet with numbers."

    def _snippet(self, text: str, limit: int = 320) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        markers = (
            "amount due",
            "total due",
            "total bill",
            "total new charges",
            "total charges",
            "total credits",
            "total gst",
            "balance brought forward",
            "account number",
            "national metering",
        )
        low = cleaned.lower()
        hits: list[str] = []
        for marker in markers:
            idx = low.find(marker)
            if idx >= 0:
                start = max(0, idx - 40)
                hits.append(cleaned[start : idx + 120].strip())
                if sum(len(h) for h in hits) >= limit:
                    break
        if not hits:
            return cleaned[:limit]
        out = " ... ".join(hits)
        return out[:limit]

    def execute(self, state: AgentState, args: RetrievalArgs) -> str:
        query_terms = _terms(args.query)

        def _score(text: str) -> int:
            return len(query_terms & _terms(text))

        ranked = sorted(self._documents.items(), key=lambda item: _score(item[1]), reverse=True)
        top = [(doc_id, text) for doc_id, text in ranked[: args.top_k] if _score(text) > 0]
        if not top:
            return f"retrieve [{args.query}]: no matching document"
        parts = [f"{doc_id} | {self._snippet(text)}" for doc_id, text in top]
        return f"retrieve [{args.query}]: " + " || ".join(parts)

    def as_tool_fn(self, args: RetrievalArgs):
        def _fn(state: AgentState) -> str:
            return self.execute(state, args)

        return _fn


class LedgerWriteTool:
    """Append-only ledger. Sensitive: run behind the approval gate."""

    name = "ledger_write"

    RULES = (
        "amounts must be positive numbers (credits are unsupported); "
        "entry_id and source_doc are required; "
        "amounts over 10000 pause for human approval"
    )

    def __init__(self) -> None:
        self.entries: list[LedgerArgs] = []

    def execute(self, state: AgentState, args: LedgerArgs) -> str:
        self.entries.append(args)
        return f"ledger_write: {args.entry_id} {args.amount:.2f} {args.currency}"

    def as_tool_fn(self, args: LedgerArgs):
        def _fn(state: AgentState) -> str:
            return self.execute(state, args)

        return _fn
