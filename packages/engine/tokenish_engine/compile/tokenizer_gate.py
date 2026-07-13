from __future__ import annotations

import re

from tokenish_engine.meters.tokens import count_tokens

_VOWEL_STRIP_HINT = re.compile(r"\b[b-df-hj-np-tv-z]{3,}\b", re.I)


def reject_char_shorthand(text: str) -> bool:
    """True if text looks like vowel-stripped stenography (forbidden)."""
    if not text:
        return False
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 3:
        return False
    strippedish = sum(
        1
        for w in words
        if _VOWEL_STRIP_HINT.fullmatch(w) and not re.search(r"[aeiouy]", w, re.I)
    )
    return strippedish / max(1, len(words)) >= 0.35


def apply_if_cheaper(before: str, after: str) -> str:
    if count_tokens(after) < count_tokens(before):
        return after
    return before
