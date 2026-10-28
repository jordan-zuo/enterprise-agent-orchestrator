"""Manual live end-to-end loop. NOT part of CI: needs provider keys and network.

Runs the model-driven loop against real tools. Small ledger writes execute
at once; anything over the threshold pauses for your approval decision.

Usage (repo root):
    python scripts/live_loop.py
"""
from __future__ import annotations

import json
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
    client = build_client()
    labels = [spec.label for spec in client.specs]
    print(f"agent pool={', '.join(labels)} (key hidden)")
    model = "auto"
    queue = ApprovalQueue()
    ledger = LedgerWriteTool()
    state = run_with_model(
        AgentState(task="Reconcile the Origin standing bill and post its total amount due.", max_steps=6),
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
