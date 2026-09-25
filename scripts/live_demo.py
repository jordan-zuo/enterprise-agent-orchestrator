"""Manual live-model demo. NOT part of CI: needs LLM_API_KEY and network.

Usage (repo root, server not required):
    $env:LLM_API_KEY = "<key>"
    python scripts/live_demo.py
"""
from __future__ import annotations

import os
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
    model = os.environ.get("LLM_MODEL", "mistral-Nemo-Instruct-2407")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.llm7.io/v1")
    print(f"model={model} base={base_url} (key hidden)")
    client = build_client()
    state = AgentState(task="Reconcile the Q3 utility bill against the lease clauses.")
    decision = decide(state, client, model)
    print(f"action={decision.action} args={decision.args}")
    print(f"reason={decision.reason}")


if __name__ == "__main__":
    main()
