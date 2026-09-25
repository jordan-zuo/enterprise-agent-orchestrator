from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    task: str
    step_count: int = 0
    max_steps: int = 10
    history: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "awaiting_approval", "done", "failed"] = "pending"
    failure_reason: str = ""


class StepDecision(BaseModel):
    next_node: Literal["execute_tool", "await_approval", "terminal"]
    detail: str = ""
