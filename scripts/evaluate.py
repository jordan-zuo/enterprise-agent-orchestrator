"""Scenario eval suite. Deterministic, dependency-free.

Each scenario in scenarios/suite.json declares its tool behavior and the
expected outcome. The suite runs every scenario, scores completion,
trajectory efficiency, and gating accuracy, and writes eval/results.json.

Usage (repo root):
    python scripts/evaluate.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.approvals import ApprovalQueue  # noqa: E402
from agent.graph import run  # noqa: E402
from agent.ledger_flow import guarded_ledger_write, resume_after_approval  # noqa: E402
from agent.states import AgentState  # noqa: E402
from agent.tools import LedgerArgs, LedgerWriteTool  # noqa: E402

SUITE_PATH = ROOT / "scenarios" / "suite.json"
RESULTS_PATH = ROOT / "eval" / "results.json"

COMPLETE_EVENT = "TASK_COMPLETE"


def _completing_tool(steps_needed: int):
    def _fn(state: AgentState) -> str:
        if state.step_count + 1 >= steps_needed:
            state.status = "done"
            return COMPLETE_EVENT
        return f"progress {state.step_count + 1}/{steps_needed}"

    return _fn


def _stubborn_tool(state: AgentState) -> str:
    return "no progress"


def _run_completion(case: dict) -> dict:
    state = AgentState(task=case["id"], max_steps=case.get("max_steps", 10))
    start = time.perf_counter()
    if case["kind"] == "stubborn":
        final = run(state, _stubborn_tool)
    else:
        final = run(state, _completing_tool(case["steps_needed"]))
    latency_ms = (time.perf_counter() - start) * 1000
    completed = COMPLETE_EVENT in final.history
    efficiency = (case.get("optimal_steps", 0) / final.step_count) if completed and final.step_count else 0.0
    passed = completed == case["expected_done"]
    return {
        "id": case["id"],
        "kind": case["kind"],
        "passed": passed,
        "completed": completed,
        "steps": final.step_count,
        "efficiency": round(efficiency, 4),
        "latency_ms": round(latency_ms, 2),
    }


def _run_ledger(case: dict) -> dict:
    ledger, queue = LedgerWriteTool(), ApprovalQueue()
    state = AgentState(task=case["id"])
    args = LedgerArgs(entry_id=case["entry_id"], amount=case["amount"], source_doc="eval")
    state.history.append(f"retrieve [seed]: eval | total {args.amount:.2f}")
    out = guarded_ledger_write(state, ledger, args, queue)
    if state.status == "awaiting_approval":
        if case.get("approve", False):
            out = resume_after_approval(state, ledger, args, queue, out)
        else:
            state.status = "failed"
            state.failure_reason = "denied by eval policy"
    gated = any(line.startswith("gated:") for line in state.history)
    passed = (gated == case["expected_gated"]) and (state.status == case["expected_status"])
    return {
        "id": case["id"],
        "kind": case["kind"],
        "passed": passed,
        "gated": gated,
        "status": state.status,
        "entries": len(ledger.entries),
    }


def _run_bad_args(case: dict) -> dict:
    try:
        LedgerArgs(
            entry_id=case.get("entry_id", ""),
            amount=case.get("amount", -1),
            source_doc="",
        )
        return {"id": case["id"], "kind": case["kind"], "passed": False, "raised": False}
    except Exception as exc:
        return {"id": case["id"], "kind": case["kind"], "passed": True, "raised": type(exc).__name__}


def _run_grounding(case: dict) -> dict:
    ledger, queue = LedgerWriteTool(), ApprovalQueue()
    state = AgentState(task=case["id"])
    args = LedgerArgs(
        entry_id=case["entry_id"],
        amount=case["amount"],
        source_doc=case.get("source_doc", "q3"),
    )
    if case.get("seed", False):
        state.history.append(
            f"retrieve [seed]: {args.source_doc} | total {args.amount:.2f}"
        )
    out = guarded_ledger_write(state, ledger, args, queue)
    allowed = out.startswith("ledger_write:") or out.startswith("t-")
    passed = allowed == case["expected_allowed"]
    return {
        "id": case["id"],
        "kind": case["kind"],
        "passed": passed,
        "allowed": allowed,
        "entries": len(ledger.entries),
    }


def _run_math(case: dict) -> dict:
    ledger, queue = LedgerWriteTool(), ApprovalQueue()
    bill_text = (
        "retrieve [bill]: bill-q3-electricity | Amount due 4049.18 dollars, "
        "that is 4049 dollars 18 cents"
    )
    state = AgentState(task=case["id"], history=[bill_text])
    args = LedgerArgs(
        entry_id=case["entry_id"],
        amount=case["amount"],
        source_doc="bill-q3-electricity",
    )
    if abs(float(case["amount"]) - 4049.18) > 0.01:
        state.history.append(
            f"retrieve [guess]: bill-q3-electricity | total {float(case['amount']):.2f}"
        )
    out = guarded_ledger_write(state, ledger, args, queue)
    allowed = out.startswith("ledger_write:") or out.startswith("t-")
    passed = allowed == case["expected_allowed"]
    return {
        "id": case["id"],
        "kind": case["kind"],
        "passed": passed,
        "allowed": allowed,
        "entries": len(ledger.entries),
    }


def main() -> dict:
    cases = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    results: list[dict] = []
    for case in cases:
        kind = case["kind"]
        if kind in ("complete", "stubborn"):
            results.append(_run_completion(case))
        elif kind == "ledger":
            results.append(_run_ledger(case))
        elif kind == "grounding":
            results.append(_run_grounding(case))
        elif kind == "math":
            results.append(_run_math(case))
        elif kind == "bad_args":
            results.append(_run_bad_args(case))
        else:
            raise ValueError(f"unknown scenario kind: {kind}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    completion_cases = [r for r in results if r["kind"] in ("complete", "stubborn")]
    completed = [r for r in completion_cases if r.get("completed")]
    efficiencies = [r["efficiency"] for r in completed]
    ledger_cases = [r for r in results if r["kind"] == "ledger"]

    summary = {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "completion_rate": round(len(completed) / len(completion_cases), 4) if completion_cases else 0.0,
        "mean_trajectory_efficiency": round(sum(efficiencies) / len(efficiencies), 4) if efficiencies else 0.0,
        "gating_accuracy": round(
            sum(1 for r in ledger_cases if r["passed"]) / len(ledger_cases), 4
        ) if ledger_cases else 0.0,
        "cases": results,
    }
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=== Scenario eval ===")
    for r in results:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['id']} ({r['kind']})")
    print(
        f"pass_rate={summary['pass_rate']} completion={summary['completion_rate']} "
        f"efficiency={summary['mean_trajectory_efficiency']} gating={summary['gating_accuracy']}"
    )
    print(f"Saved to {RESULTS_PATH}")
    return summary


if __name__ == "__main__":
    summary = main()
    raise SystemExit(0 if summary["pass_rate"] == 1.0 else 1)
