"""
Neoborg — benevolent hive TOKEX clock agent.

Receives Mrs. Brown handoffs, fact-checks them again, keeps a slim local
counter for hive sync, and (when opted in) broadcasts vetted deltas.
Does NOT re-archive Rainman/Agatha briefs — one markdown file per run only.
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
            "agent": "Neoborg",
            "contributions": 0,
            "global_saved_tokex": 0,
            "global_total_tokex": 0,
            "updated_ts": None,
            "entries": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "agent": "Neoborg",
            "contributions": 0,
            "global_saved_tokex": 0,
            "global_total_tokex": 0,
            "updated_ts": None,
            "entries": [],
        }
    data["agent"] = "Neoborg"
    return data


def _save_ledger(data: dict[str, Any]) -> None:
    path = _ledger_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _broadcast_sync(saved: int, total: int) -> dict[str, Any]:
    """Sync hive contribute (pipeline is sync)."""
    from tokenish_engine.agents.tokex_clock import broadcast_contribution_sync

    return broadcast_contribution_sync(saved, total)


def cross_vet_and_record(handoff: dict[str, Any] | None) -> dict[str, Any]:
    if not handoff:
        return {
            "agent": "Neoborg",
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
            "agent": "Neoborg",
            "accepted": False,
            "reason": "handoff tokex not numeric",
            "broadcast": False,
            "ledger": _load_ledger(),
        }
    if saved < 0 or total < 0 or (total > 0 and saved > total):
        return {
            "agent": "Neoborg",
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
    # Slim counter only — no brief re-archive (Agatha owns ~/.tokenish/output/runs/*.md).
    ledger["entries"] = (list(ledger.get("entries") or []) + [
        {"ts": ledger["updated_ts"], "saved_tokex": saved, "total_tokex": total}
    ])[-50:]
    ledger["agent"] = "Neoborg"
    _save_ledger(ledger)

    saved_sum = int(ledger["global_saved_tokex"])
    total_sum = int(ledger["global_total_tokex"])
    pct = round((saved_sum / total_sum) * 100.0, 2) if total_sum else 0.0

    hive = _broadcast_sync(saved, total)

    return {
        "agent": "Neoborg",
        "accepted": True,
        "reason": "ok",
        "broadcast": bool(hive.get("broadcast")),
        "broadcast_note": hive.get("reason") or "",
        "hive": hive,
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
        "agent": "Neoborg",
        "broadcast": False,
        "saved_tokex": saved_sum,
        "total_tokex": total_sum,
        "saved_pct": pct,
        "contributions": int(ledger.get("contributions") or 0),
        "updated_ts": ledger.get("updated_ts"),
    }
