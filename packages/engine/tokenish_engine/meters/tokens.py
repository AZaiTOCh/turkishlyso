from __future__ import annotations

_ENCODER = None
_TOKENIZER_NAME = "char/4-fallback"


def _encoder():
    global _ENCODER, _TOKENIZER_NAME
    if _ENCODER is None:
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding("cl100k_base")
            _TOKENIZER_NAME = "tiktoken/cl100k_base"
        except Exception:
            _ENCODER = False
            _TOKENIZER_NAME = "char/4-fallback"
    return _ENCODER


def tokenizer_name() -> str:
    _encoder()
    return _TOKENIZER_NAME


def count_tokens(text: str) -> int:
    if not text:
        return 0
    enc = _encoder()
    if enc:
        return len(enc.encode(text))
    return max(1, (len(text) + 3) // 4)
