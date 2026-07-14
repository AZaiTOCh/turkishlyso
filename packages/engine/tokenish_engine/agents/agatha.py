"""
Agatha — tokopt archive / performance ledger.

SQLite record-keeper for Rainman briefs and per-run cylinder firing.
No hallucinations: stores only what Rainman and the pipeline hand her.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from tokenish_engine.settings_store import tokenish_home


def _db_path() -> Path:
    home = tokenish_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "agatha.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cylinder_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            fidelity_mode TEXT,
            total_tokex INTEGER,
            tokex_this_run INTEGER,
            saved_tokex INTEGER,
            saved_pct REAL,
            stages_json TEXT,
            cylinders_json TEXT,
            rainman_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cylinder_totals (
            cylinder TEXT PRIMARY KEY,
            fires INTEGER NOT NULL DEFAULT 0,
            last_ts REAL
        )
        """
    )
    conn.commit()
    return conn


def archive_rainman_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Persist a Rainman brief. Returns factual archive receipt."""
    tokex = brief.get("tokex") or {}
    stages = brief.get("stages") or []
    cylinders = brief.get("cylinders") or []
    ts = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO cylinder_runs
            (ts, fidelity_mode, total_tokex, tokex_this_run, saved_tokex, saved_pct,
             stages_json, cylinders_json, rainman_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                brief.get("fidelity_mode") or "loyalty",
                int(tokex.get("total_tokex") or 0),
                int(tokex.get("tokex_this_run") or 0),
                int(tokex.get("saved_tokex") or 0),
                float(tokex.get("saved_pct") or 0.0),
                json.dumps(stages),
                json.dumps(cylinders),
                json.dumps(brief),
            ),
        )
        for row in cylinders:
            if not row.get("fired"):
                continue
            name = str(row.get("cylinder") or "unknown")
            conn.execute(
                """
                INSERT INTO cylinder_totals (cylinder, fires, last_ts)
                VALUES (?, 1, ?)
                ON CONFLICT(cylinder) DO UPDATE SET
                    fires = fires + 1,
                    last_ts = excluded.last_ts
                """,
                (name, ts),
            )
        conn.commit()
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {
        "agent": "Agatha",
        "archived": True,
        "run_id": run_id,
        "db": str(_db_path()),
        "ts": ts,
    }


def cylinder_rollups() -> list[dict[str, Any]]:
    """Factual fire counts only — not invented token savings."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT cylinder, fires, last_ts FROM cylinder_totals ORDER BY fires DESC"
        ).fetchall()
    return [
        {"cylinder": r["cylinder"], "fires": r["fires"], "last_ts": r["last_ts"]}
        for r in rows
    ]


def recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, ts, fidelity_mode, total_tokex, tokex_this_run, saved_tokex, saved_pct
            FROM cylinder_runs ORDER BY id DESC LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [dict(r) for r in rows]
