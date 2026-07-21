"""Tests for Rainman sequential deltas, envelope gate fallback, ffmpeg cylinder."""

from __future__ import annotations

from tokenish_engine.agents.rainman import interrogate_run
from tokenish_engine.compile.lcs import pick_gated_envelope, rank_envelopes
from tokenish_engine.media.ffmpeg_cylinder import is_temporal_media, sample_media_frames
from tokenish_engine.pipeline import optimize


def test_rank_envelopes_orders_by_tokens():
    ranked = rank_envelopes(
        [
            ("long", "word " * 200),
            ("short", "hi"),
            ("mid", "word " * 40),
        ]
    )
    assert ranked[0][0] == "short"
    assert ranked[-1][0] == "long"


def test_pick_gated_envelope_falls_back():
    baseline = "baseline " * 50
    # First candidate longer than baseline → gate reject; second cheaper → keep.
    stage, text, extras = pick_gated_envelope(
        [
            ("bloated", baseline + " " + ("extra " * 80)),
            ("tight", "ok"),
        ],
        baseline=baseline,
        min_fallbacks=2,
    )
    assert stage == "tight"
    assert text == "ok"
    assert any(e.startswith("envelope_gate_reject_") for e in extras)


def test_rainman_sequential_delta_attribution():
    brief = interrogate_run(
        stages=["ingest", "lcs", "dedupe_drop_2", "hi0", "split_exec"],
        tokex={"total_tokex": 1000, "tokex_this_run": 700, "saved_tokex": 300, "saved_pct": 30.0},
        stage_deltas=[
            {"cylinder": "dedupe", "tokens_before": 900, "tokens_after": 650, "delta_saved": 250},
            {"cylinder": "hi0", "tokens_before": 650, "tokens_after": 620, "delta_saved": 30},
        ],
    )
    assert brief["attribution_mode"] == "sequential_delta"
    by_name = {c["cylinder"]: c for c in brief["cylinders"]}
    assert by_name["dedupe"]["saved_tokens"] >= by_name["hi0"]["saved_tokens"]
    assert by_name["dedupe"]["delta_saved"] == 250


def test_ffmpeg_disabled_by_default_marks_consent_stage():
    # Minimal GIF89a header-ish bytes — cylinder should not apply when disabled.
    tiny = b"GIF89a" + b"\x00" * 32
    out = sample_media_frames("clip.gif", tiny, enabled=False)
    assert out["applied"] is False
    assert out["stage"] == "ffmpeg_disabled_consent"


def test_is_temporal_media():
    assert is_temporal_media("a.GIF")
    assert is_temporal_media("x.mp4")
    assert not is_temporal_media("x.png")


def test_optimize_accepts_enable_ffmpeg_flag():
    result = optimize(
        prompt="what is in this clip?",
        files=[("note.txt", b"hello media placeholder")],
        enable_ffmpeg=False,
        enable_pxpipe=False,
        enable_its=False,
    )
    assert result.rainman.get("agent") == "Rainman"
    assert "attribution_mode" in result.rainman
