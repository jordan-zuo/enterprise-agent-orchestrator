# enterprise-agent-orchestrator: Deterministic Workflow Orchestration with Approval Gates

Hand-rolled state graph for tool-using workflows. Typed Pydantic state, pure routing function, hard step ceiling, fail-loud tool errors, and a human approval gate for sensitive operations. No agent framework dependency.

Status: state graph core with termination guarantee. Tools, guardrails, and the scenario eval suite land in follow-up milestones.

## Run

```powershell
pip install -r requirements.txt
python -m pytest -q
```
