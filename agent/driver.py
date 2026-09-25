from __future__ import annotations

import json
import os
from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelDecision(BaseModel):
    action: Literal["retrieve", "ledger_write", "finish", "request_approval"]
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


KNOWN_ACTIONS = ("retrieve", "ledger_write", "finish", "request_approval")


def build_client() -> Any:
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set: live model calls need a key.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The 'openai' package is required for live calls.") from exc
    base_url = os.environ.get("LLM_BASE_URL", "https://api.llm7.io/v1")
    return OpenAI(api_key=api_key, base_url=base_url)


def decide(state: Any, client: Any, model: str) -> ModelDecision:
    """Ask the model what to do next. Malformed or unknown answers raise."""
    prompt = (
        "You route one step of a deterministic workflow. "
        "Reply with ONLY this JSON object: "
        '{"action": "retrieve|ledger_write|finish|request_approval", '
        '"args": {...}, "reason": "<short>"}. '
        f"Task: {state.task}. Steps used: {state.step_count}/{state.max_steps}. "
        f"History: {list(state.history)}."
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=200,
    )
    content = (completion.choices[0].message.content or "").strip()
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"model did not return JSON: {content!r}")
    payload = json.loads(content[start : end + 1])
    if payload.get("action") not in KNOWN_ACTIONS:
        raise ValueError(f"unknown action: {payload.get('action')!r}")
    return ModelDecision(
        action=payload["action"],
        args=dict(payload.get("args") or {}),
        reason=str(payload.get("reason") or ""),
    )
