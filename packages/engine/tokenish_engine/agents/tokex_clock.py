"""
ZamanZamin — Live World Counter Clock (legacy module id: tokex_clock).

Neoborg hive client + local clock surface.

Architecture (v1 = option B):
  Local tokenish engines POST vetted TOKEX savings to a tiny always-on hive API
  (Cloudflare Worker preferred). The same API is polled for the live collective tally.

Hybrid Pages front-end is optional later; the in-app global panel is the clock surface.
No invented totals. If hive is unreachable, report offline and show last known / local only.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from tokenish_engine.settings_store import load_prefs, save_prefs, tokenish_home

# Default empty until deployer sets TOKENISH_HIVE_URL / prefs.
DEFAULT_HIVE_URL = ""


def _prefs() -> dict[str, Any]:
    return load_prefs()


def hive_url() -> str:
    import os

    raw = (
        os.environ.get("TOKENISH_HIVE_URL")
        or (_prefs().get("hive_url") or "")
        or DEFAULT_HIVE_URL
    )
    return str(raw).strip().rstrip("/")


def hive_opt_in() -> bool:
    return bool(_prefs().get("hive_opt_in"))


def set_hive_opt_in(enabled: bool, *, url: str | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {"hive_opt_in": bool(enabled)}
    if url is not None:
        patch["hive_url"] = str(url).strip().rstrip("/")
    save_prefs(patch)
    return {"hive_opt_in": hive_opt_in(), "hive_url": hive_url()}


def _node_id_path() -> Path:
    home = tokenish_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "neoborg_node_id.txt"


def node_id() -> str:
    path = _node_id_path()
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    nid = f"tknsh_{uuid.uuid4().hex[:16]}"
    path.write_text(nid, encoding="utf-8")
    return nid


def _cache_path() -> Path:
    home = tokenish_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "tokex_clock_cache.json"


def _load_cache() -> dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict[str, Any]) -> None:
    _cache_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _empty_clock(*, source: str, online: bool, note: str = "") -> dict[str, Any]:
    return {
        "agent": "Neoborg",
        "clock": "Live World Counter Clock",
        "online": online,
        "broadcast": online,
        "source": source,
        "saved_tokex": 0,
        "total_tokex": 0,
        "saved_pct": 0.0,
        "users_online": 0,
        "nodes": 0,
        "updated_ts": None,
        "note": note,
    }


def sync_lifetime_sync(saved_tokex: int, total_tokex: int) -> dict[str, Any]:
    """Push this install's absolute lifetime TOKEX so global % matches lifetime for sole user."""
    from tokenish_engine import hive_store

    if not hive_opt_in():
        return {"ok": False, "reason": "hive opt-in off"}
    try:
        saved = int(saved_tokex)
        total = int(total_tokex)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "non-numeric tokex"}
    if saved < 0 or total < 0 or (total > 0 and saved > total):
        return {"ok": False, "reason": "impossible tokex relationship"}

    url = hive_url()
    payload = {
        "node_id": node_id(),
        "saved_tokex": saved,
        "total_tokex": total,
        "mode": "absolute",
        "ts": time.time(),
        "agent": "Neoborg",
    }
    if not url:
        try:
            snap = hive_store.upsert_node(payload["node_id"], saved, total)
            return {"ok": True, "clock": snap}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.post(f"{url}/sync", json=payload)
            if r.status_code >= 400:
                # fallback contribute-as-absolute via upsert-like field if worker old
                r = client.post(f"{url}/heartbeat", json=payload)
            if r.status_code >= 400:
                return {"ok": False, "reason": f"hive HTTP {r.status_code}"}
            return {"ok": True, "clock": r.json()}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


async def fetch_live_clock() -> dict[str, Any]:
    """
    Always try to read the live collective tally.
    Falls back to last cache, then local ledger preview — never invents.
    """
    from tokenish_engine.agents.neoborg import clock_snapshot
    from tokenish_engine import hive_store

    url = hive_url()
    # Same-origin engine hive when no external Worker URL is set.
    if not url:
        snap = hive_store.snapshot()
        return {
            "agent": "Neoborg",
            "clock": "Live World Counter Clock",
            "online": True,
            "broadcast": hive_opt_in(),
            "source": "engine-hive",
            "saved_tokex": snap.get("saved_tokex") or 0,
            "total_tokex": snap.get("total_tokex") or 0,
            "saved_pct": snap.get("saved_pct") or 0.0,
            "users_online": snap.get("users_online") or 0,
            "nodes": snap.get("nodes") or 0,
            "updated_ts": snap.get("updated_ts"),
            "note": "",
            "hive_opt_in": hive_opt_in(),
            "hive_url": url,
            "node_id": node_id(),
        }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{url}/clock")
            if r.status_code >= 400:
                raise RuntimeError(f"hive HTTP {r.status_code}")
            data = r.json()
    except Exception as exc:
        cached = _load_cache()
        if cached:
            return {
                **cached,
                "online": False,
                "broadcast": False,
                "source": "cache",
                "note": f"hive offline ({exc}); last cached tally",
                "hive_opt_in": hive_opt_in(),
                "hive_url": url,
                "node_id": node_id(),
            }
        local = clock_snapshot()
        return {
            **_empty_clock(source="local", online=False, note=f"hive offline ({exc})"),
            "saved_tokex": local.get("saved_tokex") or 0,
            "total_tokex": local.get("total_tokex") or 0,
            "saved_pct": local.get("saved_pct") or 0.0,
            "updated_ts": local.get("updated_ts"),
            "hive_opt_in": hive_opt_in(),
            "hive_url": url,
            "node_id": node_id(),
        }

    saved = int(data.get("saved_tokex") or 0)
    total = int(data.get("total_tokex") or 0)
    pct = round((saved / total) * 100.0, 2) if total else float(data.get("saved_pct") or 0.0)
    out = {
        "agent": "Neoborg",
        "clock": "Live World Counter Clock",
        "online": True,
        "broadcast": True,
        "source": "hive",
        "saved_tokex": saved,
        "total_tokex": total,
        "saved_pct": pct,
        "users_online": int(data.get("users_online") or data.get("nodes") or 0),
        "nodes": int(data.get("nodes") or 0),
        "updated_ts": data.get("updated_ts") or time.time(),
        "note": "",
        "hive_opt_in": hive_opt_in(),
        "hive_url": url,
        "node_id": node_id(),
    }
    _save_cache(out)
    return out


def broadcast_contribution_sync(saved_tokex: int, total_tokex: int) -> dict[str, Any]:
    """POST one vetted local contribution (sync; for optimize pipeline)."""
    from tokenish_engine import hive_store

    if not hive_opt_in():
        return {"broadcast": False, "reason": "hive opt-in off"}
    try:
        saved = int(saved_tokex)
        total = int(total_tokex)
    except (TypeError, ValueError):
        return {"broadcast": False, "reason": "non-numeric tokex"}
    if saved < 0 or total < 0 or (total > 0 and saved > total):
        return {"broadcast": False, "reason": "impossible tokex relationship"}

    url = hive_url()
    payload = {
        "node_id": node_id(),
        "saved_tokex": saved,
        "total_tokex": total,
        "ts": time.time(),
        "agent": "Neoborg",
    }
    if not url:
        try:
            snap = hive_store.contribute(payload["node_id"], saved, total)
            return {"broadcast": True, "reason": "ok", "hive": snap, "source": "engine-hive"}
        except Exception as exc:
            return {"broadcast": False, "reason": f"engine-hive error: {exc}"}

    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.post(f"{url}/contribute", json=payload)
            if r.status_code >= 400:
                return {"broadcast": False, "reason": f"hive HTTP {r.status_code}", "body": r.text[:200]}
            return {"broadcast": True, "reason": "ok", "hive": r.json(), "source": "remote-hive"}
    except Exception as exc:
        return {"broadcast": False, "reason": f"hive error: {exc}"}


async def broadcast_contribution(saved_tokex: int, total_tokex: int) -> dict[str, Any]:
    return broadcast_contribution_sync(saved_tokex, total_tokex)