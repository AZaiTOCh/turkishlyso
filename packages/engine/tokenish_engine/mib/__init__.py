"""
Maximally Informative Binarization (MIB) + ITS skill scoring.

Open reimplementation of the Moorcheh-style contingency → C+/C− → RSS path
described in the Tokenish brief. Not a copy of proprietary Moorcheh code.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from tokenish_engine.retrieve.its import contingency_table, mib_binarize


def build_contingency(query_bits: int, doc_bits: int, bits: int = 512) -> dict[str, int]:
    return contingency_table(query_bits, doc_bits, bits)


def compute_c_plus(cont: dict[str, int]) -> float:
    """Desirable information (signal)."""
    a, b, c, d, n = cont["a"], cont["b"], cont["c"], cont["d"], cont.get("N") or sum(cont[k] for k in "abcd")
    if n <= 0:
        return 0.0
    term1 = a * math.log2((a * n) / ((a + b) * (a + c))) if a > 0 and (a + b) and (a + c) else 0.0
    term2 = d * math.log2((d * n) / ((d + b) * (d + c))) if d > 0 and (d + b) and (d + c) else 0.0
    return float(term1 + term2)


def compute_c_minus(cont: dict[str, int]) -> float:
    """Undesirable information (noise)."""
    a, b, c, d, n = cont["a"], cont["b"], cont["c"], cont["d"], cont.get("N") or sum(cont[k] for k in "abcd")
    if n <= 0:
        return 0.0
    term1 = b * math.log2((b * n) / ((b + a) * (b + d))) if b > 0 and (b + a) and (b + d) else 0.0
    term2 = c * math.log2((c * n) / ((c + d) * (c + a))) if c > 0 and (c + d) and (c + a) else 0.0
    return float(term1 + term2)


def retrieval_skill_score(
    query_bin: int | np.ndarray,
    doc_bin: int | np.ndarray,
    *,
    bits: int = 512,
    s_q: float | None = None,
) -> tuple[float, float, float]:
    """
    RSS ≈ (C+ + C−) / S(Q).
    Accepts packed int bitsets (local MIB) or binary arrays.
    """
    if isinstance(query_bin, np.ndarray):
        q = int(np.packbits(query_bin.astype(np.uint8)).tobytes().hex()[:16] or "0", 16)
        # Prefer bit-wise path via mib ints when arrays passed as 0/1 vectors:
        q_bits = 0
        for i, bit in enumerate(query_bin.astype(int).ravel()[:bits]):
            if bit:
                q_bits |= 1 << int(i)
        query_bin = q_bits
    if isinstance(doc_bin, np.ndarray):
        d_bits = 0
        for i, bit in enumerate(doc_bin.astype(int).ravel()[:bits]):
            if bit:
                d_bits |= 1 << int(i)
        doc_bin = d_bits

    cont = build_contingency(int(query_bin), int(doc_bin), bits)
    cont["N"] = bits
    c_plus = compute_c_plus(cont)
    c_minus = compute_c_minus(cont)
    s_q = s_q if s_q is not None else math.log2(bits + 1e-8)
    rss = (c_plus + c_minus) / s_q if s_q else 0.0
    return float(rss), float(c_plus), float(c_minus)


def score_text_pair(query: str, chunk: str, bits: int = 512) -> dict[str, Any]:
    q = mib_binarize(query, bits)
    d = mib_binarize(chunk, bits)
    rss, c_plus, c_minus = retrieval_skill_score(q, d, bits=bits)
    cont = build_contingency(q, d, bits)
    return {
        "rss": rss,
        "c_plus": c_plus,
        "c_minus": c_minus,
        "table": cont,
        "query_bits": q.bit_count(),
        "doc_bits": d.bit_count(),
    }


def simple_bq(vectors: np.ndarray) -> np.ndarray:
    """1-bit sign quantization for float embedding matrices."""
    return (vectors > 0).astype(np.uint8)


__all__ = [
    "build_contingency",
    "compute_c_plus",
    "compute_c_minus",
    "retrieval_skill_score",
    "score_text_pair",
    "simple_bq",
    "mib_binarize",
]
