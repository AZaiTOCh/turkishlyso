"""
Memtrove-inspired Information-Theoretic Scoring (open reimplementation).

Sources decoded into this module:
  - Architecture brief: MIB → contingency (a,b,c,d) → ITS / RSS skill score,
    CPR honesty gate, Drift-Terminator pruning, Kiosk Mode.
  - Local Memtrove-compatible semantics (optional cloud SDK via memtrove_client).

This is an open approximation for local gating before LLM context assembly.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

from tokenish_engine.config import settings


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())


def mib_binarize(text: str, bits: int = 512) -> int:
    """
    Open MIB-style binarization: map tokens → bit positions via hashing.

    Not Memtrove's proprietary transform — a local stand-in that preserves the
    bitwise contingency workflow from the decode brief.
    """
    vec = 0
    for tok in _tokenize(text):
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        # Multi-hash for denser codes (Maximally Informative-ish coverage)
        for salt in (0, 1, 2):
            idx = (h + salt * 0x9E3779B97F4A7C15) % bits
            vec |= 1 << idx
    return vec


def contingency_table(query_bits: int, doc_bits: int, bits: int = 512) -> dict[str, int]:
    """
    Contingency table for binary codes:
      a = hits            (q=1, d=1)
      b = false alarms    (q=1, d=0)
      c = misses          (q=0, d=1)
      d = correct neg.    (q=0, d=0)
    """
    a = (query_bits & doc_bits).bit_count()
    b = (query_bits & ~doc_bits).bit_count()
    c = (~query_bits & doc_bits).bit_count()
    # mask to bit-width
    mask = (1 << bits) - 1 if bits < 62 else None
    if mask is not None:
        # for safety with python ints, recompute d from identity
        d = bits - a - b - c
    else:
        d = bits - a - b - c
    return {"a": a, "b": b, "c": c, "d": max(0, d)}


def peirce_skill_score(a: int, b: int, c: int, d: int) -> float:
    """PSS / True Skill Statistic — can be negative (honest noise signal)."""
    den = (a + c) * (b + d)
    if den == 0:
        return 0.0
    return (a * d - b * c) / float(den)


def heidke_skill_score(a: int, b: int, c: int, d: int) -> float:
    """Heidke Skill Score (HSS) used as ITS / RSS gatekeeper in the brief."""
    n = a + b + c + d
    if n == 0:
        return 0.0
    expected = ((a + c) * (a + b) + (b + d) * (c + d)) / float(n)
    den = n - expected
    if abs(den) < 1e-12:
        return 0.0
    return (a + d - expected) / den


def critical_performance_ratio(a: int, b: int, c: int, d: int) -> float:
    """
    CPR — signal/(signal+noise) style honesty ratio.
    Low CPR ⇒ hedged / unskilled retrieval ⇒ Kiosk / prune.
    """
    signal = float(a)
    noise = float(b + c)
    return signal / (signal + noise + 1e-9)


def relevance_label(score: float, threshold: float) -> str:
    if score >= max(threshold, 0.55):
        return "High Relevance"
    if score >= threshold:
        return "Medium Relevance"
    if score >= threshold * 0.5:
        return "Low Relevance"
    return "Noise / Hedge"


def its_score_pair(query: str, chunk: str, bits: int = 512) -> dict[str, float | str | dict]:
    q = mib_binarize(query, bits)
    d = mib_binarize(chunk, bits)
    table = contingency_table(q, d, bits)
    hss = heidke_skill_score(table["a"], table["b"], table["c"], table["d"])
    pss = peirce_skill_score(table["a"], table["b"], table["c"], table["d"])
    cpr = critical_performance_ratio(table["a"], table["b"], table["c"], table["d"])
    # Memtrove-style C+/C− RSS (info-theoretic) blended with HSS/PSS
    from tokenish_engine.mib import retrieval_skill_score

    rss, c_plus, c_minus = retrieval_skill_score(q, d, bits=bits)
    its = 0.45 * hss + 0.25 * pss + 0.30 * max(-1.0, min(1.0, rss))
    thr = settings.its_threshold
    return {
        "its": its,
        "hss": hss,
        "pss": pss,
        "cpr": cpr,
        "rss": rss,
        "c_plus": c_plus,
        "c_minus": c_minus,
        "table": table,
        "label": relevance_label(its, thr),
    }


def its_skill_score(query: str, chunk: str, bits: int = 512) -> float:
    return float(its_score_pair(query, chunk, bits)["its"])


@dataclass
class GatedDocument:
    text: str
    dropped: int
    kept: int
    scores: list[float]
    labels: list[str] = field(default_factory=list)
    kiosk_blocked: bool = False
    details: list[dict] = field(default_factory=list)


def gate_document(
    query: str,
    document: str,
    *,
    threshold: float | None = None,
    enabled: bool = True,
    min_chunk_chars: int = 80,
    kiosk_mode: bool = False,
) -> GatedDocument:
    """
    Split document into chunks; drop low-ITS chunks (Drift-Terminator style).
    Kiosk Mode: if no chunk clears threshold, block (honesty) instead of guessing.
    """
    if not enabled or not document.strip() or not query.strip():
        return GatedDocument(text=document, dropped=0, kept=1, scores=[])

    thr = settings.its_threshold if threshold is None else threshold
    if "--- PAGE BREAK ---" in document:
        chunks = [c.strip() for c in document.split("--- PAGE BREAK ---") if c.strip()]
        joiner = "\n--- PAGE BREAK ---\n"
    else:
        chunks = [c.strip() for c in re.split(r"\n\s*\n", document) if c.strip()]
        joiner = "\n\n"

    if len(chunks) <= 1:
        if len(chunks) == 1:
            detail = its_score_pair(query, chunks[0])
            score = float(detail["its"])
            if kiosk_mode and score < thr:
                return GatedDocument(
                    text="",
                    dropped=1,
                    kept=0,
                    scores=[score],
                    labels=[str(detail["label"])],
                    kiosk_blocked=True,
                    details=[detail],
                )
        return GatedDocument(text=document, dropped=0, kept=len(chunks), scores=[])

    # FAISS binary prefilter when many chunks — then ITS on shortlist
    candidate_idxs = list(range(len(chunks)))
    faiss_meta: dict = {}
    if getattr(settings, "enable_faiss_mib", True) and len(chunks) > 8:
        try:
            from tokenish_engine.mib import rank_chunks_binary

            top_k = min(int(getattr(settings, "faiss_top_k", 24)), len(chunks))
            ranked = rank_chunks_binary(
                query,
                chunks,
                bits=int(getattr(settings, "faiss_mib_bits", 512)),
                top_k=top_k,
            )
            candidate_idxs = [i for i, _d, _t in ranked]
            faiss_meta = {
                "faiss_prefilter": True,
                "faiss_top_k": top_k,
                "faiss_candidates": len(candidate_idxs),
                "faiss_backend": "faiss_or_numpy",
            }
        except Exception as exc:
            faiss_meta = {"faiss_prefilter": False, "faiss_error": str(exc)[:120]}

    kept: list[str] = []
    scores: list[float] = []
    labels: list[str] = []
    details: list[dict] = []
    dropped = 0
    seen: set[int] = set()
    for idx in candidate_idxs:
        if idx in seen or idx < 0 or idx >= len(chunks):
            continue
        seen.add(idx)
        ch = chunks[idx]
        detail = its_score_pair(query, ch)
        if faiss_meta:
            detail = {**detail, **faiss_meta}
        score = float(detail["its"])
        scores.append(score)
        labels.append(str(detail["label"]))
        details.append(detail)
        if len(ch) < min_chunk_chars:
            kept.append(ch)
            continue
        cpr = float(detail["cpr"])
        if score >= thr and cpr >= 0.35:
            kept.append(ch)
        else:
            dropped += 1

    # Count non-candidate chunks as dropped when FAISS shortlisted
    if faiss_meta.get("faiss_prefilter"):
        dropped += max(0, len(chunks) - len(seen))

    if not kept:
        if kiosk_mode:
            return GatedDocument(
                text="",
                dropped=dropped or len(chunks),
                kept=0,
                scores=scores,
                labels=labels,
                kiosk_blocked=True,
                details=details,
            )
        return GatedDocument(
            text=document,
            dropped=0,
            kept=len(chunks),
            scores=scores,
            labels=labels,
            details=details,
        )

    return GatedDocument(
        text=joiner.join(kept),
        dropped=dropped,
        kept=len(kept),
        scores=scores,
        labels=labels,
        details=details,
    )


def drift_terminator_rank(query: str, nodes: list[str], threshold: float | None = None) -> list[dict]:
    """Rank graph-like text nodes; terminate low-skill branches."""
    thr = settings.its_threshold if threshold is None else threshold
    ranked = []
    for node in nodes:
        detail = its_score_pair(query, node)
        skill = float(detail["its"])
        if skill < thr:
            ranked.append({**detail, "text": node[:200], "action": "terminate_branch"})
        else:
            ranked.append({**detail, "text": node[:200], "action": "augment_context"})
    ranked.sort(key=lambda x: float(x["its"]), reverse=True)
    return ranked
