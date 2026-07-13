"""
Open ITS-style retrieval skill scoring (Moorcheh-inspired, not proprietary MIB).

Uses binary hashing of text chunks + contingency-table skill score to drop
low-relevance chunks before they enter #D.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from tokenish_engine.config import settings


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def _bit_vector(text: str, bits: int = 256) -> int:
    """Hash bag-of-tokens into a compact bitset."""
    vec = 0
    for tok in _tokenize(text):
        h = int(hashlib.sha1(tok.encode("utf-8")).hexdigest(), 16)
        vec |= 1 << (h % bits)
    return vec


def contingency(a: int, b: int, bits: int = 256) -> tuple[int, int, int, int]:
    """Return (hits, false_alarms, misses, correct_negatives)."""
    hits = (a & b).bit_count()
    false_alarms = (a & ~b).bit_count()
    misses = (~a & b).bit_count()
    correct_neg = bits - hits - false_alarms - misses
    return hits, false_alarms, misses, correct_neg


def its_skill_score(query: str, chunk: str, bits: int = 256) -> float:
    """
    Information-theoretic style skill score in [-1, 1]-ish range.
    Positive => skillful match; low/negative => hedge / noise.
    """
    q = _bit_vector(query, bits)
    c = _bit_vector(chunk, bits)
    a, b, c_miss, d = contingency(q, c, bits)
    # Heidke-like skill: (ad - bc) / ((a+c)(b+d) + (a+b)(c+d) + eps) simplified
    num = (a * d) - (b * c_miss)
    den = ((a + c_miss) * (b + d)) + ((a + b) * (c_miss + d)) + 1e-9
    return float(num) / float(den)


@dataclass
class GatedDocument:
    text: str
    dropped: int
    kept: int
    scores: list[float]


def gate_document(
    query: str,
    document: str,
    *,
    threshold: float | None = None,
    enabled: bool = True,
    min_chunk_chars: int = 80,
) -> GatedDocument:
    """
    Split document into chunks; drop low-ITS chunks.
    If everything would drop, keep original (honesty fallback with full data).
    """
    if not enabled or not document.strip() or not query.strip():
        return GatedDocument(text=document, dropped=0, kept=1, scores=[])

    thr = settings.its_threshold if threshold is None else threshold
    # Prefer page breaks, else paragraphs
    if "--- PAGE BREAK ---" in document:
        chunks = [c.strip() for c in document.split("--- PAGE BREAK ---") if c.strip()]
        joiner = "\n--- PAGE BREAK ---\n"
    else:
        chunks = [c.strip() for c in re.split(r"\n\s*\n", document) if c.strip()]
        joiner = "\n\n"

    if len(chunks) <= 1:
        return GatedDocument(text=document, dropped=0, kept=len(chunks), scores=[])

    kept: list[str] = []
    scores: list[float] = []
    dropped = 0
    for ch in chunks:
        if len(ch) < min_chunk_chars:
            kept.append(ch)
            scores.append(1.0)
            continue
        score = its_skill_score(query, ch)
        scores.append(score)
        if score >= thr:
            kept.append(ch)
        else:
            dropped += 1

    if not kept:
        # Never return empty #D — honesty means keep original if gate is too aggressive
        return GatedDocument(text=document, dropped=0, kept=len(chunks), scores=scores)

    return GatedDocument(text=joiner.join(kept), dropped=dropped, kept=len(kept), scores=scores)
