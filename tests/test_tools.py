import pytest
from pydantic import ValidationError

from agent.states import AgentState
from agent.tools import LedgerArgs, LedgerWriteTool, RetrievalArgs, RetrievalTool

DOCS = {
    "q3-financials": "enterprise revenue was 48.2 million with margin 18.4 percent",
    "security-policy": "api keys must be rotated every 90 days with hardware mfa",
}


def test_retrieval_returns_top_doc() -> None:
    tool = RetrievalTool(DOCS)
    event = tool.execute(AgentState(task="t"), RetrievalArgs(query="api key rotation"))
    assert "security-policy" in event


def test_retrieval_folds_plurals() -> None:
    tool = RetrievalTool(DOCS)
    event = tool.execute(AgentState(task="t"), RetrievalArgs(query="keys rotated"))
    assert "security-policy" in event


def test_retrieval_splits_underscores_and_hyphens() -> None:
    tool = RetrievalTool(DOCS)
    event = tool.execute(AgentState(task="t"), RetrievalArgs(query="api_keys-rotated"))
    assert "security-policy" in event


def test_retrieval_no_match_says_so() -> None:
    tool = RetrievalTool(DOCS)
    event = tool.execute(AgentState(task="t"), RetrievalArgs(query="penguin migration"))
    assert event == "retrieve [penguin migration]: no matching document"


def test_retrieval_blank_query_rejected() -> None:
    with pytest.raises(ValidationError):
        RetrievalArgs(query="   ")


def test_ledger_appends_and_receipts() -> None:
    ledger = LedgerWriteTool()
    args = LedgerArgs(entry_id="j-001", amount=48.2, source_doc="q3-financials")
    event = ledger.execute(AgentState(task="t"), args)
    assert event == "ledger_write: j-001 48.20 AUD"
    assert len(ledger.entries) == 1


def test_ledger_rejects_bad_args() -> None:
    with pytest.raises(ValidationError):
        LedgerArgs(entry_id="", amount=-5, source_doc="")
