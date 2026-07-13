"""
Maximally Informative Binarization (MIB) + ITS skill scoring + FAISS binary index.

Open Memtrove-style contingency → C+/C− → RSS path for Tokenish.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from tokenish_engine.mib.faiss_index import TokenishBinaryIndex, rank_chunks_binary, texts_to_binary_matrix
from tokenish_engine.retrieve.its import contingency_table, mib_binarize


def build_contingency(query_bits: int, doc_bits: int, bits: int = 512) -> dict[str, int]:
    return contingency_table(query_bits, doc_bits, bits)


def compute_c_plus(cont: dict[str, int]) -> float:
    a, b, c, d, n = cont["a"], cont["b"], cont["c"], cont["d"], cont.get("N") or sum(cont[k] for k in "abcd")
    if n <= 0:
        return 0.0
    term1 = a * math.log2((a * n) / ((a + b) * (a + c))) if a > 0 and (a + b) and (a + c) else 0.0
    term2 = d * math.log2((d * n) / ((d + b) * (d + c))) if d > 0 and (d + b) and (d + c) else 0.0
    return float(term1 + term2)


def compute_c_minus(cont: dict[str, int]) -> float:
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
    if isinstance(query_bin, np.ndarray):
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
    return (vectors > 0).astype(np.uint8)


__all__ = [
    "TokenishBinaryIndex",
    "build_contingency",
    "compute_c_plus",
    "compute_c_minus",
    "mib_binarize",
    "rank_chunks_binary",
    "retrieval_skill_score",
    "score_text_pair",
    "simple_bq",
    "texts_to_binary_matrix",
]
