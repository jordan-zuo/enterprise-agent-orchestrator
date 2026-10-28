"""Manual live-model demo. NOT part of CI: needs provider keys and network.

Usage (repo root, server not required):
    python scripts/live_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.driver import build_client, decide
from agent.states import AgentState

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main() -> None:
    client = build_client()
    labels = [spec.label for spec in client.specs]
    print(f"agent pool={', '.join(labels)} (key hidden)")
    state = AgentState(task="Reconcile the Q3 utility bill against the lease clauses.")
    decision = decide(state, client, "auto")
    print(f"answered by={client.last_label}")
    print(f"action={decision.action} args={decision.args}")
    print(f"reason={decision.reason}")


if __name__ == "__main__":
    main()
