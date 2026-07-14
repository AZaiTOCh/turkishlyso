"""
NeoBorg — benevolent hive TOKEX clock agent.

Receives Mrs. Brown handoffs, fact-checks them again, and keeps a local
running tally that will later power the live global TOKEX CLOCK
(GitHub / website aggregate — network broadcast deliberately parked).

Star Trek Borg as metaphor only: cooperative shared savings, not extraction.
No LLM. No invented global figures beyond what has been handed in.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tokenish_engine.settings_store import tokenish_home


def _ledger_path() -> Path:
    home = tokenish_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "neoborg_ledger.json"


def _load_ledger() -> dict[str, Any]:
    path = _ledger_path()
    if not path.exists():
        return {
            "agent": "NeoBorg",
            "contributions": 0,
            "global_saved_tokex": 0,
            "global_total_tokex": 0,
            "updated_ts": None,
            "entries": [],
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "agent": "NeoBorg",
            "contributions": 0,
            "global_saved_tokex": 0,
            "global_total_tokex": 0,
            "updated_ts": None,
            "entries": [],
        }


def _save_ledger(data: dict[str, Any]) -> None:
    path = _ledger_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cross_vet_and_record(handoff: dict[str, Any] | None) -> dict[str, Any]:
    """
    Second-pass factual check, then add to local NeoBorg ledger.
    Network broadcast of the live clock is not enabled yet.
    """
    if not handoff:
        return {
            "agent": "NeoBorg",
            "accepted": False,
            "reason": "empty handoff",
            "broadcast": False,
            "ledger": _load_ledger(),
        }
    try:
        saved = int(handoff.get("saved_tokex") or 0)
        total = int(handoff.get("total_tokex") or 0)
    except (TypeError, ValueError):
        return {
            "agent": "NeoBorg",
            "accepted": False,
            "reason": "handoff tokex not numeric",
            "broadcast": False,
            "ledger": _load_ledger(),
        }
    if saved < 0 or total < 0 or (total > 0 and saved > total):
        return {
            "agent": "NeoBorg",
            "accepted": False,
            "reason": "handoff fails cross-vet (impossible tokex relationship)",
            "broadcast": False,
            "ledger": _load_ledger(),
        }

    ledger = _load_ledger()
    ledger["contributions"] = int(ledger.get("contributions") or 0) + 1
    ledger["global_saved_tokex"] = int(ledger.get("global_saved_tokex") or 0) + saved
    ledger["global_total_tokex"] = int(ledger.get("global_total_tokex") or 0) + total
    ledger["updated_ts"] = time.time()
    entries = list(ledger.get("entries") or [])
    entries.append(
        {
            "ts": ledger["updated_ts"],
            "saved_tokex": saved,
            "total_tokex": total,
            "cylinders_fired": handoff.get("cylinders_fired") or [],
        }
    )
    ledger["entries"] = entries[-200:]  # keep last 200 local contributions
    ledger["agent"] = "NeoBorg"
    _save_ledger(ledger)

    saved_sum = int(ledger["global_saved_tokex"])
    total_sum = int(ledger["global_total_tokex"])
    pct = round((saved_sum / total_sum) * 100.0, 2) if total_sum else 0.0

    return {
        "agent": "NeoBorg",
        "accepted": True,
        "reason": "ok",
        "broadcast": False,  # live multi-user clock parked by product decision
        "broadcast_note": (
            "global live TOKEX CLOCK broadcast is parked; "
            "this ledger is local-factual only until network hive is enabled"
        ),
        "clock_preview": {
            "saved_tokex": saved_sum,
            "total_tokex": total_sum,
            "saved_pct": pct,
            "contributions": int(ledger["contributions"]),
        },
        "ledger_path": str(_ledger_path()),
    }


def clock_snapshot() -> dict[str, Any]:
    ledger = _load_ledger()
    saved_sum = int(ledger.get("global_saved_tokex") or 0)
    total_sum = int(ledger.get("global_total_tokex") or 0)
    pct = round((saved_sum / total_sum) * 100.0, 2) if total_sum else 0.0
    return {
        "agent": "NeoBorg",
        "broadcast": False,
        "saved_tokex": saved_sum,
        "total_tokex": total_sum,
        "saved_pct": pct,
        "contributions": int(ledger.get("contributions") or 0),
        "updated_ts": ledger.get("updated_ts"),
    }
