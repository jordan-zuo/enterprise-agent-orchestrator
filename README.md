# enterprise-agent-orchestrator: Deterministic Workflow Orchestration with Approval Gates

Hand-rolled state graph for tool-using workflows. Typed Pydantic state, pure routing function, hard step ceiling, fail-loud tool errors, and a human approval gate for sensitive operations. No agent framework dependency.

Status: working demo. Live run streaming, run list with reload reattach and cancel, request-id idempotency, evidence-backed ledger writes, human approvals, duplicate-posting guard, and an archive-first ledger reset. 88 tests, deterministic eval 14/14.

See [HANDOFF.md](HANDOFF.md) for architecture, guarantees, known gaps, and the remaining phases.

## Run

```powershell
pip install -r requirements.txt
python -m pytest -q
```
