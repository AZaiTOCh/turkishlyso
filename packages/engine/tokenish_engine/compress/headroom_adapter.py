"""
Headroom-inspired answer-preserving context compressor.

Tries optional `headroom` package; falls back to a local deterministic compressor
that never mutates content marked as document/#D bodies when used via pipeline
guards (caller must only pass compressible context slices).
"""

from __future__ import annotations

import re

from tokenish_engine.meters.tokens import count_tokens


def _local_compress(text: str) -> str:
    """Conservative whitespace/redundant-line compression for logs/tool dumps."""
    if not text:
        return text
    # Collapse runs of blank lines
    out = re.sub(r"\n{3,}", "\n\n", text)
    # Deduplicate consecutive identical lines
    lines = out.splitlines()
    deduped: list[str] = []
    prev = None
    for ln in lines:
        if ln == prev:
            continue
        deduped.append(ln)
        prev = ln
    # Trim trailing spaces
    return "\n".join(l.rstrip() for l in deduped).strip() + ("\n" if text.endswith("\n") else "")


def compress_context(text: str, *, min_tokens: int = 800) -> tuple[str, bool, str]:
    """
    Compress context if beneficial.
    Returns (text, applied, stage_name).
    """
    if not text or count_tokens(text) < min_tokens:
        return text, False, ""

    # Prefer real Headroom if installed
    try:
        import headroom  # type: ignore

        if hasattr(headroom, "compress"):
            packed = headroom.compress(text)
        elif hasattr(headroom, "compress_text"):
            packed = headroom.compress_text(text)
        else:
            packed = None
        if isinstance(packed, str) and count_tokens(packed) < count_tokens(text):
            return packed, True, "headroom"
    except Exception:
        pass

    local = _local_compress(text)
    if count_tokens(local) < count_tokens(text):
        return local, True, "headroom_local"
    return text, False, ""
