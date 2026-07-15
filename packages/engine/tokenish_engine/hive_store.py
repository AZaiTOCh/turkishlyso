"""
In-process Live World Counter Clock store (dev / single-host B).

Worldwide multi-user tally uses Cloudflare Worker (packages/tokex-clock).
This local store powers the same protocol when TOKENISH_HIVE_URL is unset.

Per-node values are ABSOLUTE lifetime cumulatives (not loose deltas), so a sole
user's global % stays on par with their lifetime panel.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tokenish_engine.settings_store import tokenish_home

# Presence window for "users online"
ONLINE_SECS = 90.0


def _path() -> Path:
    home = tokenish_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "live_world_counter_clock.json"


def _load() -> dict[str, Any]:
    path = _path()
    empty = {
        "clock": "Live World Counter Clock",
        "nodes": {},
        "updated_ts": None,
    }
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty
    if "nodes" not in data or not isinstance(data.get("nodes"), dict):
        # migrate old additive schema into a synthetic node
        nodes = {}
        if int(data.get("saved_tokex") or 0) or int(data.get("total_tokex") or 0):
            nodes["legacy"] = {
                "saved_tokex": int(data.get("saved_tokex") or 0),
                "total_tokex": int(data.get("total_tokex") or 0),
                "last_ts": float(data.get("updated_ts") or time.time()),
            }
        data = {"clock": "Live World Counter Clock", "nodes": nodes, "updated_ts": data.get("updated_ts")}
    return data


def _save(data: dict[str, Any]) -> None:
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _recompute(data: dict[str, Any]) -> dict[str, Any]:
    nodes = data.get("nodes") or {}
    saved = 0
    total = 0
    now = time.time()
    online = 0
    for node in nodes.values():
        saved += int(node.get("saved_tokex") or 0)
        total += int(node.get("total_tokex") or 0)
        last = float(node.get("last_ts") or 0)
        if last and (now - last) <= ONLINE_SECS:
            online += 1
    pct = round((saved / total) * 100.0, 2) if total else 0.0
    return {
        "clock": "Live World Counter Clock",
        "agent": "Neoborg",
        "saved_tokex": saved,
        "total_tokex": total,
        "saved_pct": pct,
        "users_online": online,
        "nodes": len(nodes),
        "updated_ts": data.get("updated_ts"),
        "source": "engine-hive",
    }


def snapshot() -> dict[str, Any]:
    return _recompute(_load())


def upsert_node(node_id: str, saved_tokex: int, total_tokex: int) -> dict[str, Any]:
    """Set/replace one node's absolute lifetime TOKEX, then recompute world totals."""
    node_id = str(node_id or "").strip()[:64]
    saved = int(saved_tokex)
    total = int(total_tokex)
    if not node_id:
        raise ValueError("node_id required")
    if saved < 0 or total < 0 or (total > 0 and saved > total):
        raise ValueError("impossible tokex relationship")
    data = _load()
    nodes = dict(data.get("nodes") or {})
    nodes[node_id] = {
        "saved_tokex": saved,
        "total_tokex": total,
        "last_ts": time.time(),
    }
    data["nodes"] = nodes
    data["updated_ts"] = time.time()
    _save(data)
    return _recompute(data)


def contribute(node_id: str, saved_tokex: int, total_tokex: int) -> dict[str, Any]:
    """
    Legacy delta contribute → fold into node's absolute cumulative.
    Prefer upsert_node / heartbeat for UI-parity.
    """
    node_id = str(node_id or "").strip()[:64]
    delta_saved = int(saved_tokex)
    delta_total = int(total_tokex)
    if not node_id:
        raise ValueError("node_id required")
    if delta_saved < 0 or delta_total < 0 or (delta_total > 0 and delta_saved > delta_total):
        raise ValueError("impossible tokex relationship")
    data = _load()
    nodes = dict(data.get("nodes") or {})
    cur = dict(nodes.get(node_id) or {})
    new_saved = int(cur.get("saved_tokex") or 0) + delta_saved
    new_total = int(cur.get("total_tokex") or 0) + delta_total
    return upsert_node(node_id, new_saved, new_total)


def heartbeat(node_id: str, saved_tokex: int | None = None, total_tokex: int | None = None) -> dict[str, Any]:
    """Presence ping; optionally refresh absolute lifetime stats for the node."""
    node_id = str(node_id or "").strip()[:64]
    if not node_id:
        raise ValueError("node_id required")
    data = _load()
    nodes = dict(data.get("nodes") or {})
    cur = dict(nodes.get(node_id) or {"saved_tokex": 0, "total_tokex": 0})
    if saved_tokex is not None:
        cur["saved_tokex"] = int(saved_tokex)
    if total_tokex is not None:
        cur["total_tokex"] = int(total_tokex)
    cur["last_ts"] = time.time()
    nodes[node_id] = cur
    data["nodes"] = nodes
    data["updated_ts"] = time.time()
    _save(data)
    return _recompute(data)
