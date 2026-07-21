"""
Rainman — tokopt cylinder interrogator.

Factual only: stage participation + TOKEX totals from the pipeline.

Attribution modes:
  - equal_share (legacy): split measured run savings evenly among fired cylinders
  - sequential_delta (preferred when pipeline provides stage_deltas): use
    measured before→after token deltas per cylinder; residual to equal-share
    among fired if deltas under-explain the run total
"""

from __future__ import annotations

from typing import Any


# Known cylinders → stage tag prefixes / exact names that prove they fired.
_CYLINDER_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ingest", ("ingest",)),
    ("lcs", ("lcs", "split_exec", "instruction_follow", "bare", "minimal", "prompt_only")),
    ("hi0", ("hi0",)),
    ("dedupe", ("dedupe_drop_",)),
    ("format_csv", ("format_csv",)),
    ("headroom", ("headroom", "headroom_local")),
    ("its", ("its_drop_", "its_kiosk_block", "faiss_mib")),
    ("its_skipped_fidelity", ("its_skipped_assess", "its_disabled_consent")),
    ("ffmpeg", ("ffmpeg_keyframes_", "ffmpeg_disabled_consent", "ffmpeg_skipped_no_binary", "ffmpeg_failed", "ffmpeg_no_frames")),
    ("pxpipe", ("pxpipe", "pxpipe_dropped")),
    ("tokenizer_gate", ("tokenizer_gate", "shorthand_rejected", "verbatim_fallback", "envelope_gate_reject_", "envelope_fallback_")),
    ("vision", ("vision_images_",)),
    ("passthrough", ("passthrough_short", "passthrough_parity")),
]

CYLINDER_NAMES: tuple[str, ...] = tuple(name for name, _ in _CYLINDER_RULES)


def _stage_hit(stage: str, prefixes: tuple[str, ...]) -> bool:
    return any(stage == p or stage.startswith(p) for p in prefixes)


def interrogate_run(
    *,
    stages: list[str] | None,
    tokex: dict[str, Any] | None,
    its_meta: dict[str, Any] | None = None,
    attachment_warning: str | None = None,
    fidelity_mode: str = "loyalty",
    stage_deltas: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Return a Rainman brief built only from measured inputs.

    When stage_deltas is provided, per-cylinder saved_tokens prefer sequential
    measured deltas (causal-ish ledger). Equal-share remains the fallback and
    is always disclosed in caveats.
    """
    stage_list = [str(s) for s in (stages or [])]
    t = tokex or {}
    total = int(t.get("total_tokex") or t.get("original_tokens") or 0)
    run = int(t.get("tokex_this_run") or t.get("optimized_tokens") or 0)
    saved = int(t.get("saved_tokex") or t.get("saved_tokens") or max(0, total - run))
    pct = float(t.get("saved_pct") or 0.0)
    if total > 0 and "saved_pct" not in t:
        pct = round((saved / total) * 100.0, 2)

    delta_by_cylinder: dict[str, int] = {}
    for row in stage_deltas or []:
        name = str(row.get("cylinder") or "").strip()
        if not name:
            continue
        delta = int(row.get("delta_saved") or 0)
        if delta < 0:
            delta = 0
        delta_by_cylinder[name] = delta_by_cylinder.get(name, 0) + delta

    use_sequential = bool(delta_by_cylinder)
    attribution_mode = "sequential_delta" if use_sequential else "equal_share"

    fired_names: list[str] = []
    preliminary: list[dict[str, Any]] = []
    for name, prefixes in _CYLINDER_RULES:
        hits = [s for s in stage_list if _stage_hit(s, prefixes)]
        fired = bool(hits) or (name in delta_by_cylinder and delta_by_cylinder[name] > 0)
        if fired:
            fired_names.append(name)
        preliminary.append(
            {
                "cylinder": name,
                "fired": fired,
                "stage_tags": hits,
                "saved_tokens": 0,
                "saved_pct_of_run": 0.0,
                "participation_of_fired": 0.0,
                "delta_saved": int(delta_by_cylinder.get(name, 0)),
                "status": "active" if fired else "INACTIVE",
            }
        )

    active = len(fired_names)
    if active and saved > 0:
        if use_sequential:
            assigned = 0
            for row in preliminary:
                if not row["fired"]:
                    continue
                d = int(row["delta_saved"])
                row["saved_tokens"] = d
                assigned += d
            residual = max(0, saved - assigned)
            # If deltas overshoot run total, scale down proportionally.
            if assigned > saved > 0:
                scale = saved / assigned
                for row in preliminary:
                    if row["fired"]:
                        row["saved_tokens"] = int(row["saved_tokens"] * scale)
                assigned = sum(int(r["saved_tokens"]) for r in preliminary if r["fired"])
                residual = max(0, saved - assigned)
            if residual and active:
                base = residual // active
                rem = residual - (base * active)
                for row in preliminary:
                    if not row["fired"]:
                        continue
                    extra = 1 if rem > 0 else 0
                    if rem > 0:
                        rem -= 1
                    row["saved_tokens"] = int(row["saved_tokens"]) + base + extra
            for row in preliminary:
                if not row["fired"]:
                    continue
                row["saved_pct_of_run"] = (
                    round(100.0 * int(row["saved_tokens"]) / saved, 2) if saved else 0.0
                )
                row["participation_of_fired"] = row["saved_pct_of_run"]
        else:
            base = saved // active
            rem = saved - (base * active)
            share_pct = round(100.0 / active, 2)
            for row in preliminary:
                if not row["fired"]:
                    continue
                extra = 1 if rem > 0 else 0
                if rem > 0:
                    rem -= 1
                row["saved_tokens"] = base + extra
                row["saved_pct_of_run"] = share_pct
                row["participation_of_fired"] = share_pct

    its = its_meta or {}
    findings: list[str] = [
        f"stages_observed={len(stage_list)}",
        f"cylinders_fired={active}",
        f"total_tokex={total}",
        f"tokex_this_run={run}",
        f"saved_tokex={saved}",
        f"saved_pct={pct}",
        f"fidelity_mode={fidelity_mode}",
        f"attribution_mode={attribution_mode}",
    ]
    if attachment_warning:
        findings.append(f"attachment_warning={attachment_warning}")
    if its.get("dropped") is not None:
        findings.append(f"its_dropped={its.get('dropped')}")
        findings.append(f"its_kept={its.get('kept')}")

    caveats = [
        "No LLM was used. Numbers come only from tokex + stage tags"
        + (" + sequential stage_deltas." if use_sequential else "."),
    ]
    if use_sequential:
        caveats.append(
            "Per-cylinder saved_tokens prefer measured sequential text/token deltas; "
            "any residual vs run SAVED_TOKEX is equal-shared among fired cylinders."
        )
    else:
        caveats.append(
            "Per-cylinder saved_tokens are equal attributed shares of the measured "
            "run savings among cylinders that fired — not independent before/after probes."
        )

    return {
        "agent": "Rainman",
        "truthful": True,
        "llm_used": False,
        "fidelity_mode": fidelity_mode,
        "attribution_mode": attribution_mode,
        "tokex": {
            "total_tokex": total,
            "tokex_this_run": run,
            "saved_tokex": saved,
            "saved_pct": pct,
        },
        "stages": stage_list,
        "stage_deltas": list(stage_deltas or []),
        "cylinders": preliminary,
        "findings": findings,
        "caveats": caveats,
        "verdict": (
            f"run saved {saved} tokex ({pct}%) with {active} cylinder(s) firing "
            f"[{attribution_mode}]; inactive cylinders marked INACTIVE"
            if total
            else "no measurable tokex on this run"
        ),
    }
