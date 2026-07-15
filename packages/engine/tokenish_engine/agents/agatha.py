"""
Agatha — tokopt archive / performance ledger.

Primary archive: one markdown brief per run under ~/.tokenish/output/runs/
Lifetime scoreboard: ~/.tokenish/output/scoreboard.json

Legacy agatha.db writes are disabled (v0.5) to avoid double-saving.
Neoborg must not re-archive the same brief — only hive number cross-vet.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tokenish_engine.agents.rainman import CYLINDER_NAMES
from tokenish_engine.settings_store import tokenish_home


def output_dir() -> Path:
    path = tokenish_home() / "output"
    path.mkdir(parents=True, exist_ok=True)
    (path / "runs").mkdir(parents=True, exist_ok=True)
    return path


def _scoreboard_path() -> Path:
    return output_dir() / "scoreboard.json"


def _empty_scoreboard() -> dict[str, Any]:
    cyl = {
        name: {"saved_tokens": 0, "fires": 0, "status": "INACTIVE"}
        for name in CYLINDER_NAMES
    }
    return {
        "agent": "Agatha",
        "updated_ts": None,
        "runs": 0,
        "totals": {"saved_tokens": 0, "total_tokex": 0, "tokex_this_run": 0},
        "cylinders": cyl,
    }


def load_scoreboard() -> dict[str, Any]:
    path = _scoreboard_path()
    if not path.exists():
        return _empty_scoreboard()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_scoreboard()
    # Ensure all known cylinders exist.
    base = _empty_scoreboard()
    base.update({k: data.get(k, base[k]) for k in ("updated_ts", "runs", "totals")})
    for name in CYLINDER_NAMES:
        row = (data.get("cylinders") or {}).get(name) or {}
        base["cylinders"][name] = {
            "saved_tokens": int(row.get("saved_tokens") or 0),
            "fires": int(row.get("fires") or 0),
            "status": "active" if int(row.get("fires") or 0) else "INACTIVE",
        }
    return base


def _save_scoreboard(data: dict[str, Any]) -> None:
    _scoreboard_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _brief_markdown(brief: dict[str, Any], run_id: str, ts: float) -> str:
    tokex = brief.get("tokex") or {}
    lines = [
        f"# Rainman brief `{run_id}`",
        "",
        f"- ts: {ts}",
        f"- fidelity: {brief.get('fidelity_mode') or 'loyalty'}",
        f"- total_tokex: {tokex.get('total_tokex')}",
        f"- tokex_this_run: {tokex.get('tokex_this_run')}",
        f"- saved_tokex: {tokex.get('saved_tokex')}",
        f"- saved_pct: {tokex.get('saved_pct')}",
        f"- verdict: {brief.get('verdict')}",
        "",
        "## cylinders",
        "",
        "| cylinder | status | saved tokens | % of run |",
        "|---|---|---:|---:|",
    ]
    for row in brief.get("cylinders") or []:
        status = row.get("status") or ("active" if row.get("fired") else "INACTIVE")
        saved = int(row.get("saved_tokens") or 0) if row.get("fired") else "INACTIVE"
        pct = row.get("saved_pct_of_run") if row.get("fired") else "—"
        lines.append(f"| {row.get('cylinder')} | {status} | {saved} | {pct} |")
    lines.extend(["", "## caveats", ""])
    for c in brief.get("caveats") or []:
        lines.append(f"- {c}")
    lines.append("")
    return "\n".join(lines)


def archive_rainman_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Persist one markdown brief + update lifetime scoreboard. No SQLite."""
    tokex = brief.get("tokex") or {}
    ts = time.time()
    run_id = str(int(ts * 1000))
    out = output_dir()
    md_path = out / "runs" / f"{run_id}.md"
    md_path.write_text(_brief_markdown(brief, run_id, ts), encoding="utf-8")

    board = load_scoreboard()
    board["runs"] = int(board.get("runs") or 0) + 1
    board["updated_ts"] = ts
    totals = board.setdefault("totals", {"saved_tokens": 0, "total_tokex": 0, "tokex_this_run": 0})
    totals["saved_tokens"] = int(totals.get("saved_tokens") or 0) + int(tokex.get("saved_tokex") or 0)
    totals["total_tokex"] = int(totals.get("total_tokex") or 0) + int(tokex.get("total_tokex") or 0)
    totals["tokex_this_run"] = int(totals.get("tokex_this_run") or 0) + int(tokex.get("tokex_this_run") or 0)

    cyls = board.setdefault("cylinders", {})
    for row in brief.get("cylinders") or []:
        name = str(row.get("cylinder") or "unknown")
        slot = cyls.setdefault(name, {"saved_tokens": 0, "fires": 0, "status": "INACTIVE"})
        if row.get("fired"):
            slot["fires"] = int(slot.get("fires") or 0) + 1
            slot["saved_tokens"] = int(slot.get("saved_tokens") or 0) + int(row.get("saved_tokens") or 0)
            slot["status"] = "active"
        else:
            slot["status"] = "active" if int(slot.get("fires") or 0) else "INACTIVE"
    _save_scoreboard(board)

    return {
        "agent": "Agatha",
        "archived": True,
        "run_id": run_id,
        "md": str(md_path),
        "scoreboard": str(_scoreboard_path()),
        "db": None,
        "ts": ts,
    }


def cylinder_rollups() -> list[dict[str, Any]]:
    board = load_scoreboard()
    totals_saved = int((board.get("totals") or {}).get("saved_tokens") or 0) or 1
    rows = []
    for name in CYLINDER_NAMES:
        slot = (board.get("cylinders") or {}).get(name) or {}
        saved = int(slot.get("saved_tokens") or 0)
        fires = int(slot.get("fires") or 0)
        rows.append(
            {
                "cylinder": name,
                "fires": fires,
                "saved_tokens": saved,
                "saved_pct_lifetime": round((saved / totals_saved) * 100.0, 2) if fires else 0.0,
                "status": "active" if fires else "INACTIVE",
            }
        )
    return rows


def scoreboard_payload() -> dict[str, Any]:
    board = load_scoreboard()
    rows = cylinder_rollups()
    totals = board.get("totals") or {}
    return {
        "agent": "Agatha",
        "runs": board.get("runs") or 0,
        "updated_ts": board.get("updated_ts"),
        "totals": totals,
        "cylinders": rows,
        "output_dir": str(output_dir()),
    }


def recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    runs = sorted((output_dir() / "runs").glob("*.md"), reverse=True)
    out = []
    for path in runs[: max(1, limit)]:
        out.append({"run_id": path.stem, "md": str(path), "ts": path.stat().st_mtime})
    return out
