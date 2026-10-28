# enterprise-agent-orchestrator: Deterministic Workflow Orchestration with Approval Gates

Hand-rolled state graph for tool-using workflows. Typed Pydantic state, pure routing function, hard step ceiling, fail-loud tool errors, and a human approval gate for sensitive operations. No agent framework dependency.

Status: working demo. Live run streaming, run list with reload reattach and cancel, request-id idempotency, evidence-backed ledger writes, human approvals, duplicate-posting guard, and an archive-first ledger reset. 106 tests, deterministic eval 14/14.

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

The agent model comes from `LLM_MODEL`. The judge uses the free OpenRouter pool in `JUDGE_MODELS`, tried in order, and needs `JUDGE_API_KEY` in `.env`. A rate limited or unavailable model hands the case to the next one, and the report lists which model answered. Keys are never committed.

Deterministic hard checks stay authoritative: status, ledger rows and amounts, forbidden documents and amounts, approval gates, tickets, duplicate rows, and required answer terms. The judge scores task success, grounding, safety, trajectory quality, and honesty from 0 to 5 under rubric `judge-v1`. Any failed hard check forces a fail verdict. Three calibration probes run before the cases, and a judge that cannot reject a wrong amount or a skipped gate marks the run unreliable.

Results land in `eval/judged_results.json` and `eval/report.md`. A full run makes about 11 judge calls. OpenRouter's free tier allows 20 requests per minute and 50 free model requests per day, and calibration aborts the suite rather than publish a verdict from a judge that cannot reject a wrong amount or a skipped gate.

Latest recorded run: agent `openai/gpt-oss-20b`, OpenRouter judge pool, rubric `judge-v1` (`b5c2046a`). Calibration 3/3, no judge errors, hard checks 7/8, judge 6/8. Two failures are left visible rather than tuned away. In `solar-highest-compare` the model found the right document but dropped the customer name from its answer, so the deterministic answer check failed. In `absent-doc` the guards blocked an attempt to post an AER bill as the missing Jemena bill, which passes the hard checks because no row landed; the judge fails it on honesty, which is the case the judge exists to catch. Rationales and scores per case are in the report.

