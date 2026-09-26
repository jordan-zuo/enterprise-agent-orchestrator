"""Manual live end-to-end loop. NOT part of CI: needs LLM_API_KEY and network.

Runs the model-driven loop against real tools. Small ledger writes execute
at once; anything over the threshold pauses for your approval decision.

Usage (repo root):
    $env:LLM_API_KEY = "<key>"
    python scripts/live_loop.py
"""
from __future__ import annotations

import json
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

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

DOCS = json.load(open(ROOT / "data" / "corpus.json", encoding="utf-8"))


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()
    model = os.environ.get("LLM_MODEL", "mistral-Nemo-Instruct-2407")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.llm7.io/v1")
    print(f"model={model} base={base_url} (key hidden)")
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
        if event.startswith("retrieve ["):
            head, _, rest = event.partition(": ")
            print(f"  - {head}:")
            for chunk in rest.split(" || "):
                print(f"      * {chunk[:280]}")
        else:
            print(f"  - {event}")
    for ticket in queue.pending():
        print(f"  ! pending approval: {ticket.ticket_id} ({ticket.detail})")


if __name__ == "__main__":
    main()
