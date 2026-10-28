"""Shared test helpers."""

from __future__ import annotations

import time
from typing import Any

TERMINAL = {"done", "failed", "awaiting_approval", "cancelled"}


def wait_for_run(client: Any, run_id: str, timeout: float = 20.0) -> dict:
    """Poll until the background run leaves ``running``.

    ``/run`` returns as soon as the worker is queued, so every caller that
    cares about the outcome has to wait for a settled state.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/runs/{run_id}").json()
        if body["run"]["status"] in TERMINAL:
            return body
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not settle in {timeout}s")


def wait_for_event(
    client: Any, run_id: str, kind: str, timeout: float = 10.0
) -> list[dict]:
    """Poll until an event of ``kind`` is persisted for the run."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = client.get(f"/runs/{run_id}").json()["events"]
        if any(event["kind"] == kind for event in events):
            return events
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} never recorded a {kind!r} event")
