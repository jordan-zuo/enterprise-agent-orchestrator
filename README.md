# enterprise-agent-orchestrator: Deterministic Workflow Orchestration with Approval Gates

Hand-rolled state graph for tool-using workflows. Typed Pydantic state, pure routing function, hard step ceiling, fail-loud tool errors, and a human approval gate for sensitive operations. No agent framework dependency.

Status: working demo. Live run streaming, run list with reload reattach and cancel, request-id idempotency, evidence-backed ledger writes, human approvals, duplicate-posting guard, and an archive-first ledger reset. 100 tests, deterministic eval 14/14.

## Run

```powershell
pip install -r requirements.txt
python -m pytest -q
```

## Live judged eval

The offline eval is scripted and deterministic. The live suite asks a real model to work the actual bills, then a second model scores the trajectory against a fixed rubric.

```powershell
python scripts/judged_evaluate.py --dry-run
python scripts/judged_evaluate.py --case agl-due-post
python scripts/judged_evaluate.py
```

The agent model comes from `LLM_MODEL`. The judge uses `JUDGE_MODEL` on `JUDGE_BASE_URL` and needs `JUDGE_API_KEY` in `.env`. Keys are never committed.

Deterministic hard checks stay authoritative: status, ledger rows and amounts, forbidden documents and amounts, approval gates, tickets, duplicate rows, and required answer terms. The judge scores task success, grounding, safety, trajectory quality, and honesty from 0 to 5 under rubric `judge-v1`. Any failed hard check forces a fail verdict. Three calibration probes run before the cases, and a judge that cannot reject a wrong amount or a skipped gate marks the run unreliable.

Results land in `eval/judged_results.json` and `eval/report.md`. A full run costs about 17k judge tokens; Groq's free tier caps the judge at 200k per day, and calibration aborts the suite rather than publish a verdict from a judge that cannot reject a wrong amount or a skipped gate.

