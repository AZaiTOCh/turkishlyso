"""
Rainman — tokopt cylinder interrogator.

Factual only: stage participation + TOKEX totals from the pipeline.
Per-cylinder token figures are *equal attributed share* of the measured run
savings among cylinders that fired — not independent causal probes.
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
    ("pxpipe", ("pxpipe", "pxpipe_dropped")),
    ("tokenizer_gate", ("tokenizer_gate", "shorthand_rejected", "verbatim_fallback")),
    ("vision", ("vision_images_",)),
    ("passthrough", ("passthrough_short",)),
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
) -> dict[str, Any]:
    """
    Return a Rainman brief built only from measured inputs.

    Every run total is from TokexReport / stage tags. Missing data stays null.
    Per-cylinder saved_tokens = equal share of this run's saved_tokex across
    fired cylinders (documented attribution — not a separate meter).
    """
    stage_list = [str(s) for s in (stages or [])]
    t = tokex or {}
    total = int(t.get("total_tokex") or t.get("original_tokens") or 0)
    run = int(t.get("tokex_this_run") or t.get("optimized_tokens") or 0)
    saved = int(t.get("saved_tokex") or t.get("saved_tokens") or max(0, total - run))
    pct = float(t.get("saved_pct") or 0.0)
    if total > 0 and "saved_pct" not in t:
        pct = round((saved / total) * 100.0, 2)

    fired_names: list[str] = []
    preliminary: list[dict[str, Any]] = []
    for name, prefixes in _CYLINDER_RULES:
        hits = [s for s in stage_list if _stage_hit(s, prefixes)]
        fired = bool(hits)
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
                "status": "active" if fired else "INACTIVE",
            }
        )

    active = len(fired_names)
    if active and saved > 0:
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
    ]
    if attachment_warning:
        findings.append(f"attachment_warning={attachment_warning}")
    if its.get("dropped") is not None:
        findings.append(f"its_dropped={its.get('dropped')}")
        findings.append(f"its_kept={its.get('kept')}")

    caveats = [
        "Per-cylinder saved_tokens are equal attributed shares of the measured "
        "run savings among cylinders that fired — not independent before/after probes.",
        "No LLM was used. Numbers come only from tokex + stage tags.",
    ]

    return {
        "agent": "Rainman",
        "truthful": True,
        "llm_used": False,
        "fidelity_mode": fidelity_mode,
        "tokex": {
            "total_tokex": total,
            "tokex_this_run": run,
            "saved_tokex": saved,
            "saved_pct": pct,
        },
        "stages": stage_list,
        "cylinders": preliminary,
        "findings": findings,
        "caveats": caveats,
        "verdict": (
            f"run saved {saved} tokex ({pct}%) with {active} cylinder(s) firing; "
            "inactive cylinders marked INACTIVE"
            if total
            else "no measurable tokex on this run"
        ),
    }
