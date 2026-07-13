from __future__ import annotations

_ENCODER = None


def _encoder():
    global _ENCODER
    if _ENCODER is None:
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODER = False
    return _ENCODER


def count_tokens(text: str) -> int:
    if not text:
        return 0
    enc = _encoder()
    if enc:
        return len(enc.encode(text))
    return max(1, len(text) // 4)
