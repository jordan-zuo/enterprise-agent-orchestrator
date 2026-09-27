from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    override = os.environ.get("APP_DB", "")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "app.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path | None = None) -> Path:
    target = path or db_path()
    conn = connect(target)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                step_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                kind TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                source_doc TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                ticket_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                meta TEXT NOT NULL,
                decided INTEGER NOT NULL DEFAULT 0,
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                decided_at TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return target


def create_run(task: str, path: Path | None = None) -> str:
    run_id = f"r-{uuid.uuid4().hex[:12]}"
    conn = connect(path)
    try:
        now = _now()
        conn.execute(
            "INSERT INTO runs (run_id, task, status, step_count, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, task, "running", 0, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def append_event(
    run_id: str, kind: str, body: str, path: Path | None = None
) -> None:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) AS m FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        seq = int(row["m"]) + 1
        conn.execute(
            "INSERT INTO events (run_id, seq, kind, body, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (run_id, seq, kind, body, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def set_run_status(
    run_id: str, status: str, step_count: int, path: Path | None = None
) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "UPDATE runs SET status = ?, step_count = ?, updated_at = ?"
            " WHERE run_id = ?",
            (status, step_count, _now(), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: str, path: Path | None = None) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT run_id, task, status, step_count FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_events(run_id: str, path: Path | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT seq, kind, body FROM events WHERE run_id = ? ORDER BY seq",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def insert_ledger_entry(
    run_id: str,
    entry_id: str,
    amount: float,
    currency: str,
    source_doc: str,
    path: Path | None = None,
) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO ledger (entry_id, run_id, amount, currency, source_doc,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (entry_id, run_id, float(amount), currency, source_doc, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_ledger(path: Path | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT entry_id, run_id, amount, currency, source_doc"
            " FROM ledger ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def table_counts(path: Path | None = None) -> dict[str, int]:
    conn = connect(path)
    try:
        out = {}
        for table in ("runs", "events", "ledger", "approvals"):
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            out[table] = int(row["n"])
        return out
    finally:
        conn.close()


def submit_approval(
    ticket_id: str,
    run_id: str,
    action: str,
    detail: str,
    meta: dict,
    path: Path | None = None,
) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO approvals (ticket_id, run_id, action, detail, meta,"
            " decided, approved, created_at) VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
            (ticket_id, run_id, action, detail, json.dumps(meta), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_pending_approvals(path: Path | None = None) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT ticket_id, run_id, action, detail, meta FROM approvals"
            " WHERE decided = 0 ORDER BY created_at"
        ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["meta"] = json.loads(item["meta"])
            out.append(item)
        return out
    finally:
        conn.close()


def decide_approval(
    ticket_id: str, approved: bool, path: Path | None = None
) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT ticket_id, run_id, action, detail, meta FROM approvals"
            " WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["meta"] = json.loads(item["meta"])
        conn.execute(
            "UPDATE approvals SET decided = 1, approved = ?, decided_at = ?"
            " WHERE ticket_id = ?",
            (1 if approved else 0, _now(), ticket_id),
        )
        conn.commit()
        item["approved"] = bool(approved)
        return item
    finally:
        conn.close()
