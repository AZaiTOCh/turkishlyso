"""
FAISS binary index for Memtrove-style MIB retrieval.

Uses faiss.IndexBinaryFlat (Hamming) over packed MIB bit vectors.
Falls back to pure-numpy Hamming if faiss is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tokenish_engine.retrieve.its import mib_binarize


def _bits_to_uint8(bit_int: int, nbits: int) -> np.ndarray:
    """Pack a Python int bitset into uint8 array length nbits/8 for FAISS."""
    nbytes = nbits // 8
    out = np.zeros(nbytes, dtype=np.uint8)
    for i in range(nbytes):
        out[i] = (bit_int >> (i * 8)) & 0xFF
    return out


def texts_to_binary_matrix(texts: list[str], bits: int = 512) -> np.ndarray:
    rows = [_bits_to_uint8(mib_binarize(t, bits), bits) for t in texts]
    return np.vstack(rows).astype(np.uint8)


@dataclass
class BinarySearchHit:
    index: int
    distance: int


class TokenishBinaryIndex:
    """FAISS IndexBinaryFlat wrapper with numpy Hamming fallback."""

    def __init__(self, bits: int = 512):
        if bits % 8 != 0:
            raise ValueError("bits must be divisible by 8")
        self.bits = bits
        self._faiss = None
        self._index = None
        self._matrix: np.ndarray | None = None
        try:
            import faiss  # type: ignore

            self._faiss = faiss
            self._index = faiss.IndexBinaryFlat(bits)
        except Exception:
            self._faiss = None
            self._index = None

    @property
    def backend(self) -> str:
        return "faiss" if self._index is not None else "numpy"

    def add(self, binary_vectors: np.ndarray) -> None:
        binary_vectors = np.ascontiguousarray(binary_vectors.astype(np.uint8))
        if self._index is not None:
            self._index.add(binary_vectors)
        self._matrix = (
            binary_vectors
            if self._matrix is None
            else np.vstack([self._matrix, binary_vectors])
        )

    def add_texts(self, texts: list[str]) -> None:
        self.add(texts_to_binary_matrix(texts, self.bits))

    def search(self, query_bin: np.ndarray, k: int = 10) -> list[BinarySearchHit]:
        query_bin = np.ascontiguousarray(query_bin.astype(np.uint8).reshape(1, -1))
        k = max(1, k)
        if self._index is not None and self._index.ntotal > 0:
            dists, idxs = self._index.search(query_bin, min(k, self._index.ntotal))
            hits: list[BinarySearchHit] = []
            for d, i in zip(dists[0].tolist(), idxs[0].tolist()):
                if i < 0:
                    continue
                hits.append(BinarySearchHit(index=int(i), distance=int(d)))
            return hits
        if self._matrix is None or len(self._matrix) == 0:
            return []
        # Numpy Hamming: popcount XOR per row
        q = query_bin[0]
        xor = np.bitwise_xor(self._matrix, q)
        # popcount via unpackbits
        distances = np.unpackbits(xor, axis=1).sum(axis=1)
        order = np.argsort(distances)[:k]
        return [BinarySearchHit(index=int(i), distance=int(distances[i])) for i in order]

    def search_text(self, query: str, k: int = 10) -> list[BinarySearchHit]:
        q = _bits_to_uint8(mib_binarize(query, self.bits), self.bits)
        return self.search(q, k=k)


def rank_chunks_binary(
    query: str,
    chunks: list[str],
    *,
    bits: int = 512,
    top_k: int = 24,
) -> list[tuple[int, int, str]]:
    """
    Return [(chunk_index, hamming_distance, chunk_text), ...] best-first.
    """
    if not chunks:
        return []
    index = TokenishBinaryIndex(bits=bits)
    index.add_texts(chunks)
    hits = index.search_text(query, k=min(top_k, len(chunks)))
    return [(h.index, h.distance, chunks[h.index]) for h in hits if 0 <= h.index < len(chunks)]
