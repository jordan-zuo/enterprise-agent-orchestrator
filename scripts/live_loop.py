"""Manual live end-to-end loop. NOT part of CI: needs LLM_API_KEY and network.

Runs the model-driven loop against real tools. Small ledger writes execute
at once; anything over the threshold pauses for your approval decision.

Usage (repo root):
    $env:LLM_API_KEY = "<key>"
    python scripts/live_loop.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.approvals import ApprovalQueue
from agent.driver import build_client
from agent.runner import run_with_model
from agent.states import AgentState
from agent.tools import LedgerWriteTool, RetrievalTool

DOCS = {
    "lease-7": "recovery clause submetered electricity one hundred percent recharge",
    "sopa-notes": "subcontractor statement required before progress payment release",
}


def main() -> None:
    model = os.environ.get("LLM_MODEL", "mistral-Nemo-Instruct-2407")
    client = build_client()
    queue = ApprovalQueue()
    ledger = LedgerWriteTool()
    state = run_with_model(
        AgentState(task="Reconcile the electricity bill against lease-7 and post it.", max_steps=6),
        client,
        model,
        RetrievalTool(DOCS),
        ledger,
        queue,
    )
    print(f"status={state.status} steps={state.step_count}")
    for event in state.history:
        print(f"  - {event}")
    for ticket in queue.pending():
        print(f"  ! pending approval: {ticket.ticket_id} ({ticket.detail})")


if __name__ == "__main__":
    main()
