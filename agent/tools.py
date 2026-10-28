from __future__ import annotations

import re
from typing import Callable

from pydantic import BaseModel, Field, field_validator

from agent.states import AgentState, Evidence

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A bill posting exists to quote this figure, so its window is selected ahead
# of keyword hits and cannot be pushed out by the document header.
_DUE_FIGURE_RE = re.compile(
    r"(?:total\s+amount\s+due|amount\s+due|total\s+due|balance\s+due|amount\s+payable)"
    r"[^0-9$]{0,30}?(\$\s*)?([0-9][0-9,]*(?:\.[0-9]{2})?)",
    re.IGNORECASE,
)


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
    top_k: int = Field(default=4, ge=1, le=20)

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

    def _snippet(self, text: str, query: str = "", limit: int = 700) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned

        low = cleaned.lower()
        raw_query = query.lower().strip()

        words = [w for w in re.findall(r"[a-z0-9]+", raw_query) if len(w) > 1]
        numbers = [w for w in words if any(c.isdigit() for c in w)]
        non_numbers = [w for w in words if not any(c.isdigit() for c in w)]

        matches: list[tuple[int, int, int, int, int]] = []
        for i in range(len(words) - 1):
            shingle = f"{words[i]} {words[i+1]}"
            for m in re.finditer(re.escape(shingle), low):
                matches.append((m.start(), m.end(), 12, 40, 90))

        for num in numbers:
            for m in re.finditer(rf"\b{re.escape(num)}\b", low):
                matches.append((m.start(), m.end(), 10, 40, 90))

        for w in non_numbers:
            if w in {"and", "the", "for", "which", "has", "had", "bill", "due", "kwh", "with", "also", "their"}:
                continue
            for m in re.finditer(rf"\b{re.escape(w)}", low):
                matches.append((m.start(), m.end(), 6, 40, 90))

        for anchor in ("account number", "name", "customer", "tenant"):
            for m in re.finditer(rf"\b{re.escape(anchor)}\b", low):
                matches.append((m.start(), m.end(), 15, 30, 100))

        for anchor in ("amount due", "total due", "total bill"):
            for m in re.finditer(re.escape(anchor), low):
                matches.append((m.start(), m.end(), 7, 30, 90))

        for m in _DUE_FIGURE_RE.finditer(cleaned):
            sign, number = m.group(1), m.group(2)
            if not (sign or "." in number):
                continue
            matches.append((m.start(), m.end(), 20, 30, 110))

        if not matches:
            for marker in ("amount due", "total due", "total bill", "total new charges", "account number"):
                idx = low.find(marker)
                if idx >= 0:
                    matches.append((idx, idx + len(marker), 1, 30, 90))

        if not matches:
            return cleaned[:limit]

        raw_intervals: list[tuple[int, int, int]] = []
        for start, end, priority, pad_before, pad_after in matches:
            w_start = max(0, start - pad_before)
            w_end = min(len(cleaned), end + pad_after)
            raw_intervals.append((w_start, w_end, priority))
        raw_intervals.sort(key=lambda x: x[0])

        merged_intervals: list[tuple[int, int, int]] = []
        for s, e, priority in raw_intervals:
            merged = False
            for i, (ms, me, mp) in enumerate(merged_intervals):
                if not (e < ms - 20 or s > me + 20):
                    merged_intervals[i] = (min(ms, s), max(me, e), max(mp, priority))
                    merged = True
                    break
            if not merged:
                merged_intervals.append((s, e, priority))

        merged_intervals.sort(key=lambda x: x[0])

        chosen: list[tuple[int, int]] = []
        cur_len = 0
        for s, e, priority in sorted(merged_intervals, key=lambda x: (-x[2], x[0])):
            span_len = e - s
            if cur_len + span_len <= limit:
                chosen.append((s, e))
                cur_len += span_len
            elif limit - cur_len > 60:
                chosen.append((s, s + (limit - cur_len)))
                cur_len = limit
            if cur_len >= limit - 30:
                break

        chosen.sort(key=lambda x: x[0])

        if not chosen and merged_intervals:
            s, e = merged_intervals[0]
            chosen = [(s, min(len(cleaned), s + limit))]

        snippets = [cleaned[s:e].strip() for s, e in chosen]
        return " ... ".join(snippets)

    def execute(self, state: AgentState, args: RetrievalArgs) -> str:
        query_terms = _terms(args.query)

        def _score(text: str) -> float:
            low = text.lower()
            doc_terms = _terms(text)
            matched = query_terms & doc_terms
            if not matched:
                return 0.0
            score = float(len(matched) * 10)
            raw_q = args.query.lower().strip()
            if raw_q in low:
                score += 15.0
            for term in query_terms:
                score += min(low.count(term), 5)
            return score

        ranked = sorted(self._documents.items(), key=lambda item: _score(item[1]), reverse=True)
        top = [(doc_id, text) for doc_id, text in ranked[: args.top_k] if _score(text) > 0]
        if not top:
            return f"retrieve [{args.query}]: no matching document"
        parts = []
        for doc_id, text in top:
            # Evidence records the document's own text, not the formatted
            # history line. Grounding checks this lane only.
            state.evidence.append(Evidence(doc_id=doc_id, text=text, query=args.query))
            parts.append(f"{doc_id} | {self._snippet(text, query=args.query)}")
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
        "amounts over 10000 pause for human approval; "
        "a document already posted cannot be posted again"
    )

    def __init__(self, posted: Callable[[LedgerArgs], dict | None] | None = None) -> None:
        self.entries: list[LedgerArgs] = []
        # Injected by the service so the orchestrator can refuse a re-post
        # before a human is ever asked to approve one.
        self._posted = posted

    def already_posted(self, args: LedgerArgs) -> dict | None:
        if self._posted is None:
            return None
        return self._posted(args)

    def execute(self, state: AgentState, args: LedgerArgs) -> str:
        self.entries.append(args)
        return f"ledger_write: {args.source_doc} {args.amount:.2f} {args.currency}"

    def as_tool_fn(self, args: LedgerArgs):
        def _fn(state: AgentState) -> str:
            return self.execute(state, args)

        return _fn
