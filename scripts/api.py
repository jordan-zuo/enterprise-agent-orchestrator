"""HTTP service over the deterministic runner. SQLite backed.

Run records persist with replayable events. Ledger stays append only.
Approvals pause large writes behind tickets and resume on decision.

Usage (repo root):
    uvicorn scripts.api:app --port 8000
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import store  # noqa: E402
from agent.approvals import ApprovalQueue  # noqa: E402
from agent.bill_math import verify_ledger_math  # noqa: E402
from agent.guardrails import assess_grounding  # noqa: E402
from agent.runner import run_with_model  # noqa: E402
from agent.states import AgentState  # noqa: E402
from agent.tools import LedgerArgs, LedgerWriteTool, RetrievalTool  # noqa: E402

app = FastAPI(title="enterprise-agent-orchestrator")

TEST_CLIENT: Any = None


class RunRequest(BaseModel):
    task: str = Field(min_length=1)
    max_steps: int = Field(default=6, ge=1, le=20)


class DecideRequest(BaseModel):
    approved: bool


def _client() -> Any:
    if TEST_CLIENT is not None:
        return TEST_CLIENT
    from agent.driver import build_client

    return build_client()


def _model() -> str:
    return os.environ.get("LLM_MODEL", "mistral-Nemo-Instruct-2407")


def _docs() -> dict[str, str]:
    return json.loads((ROOT / "data" / "corpus.json").read_text(encoding="utf-8"))


def _kind(event: str) -> str:
    for prefix in (
        "retrieve",
        "ledger_write",
        "rejected",
        "gated",
        "finish",
        "exhausted",
        "repeated",
        "denied",
    ):
        if event.startswith(prefix):
            return prefix
    return "note"


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/")
def index() -> dict[str, Any]:
    return {
        "service": "enterprise-agent-orchestrator",
        "docs": "/docs",
        "health": "/health",
        "ledger": "/ledger",
        "approvals": "/approvals",
    }


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/ledger")
def ledger() -> dict[str, Any]:
    store.init_db()
    return {"entries": store.list_ledger()}


@app.get("/storage")
def storage() -> dict[str, Any]:
    path = store.init_db()
    counts = store.table_counts()
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "tables": counts,
    }


@app.get("/approvals")
def approvals() -> dict[str, Any]:
    store.init_db()
    return {"pending": store.list_pending_approvals()}


@app.post("/run")
def create_run(req: RunRequest) -> dict[str, Any]:
    store.init_db()
    run_id = store.create_run(req.task)
    retrieval = RetrievalTool(_docs())
    ledger = LedgerWriteTool()
    queue: ApprovalQueue = ApprovalQueue()
    state = run_with_model(
        AgentState(task=req.task, max_steps=req.max_steps),
        _client(),
        _model(),
        retrieval,
        ledger,
        queue,
    )
    for event in state.history:
        store.append_event(run_id, _kind(event), event)
    for entry in ledger.entries:
        store.insert_ledger_entry(
            run_id, entry.entry_id, entry.amount, entry.currency, entry.source_doc
        )
    for ticket in queue.pending():
        store.submit_approval(
            ticket.ticket_id,
            run_id,
            ticket.action,
            ticket.detail,
            ticket.meta,
        )
    store.set_run_status(run_id, state.status, state.step_count)
    return {
        "run_id": run_id,
        "status": state.status,
        "steps": state.step_count,
        "history": state.history,
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    store.init_db()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    return {"run": run, "events": store.get_events(run_id)}


@app.get("/runs/{run_id}/stream")
def stream_run(run_id: str) -> StreamingResponse:
    store.init_db()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    events = store.get_events(run_id)

    def _gen() -> Any:
        for item in events:
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.post("/approvals/{ticket_id}/decide")
def decide(ticket_id: str, req: DecideRequest) -> dict[str, Any]:
    store.init_db()
    ticket = store.decide_approval(ticket_id, req.approved)
    if ticket is None:
        raise HTTPException(status_code=404, detail="unknown approval ticket")
    run_id = ticket["run_id"]
    events = store.get_events(run_id)
    history = [e["body"] for e in events]
    if not req.approved:
        store.append_event(run_id, "denied", f"denied: {ticket_id}")
        run = store.get_run(run_id) or {}
        store.set_run_status(run_id, "failed", int(run.get("step_count", 0)))
        return {"ticket_id": ticket_id, "approved": False, "status": "failed"}
    meta = ticket.get("meta") or {}
    try:
        args = LedgerArgs(
            entry_id=str(meta.get("entry_id", "")),
            amount=float(meta.get("amount", 0)),
            currency=str(meta.get("currency", "AUD")),
            source_doc=str(meta.get("source_doc", "")),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"stored args invalid: {exc}")
    ok, reason = assess_grounding(args, history)
    if not ok:
        raise HTTPException(status_code=422, detail=reason)
    math_ok, math_reason = verify_ledger_math(args)
    if not math_ok:
        raise HTTPException(status_code=422, detail=math_reason)
    receipt = f"ledger_write: {args.entry_id} {args.amount:.2f} {args.currency}"
    store.insert_ledger_entry(
        run_id, args.entry_id, args.amount, args.currency, args.source_doc
    )
    store.append_event(run_id, "ledger_write", receipt)
    run = store.get_run(run_id) or {}
    store.set_run_status(run_id, "done", int(run.get("step_count", 0)))
    return {
        "ticket_id": ticket_id,
        "approved": True,
        "status": "done",
        "receipt": receipt,
    }
