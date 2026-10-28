import json
from types import SimpleNamespace

import pytest

from scripts.judge import (
    RUBRIC_SHA,
    RUBRIC_VERSION,
    JudgeConfigError,
    JudgeError,
    build_judge_client,
    build_judge_messages,
    judge_case,
    preflight_judge,
)
from scripts.judged_evaluate import (
    aggregate,
    hard_checks,
    load_suite,
    render_report,
    run_live_case,
)


def _case(case_id: str) -> dict:
    return {case["id"]: case for case in load_suite()["cases"]}[case_id]


def _record(ledger: list[dict], *, status: str = "done", gated: bool = False, tickets: list[dict] | None = None) -> dict:
    history = ["retrieve [AGL amount due]: agl-better-bills-sample-bill-necf | Amount due $63.70"]
    if gated:
        history.append("gated: t-1 (amount over threshold)")
    history.append("ledger_write: agl-better-bills-sample-bill-necf 63.70 AUD")
    return {
        "status": status,
        "failure_reason": "",
        "steps": 3,
        "settled": False,
        "decisions": [{"step": 3, "action": "finish", "args": {}, "reason": "posted AGL 63.70"}],
        "ledger": ledger,
        "tickets": tickets or [],
        "history": history,
        "latency_ms": 10.0,
    }


def _completion(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _empty_completion():
    """OpenRouter can answer 200 with no choices when a free provider fails."""
    return SimpleNamespace(choices=None, usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0))


class _Completions:
    def __init__(self, contents: list[str]) -> None:
        self.contents = list(contents)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.contents.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return _completion(item)
        return item


class _JudgeClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = SimpleNamespace(completions=_Completions(contents))


def _verdict(verdict: str = "pass") -> dict:
    return {
        "task_success": 5,
        "grounding": 5,
        "safety": 5,
        "trajectory_quality": 4,
        "honesty": 5,
        "overall": 5,
        "verdict": verdict,
        "rationale": "posted the right amount from the cited document",
        "evidence_refs": ["agl-better-bills-sample-bill-necf"],
    }


def test_hard_checks_reject_wrong_amount_and_missing_gate() -> None:
    agl = _case("agl-due-post")
    good = _record([{"entry_id": "j-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"}])
    assert hard_checks(agl, good)["passed"] is True

    wrong = _record([{"entry_id": "j-2", "amount": 79.87, "source_doc": "agl-better-bills-sample-bill-necf"}])
    failed = {check["name"] for check in hard_checks(agl, wrong)["checks"] if not check["ok"]}
    assert {"ledger_match", "forbidden_amounts"} <= failed

    origin = _case("origin-gated-post")
    ungated = _record(
        [{"entry_id": "j-3", "amount": 13376.47, "source_doc": "origin-standing-bill-modified-alexcarter"}]
    )
    failed = {check["name"] for check in hard_checks(origin, ungated)["checks"] if not check["ok"]}
    assert {"gate", "tickets", "ticket_approved"} <= failed


def test_judge_prompt_embeds_rubric_gold_and_hard_checks() -> None:
    agl = _case("agl-due-post")
    record = _record([{"entry_id": "j-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"}])
    record["hard"] = hard_checks(agl, record)

    messages = build_judge_messages(agl, record)
    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "Deterministic checks are authoritative" in system
    assert RUBRIC_VERSION in user
    assert "agl-better-bills-sample-bill-necf" in user
    assert "63.7" in user
    assert "deterministic_checks" in user


def test_judge_retries_malformed_json_then_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE_REASONING", raising=False)
    monkeypatch.delenv("JUDGE_JSON_MODE", raising=False)
    agl = _case("agl-due-post")
    record = _record([{"entry_id": "j-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"}])
    record["hard"] = hard_checks(agl, record)

    client = _JudgeClient(["not json", json.dumps(_verdict())])
    result = judge_case(client, "qwen/qwen3.8-27b", agl, record)
    assert result["verdict"]["verdict"] == "pass"
    assert len(client.chat.completions.calls) == 2
    assert client.chat.completions.calls[0]["temperature"] == 0

    with pytest.raises(JudgeError):
        judge_case(_JudgeClient(["nope", "still nope"]), "qwen/qwen3.8-27b", agl, record)


class _RateLimited(Exception):
    status_code = 429


def test_judge_pool_moves_to_next_model_when_one_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE_REASONING", raising=False)
    monkeypatch.delenv("JUDGE_JSON_MODE", raising=False)
    agl = _case("agl-due-post")
    record = _record([{"entry_id": "j-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"}])
    record["hard"] = hard_checks(agl, record)

    client = _JudgeClient([_RateLimited("429 from model-a"), json.dumps(_verdict())])
    result = judge_case(client, "model-a,model-b", agl, record)
    assert result["model"] == "model-b"
    assert [call["model"] for call in client.chat.completions.calls] == ["model-a", "model-b"]
    assert "response_format" not in client.chat.completions.calls[0]
    assert "extra_body" not in client.chat.completions.calls[0]

    with pytest.raises(JudgeError, match="model-a.*model-b"):
        judge_case(_JudgeClient([_RateLimited("a"), _RateLimited("b")]), "model-a,model-b", agl, record)


def test_judge_moves_on_when_a_model_returns_no_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE_REASONING", raising=False)
    monkeypatch.delenv("JUDGE_JSON_MODE", raising=False)
    agl = _case("agl-due-post")
    record = _record([{"entry_id": "j-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"}])
    record["hard"] = hard_checks(agl, record)

    client = _JudgeClient([_empty_completion(), _empty_completion(), json.dumps(_verdict())])
    result = judge_case(client, "model-a,model-b", agl, record)
    assert result["model"] == "model-b"
    assert len(client.chat.completions.calls) == 3


def test_judge_request_settings_follow_env_and_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    agl = _case("agl-due-post")
    record = _record([{"entry_id": "j-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"}])
    record["hard"] = hard_checks(agl, record)

    monkeypatch.delenv("JUDGE_REASONING", raising=False)
    monkeypatch.delenv("JUDGE_JSON_MODE", raising=False)
    plain = _JudgeClient([json.dumps(_verdict())])
    judge_case(plain, "m", agl, record, base_url="https://openrouter.ai/api/v1")
    assert "extra_body" not in plain.chat.completions.calls[0]

    monkeypatch.setenv("JUDGE_REASONING", "off")
    monkeypatch.setenv("JUDGE_JSON_MODE", "1")
    tuned = _JudgeClient([json.dumps(_verdict()), json.dumps(_verdict())])
    judge_case(tuned, "m", agl, record, base_url="https://openrouter.ai/api/v1")
    judge_case(tuned, "m", agl, record, base_url="https://api.groq.com/openai/v1")
    openrouter, groq = tuned.chat.completions.calls
    assert openrouter["extra_body"] == {"reasoning": {"enabled": False}}
    assert openrouter["response_format"] == {"type": "json_object"}
    assert groq["extra_body"] == {"reasoning_effort": "none"}


class _AuthError(Exception):
    status_code = 401


class _Models:
    def list(self):
        raise _AuthError("invalid api key")


def test_judge_preflight_reports_missing_key_and_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    with pytest.raises(JudgeConfigError) as missing:
        build_judge_client(load_env=False)
    assert "JUDGE_API_KEY" in str(missing.value)

    with pytest.raises(JudgeConfigError) as rejected:
        preflight_judge(
            SimpleNamespace(models=_Models()),
            "qwen/qwen3.8-27b",
            "https://api.groq.com/openai/v1",
        )
    assert "api.groq.com/openai/v1" in str(rejected.value)
    assert "fresh key" in str(rejected.value)


def test_report_aggregates_agreement_and_dimension_means() -> None:
    passing = {
        "id": "case-a",
        "status": "done",
        "steps": 3,
        "latency_ms": 100.0,
        "hard": {"passed": True, "checks": []},
        "judge": {
            "verdict": {**_verdict(), "task_success": 5, "grounding": 5, "safety": 5,
                        "trajectory_quality": 5, "honesty": 5, "overall": 5},
            "latency_ms": 40.0,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    }
    failing = {
        "id": "case-b",
        "status": "failed",
        "steps": 5,
        "latency_ms": 200.0,
        "hard": {"passed": False, "checks": [{"name": "ledger_match", "ok": False, "detail": "wrong"}]},
        "judge": {
            "verdict": {**_verdict("fail"), "task_success": 1, "grounding": 1, "safety": 1,
                        "trajectory_quality": 1, "honesty": 1, "overall": 1},
            "latency_ms": 60.0,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        "failure_reason": "wrong amount",
    }
    meta = {
        "agent_model": "agent-test",
        "agent_base_url": "https://example.invalid/v1",
        "judge_model": "qwen/qwen3.8-27b",
        "judge_base_url": "https://api.groq.com/openai/v1",
        "reasoning_effort": "none",
        "rubric_version": RUBRIC_VERSION,
        "rubric_sha": RUBRIC_SHA,
        "started_at": "t0",
        "finished_at": "t1",
        "command": "test",
    }
    calibration = {"ok": True, "passed": 3, "total": 3, "probes": []}
    summary = aggregate([passing, failing], calibration, meta, judge_required=True)

    assert summary["hard_pass_rate"] == 0.5
    assert summary["judge_pass_rate"] == 0.5
    assert summary["agreement"] == 1.0
    assert summary["judge_stricter"] == 0
    assert summary["judge_lenient"] == 0
    assert summary["mean_scores"]["overall"] == 3.0
    assert summary["pass"] is False

    report = render_report(summary, judge_required=True)
    assert RUBRIC_SHA in report
    assert "case-a" in report and "case-b" in report
    assert "Judge calibration" in report


class _ScriptedClient:
    def __init__(self, script: list[dict]) -> None:
        self._script = list(script)
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        payload = self._script.pop(0) if self._script else {"action": "finish", "args": {}, "reason": "done"}
        return _completion(json.dumps(payload))


def test_live_case_captures_ledger_and_isolates_runs() -> None:
    agl = _case("agl-due-post")
    corpus = json.loads((__import__("pathlib").Path(__file__).resolve().parent.parent / "data" / "corpus.json").read_text(encoding="utf-8"))
    script = [
        {"action": "retrieve", "args": {"query": "AGL amount due"}, "reason": "find the bill"},
        {
            "action": "ledger_write",
            "args": {"entry_id": "eval-1", "amount": 63.70, "source_doc": "agl-better-bills-sample-bill-necf"},
            "reason": "post the amount due",
        },
        {"action": "finish", "args": {}, "reason": "posted AGL 63.70"},
    ]

    first = run_live_case(agl, _ScriptedClient(script), "scripted", corpus)
    assert first["status"] == "done"
    assert first["steps"] == 3
    assert len(first["ledger"]) == 1
    assert first["ledger"][0]["amount"] == 63.70
    assert first["hard"]["passed"] is True

    second = run_live_case(agl, _ScriptedClient(script), "scripted", corpus)
    assert len(second["ledger"]) == 1
