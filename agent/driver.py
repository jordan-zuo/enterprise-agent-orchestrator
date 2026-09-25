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
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("The 'python-dotenv' package is required.") from exc
    load_dotenv()
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set: live model calls need a key.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The 'openai' package is required for live calls.") from exc
    base_url = os.environ.get("LLM_BASE_URL", "https://api.llm7.io/v1")
    return OpenAI(api_key=api_key, base_url=base_url)


def _prompt_for(state: Any, hint: str = "") -> str:
    base = (
        "You route one step of a deterministic workflow. "
        "You MUST pick action from exactly this set: retrieve, ledger_write, "
        "finish, request_approval. Any other action string is invalid. "
        "Arg shapes: retrieve takes {query}; ledger_write takes "
        "{entry_id, amount, source_doc}; finish takes {}; request_approval "
        "takes {reason}. Reply with ONLY this JSON object: "
        '{"action": "<one of the four>", "args": {...}, "reason": "<short>"}. '
        f"Task: {state.task}. Steps used: {state.step_count}/{state.max_steps}. "
        f"History: {list(state.history)}."
    )
    if hint:
        return base + f" Previous answer was rejected: {hint}. Fix it."
    return base


def _parse(content: str) -> ModelDecision:
    text = (content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"model did not return JSON: {content!r}")
    payload = json.loads(text[start : end + 1])
    if payload.get("action") not in KNOWN_ACTIONS:
        raise ValueError(f"unknown action: {payload.get('action')!r}")
    return ModelDecision(
        action=payload["action"],
        args=dict(payload.get("args") or {}),
        reason=str(payload.get("reason") or ""),
    )


def decide(state: Any, client: Any, model: str, max_attempts: int = 2) -> ModelDecision:
    """Ask the model what to do next. Malformed or unknown answers raise.

    The model gets one retry with the rejection reason fed back. Persistent
    misbehavior raises instead of executing something unintended.
    """
    hint = ""
    for _ in range(max_attempts):
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _prompt_for(state, hint)}],
            temperature=0,
            max_tokens=200,
        )
        content = completion.choices[0].message.content or ""
        try:
            return _parse(content)
        except ValueError as exc:
            hint = str(exc)
    raise ValueError(f"model failed to route after {max_attempts} attempts: {hint}")
