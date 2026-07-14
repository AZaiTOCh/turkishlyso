"""
Mrs. Brown — matriarch hive agent.

Receives validated local TOKEX / cylinder records (from Agatha),
checks they are well-formed numbers only, then hands them to NeoBorg
for global cross-vetting and broadcast bookkeeping.

No LLM. No invented totals.
"""

from __future__ import annotations

from typing import Any


def intake_local_savings(record: dict[str, Any]) -> dict[str, Any]:
    """
    Accept one local run record. Reject anything that is not factual numeric TOKEX.
    """
    tokex = record.get("tokex") or {}
    try:
        total = int(tokex.get("total_tokex") or 0)
        run = int(tokex.get("tokex_this_run") or 0)
        saved = int(tokex.get("saved_tokex") or max(0, total - run))
        pct = float(tokex.get("saved_pct") or 0.0)
    except (TypeError, ValueError):
        return {
            "agent": "Mrs. Brown",
            "accepted": False,
            "reason": "record is missing numeric tokex fields",
            "handoff": None,
        }

    if total < 0 or run < 0 or saved < 0:
        return {
            "agent": "Mrs. Brown",
            "accepted": False,
            "reason": "negative tokex values are not allowed",
            "handoff": None,
        }

    handoff = {
        "source": "agatha_local",
        "total_tokex": total,
        "tokex_this_run": run,
        "saved_tokex": saved,
        "saved_pct": pct,
        "rainman_verdict": (record.get("rainman") or {}).get("verdict"),
        "cylinders_fired": [
            c.get("cylinder")
            for c in (record.get("cylinders") or [])
            if c.get("fired")
        ],
    }
    return {
        "agent": "Mrs. Brown",
        "accepted": True,
        "reason": "ok",
        "handoff": handoff,
    }
