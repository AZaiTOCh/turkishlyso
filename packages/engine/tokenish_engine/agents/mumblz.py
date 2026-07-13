"""
Mumblz — History title agent.

Reads a full dialog and picks the two most suitable Title Case words
for the History label (no vowel stripping).
"""

from __future__ import annotations

import re
from collections import Counter

_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this",
    "these", "those", "to", "of", "in", "on", "for", "with", "as", "by", "at",
    "from", "into", "about", "over", "after", "before", "between", "is", "are",
    "was", "were", "be", "been", "being", "it", "its", "i", "you", "we", "they",
    "he", "she", "my", "your", "our", "their", "me", "him", "her", "them",
    "do", "does", "did", "doing", "done", "have", "has", "had", "having",
    "will", "would", "can", "could", "should", "may", "might", "must", "not",
    "no", "yes", "so", "very", "just", "also", "only", "more", "most", "some",
    "any", "all", "each", "every", "both", "few", "other", "such", "own",
    "same", "too", "out", "up", "down", "off", "again", "further", "once",
    "here", "there", "when", "where", "why", "how", "what", "which", "who",
    "whom", "whose", "please", "thanks", "thank", "attached", "attachment",
    "document", "documents", "file", "files", "pdf", "image", "images", "new",
    "want", "need", "make", "get", "like", "using", "used", "use", "based",
    "following", "below", "above", "one", "two", "three", "first", "second",
    "final", "generate", "generated", "provide", "provided", "deeply", "whole",
    "check", "checked", "online", "sources", "source", "trusted", "relevant",
    "everything", "something", "anything", "page", "pages", "part", "parts",
    "color", "colour", "colors", "colours",
}

_TOPIC_MAP: list[tuple[re.Pattern[str], str, int]] = [
    (re.compile(r"unicombinator|freefactorial|freesar|superfreefactorial|g[- ]?triangle", re.I), "Combinatorics", 12),
    (re.compile(r"\bgveb\b|waldo|raphael|bosch|visual exhaustion|grounded visual", re.I), "Benchmark", 12),
    (re.compile(r"palette|color|colours?|chiaroscuro|brushstroke|painterly|chromatic", re.I), "Chromatic", 10),
    (re.compile(r"quantum|cryptograph|shor|grover", re.I), "Quantum", 9),
    (re.compile(r"peer review|adversar|critique|auditor", re.I), "Critique", 9),
    (re.compile(r"exec(utive)?\s*summary|one[- ]?page|brief", re.I), "Digest", 8),
    (re.compile(r"fact[- ]?check|vetting|validity|verify|verification", re.I), "Vetting", 8),
    (re.compile(r"token|tokex|multimodal|llm|benchmark", re.I), "Tokens", 7),
    (re.compile(r"urban|street|parking|dusk|cityscape|nocturne", re.I), "Cityscape", 8),
    (re.compile(r"animation|cel[- ]?shad|cartoon|character", re.I), "Animation", 8),
    (re.compile(r"mathematic|formula|permutation|factorial|subset", re.I), "Mathcraft", 7),
    (re.compile(r"synthesis|integrat", re.I), "Synthesis", 6),
    (re.compile(r"assess|analysis|analyze|analyse", re.I), "Assessment", 5),
]

_TASK_MAP: list[tuple[re.Pattern[str], str, int]] = [
    (re.compile(r"adversar|peer review|critique", re.I), "Critique", 10),
    (re.compile(r"fact[- ]?check|vet|valid", re.I), "Audit", 9),
    (re.compile(r"summar|brief|exec", re.I), "Digest", 8),
    (re.compile(r"break\s*down|ratio|style|pattern|color", re.I), "Breakdown", 8),
    (re.compile(r"synthes", re.I), "Synthesis", 7),
    (re.compile(r"assess|analy", re.I), "Scrutiny", 6),
    (re.compile(r"compare|contrast", re.I), "Contrast", 6),
]

_DEFAULT_WORDS = [
    "Scrutiny", "Digest", "Breakdown", "Synthesis", "Contrast",
    "Framework", "Signalcraft", "Threadmark", "Spotlight", "Blueprint",
]

_STYLE_WORDS = {
    "urban", "cinematic", "painterly", "quantum", "visual", "grounded",
    "combinatorial", "adversarial", "executive", "academic", "critical",
    "spectral", "nocturne", "chrome", "verdant", "crimson", "chromatic",
    "framework", "benchmark", "cityscape", "animation",
}

_TITLE_WORDS = 2


def strip_vowels_word(word: str) -> str:
    """Deprecated no-op kept for import compatibility — returns title-cased word."""
    return _title_case(re.sub(r"[^A-Za-z0-9-]", "", word or "")) or (word or "")


def mumblz_title(title: str) -> str:
    """Normalize to at most two Title Case words (no vowel stripping)."""
    parts = [p for p in re.split(r"\s+", (title or "").strip()) if p]
    if not parts:
        return "Fresh Thread"
    out = " ".join(_title_case(p) for p in parts[:_TITLE_WORDS])
    # Never emit vowel-stripped stubs from older Mumblz revisions.
    letters = re.sub(r"[^A-Za-z]", "", out)
    if letters and not re.search(r"[aeiouAEIOU]", letters):
        return "Fresh Thread"
    return out


def _title_case(word: str) -> str:
    if not word:
        return word
    cleaned = re.sub(r"[^A-Za-z0-9-]", "", word)
    if not cleaned:
        return word
    if cleaned.isupper() and len(cleaned) <= 4:
        return cleaned
    return cleaned[:1].upper() + cleaned[1:].lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text or "")


def _dialog_blob(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for m in messages or []:
        role = (m.get("role") or "").lower()
        content = (m.get("content") or "").strip()
        if not content or content.startswith("Attach a pdf"):
            continue
        if role in {"user", "assistant"}:
            parts.append(content[:1200] if role == "user" else content[:800])
    return "\n".join(parts)


def _pick_topics(blob: str) -> list[tuple[str, float]]:
    hits: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pat, label, score in _TOPIC_MAP:
        if pat.search(blob) and label.lower() not in seen:
            hits.append((label, float(score)))
            seen.add(label.lower())
    return hits


def _pick_tasks(blob: str) -> list[tuple[str, float]]:
    hits: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pat, label, score in _TASK_MAP:
        if pat.search(blob) and label.lower() not in seen:
            hits.append((label, float(score)))
            seen.add(label.lower())
    return hits


def _keyword_pool(blob: str) -> list[tuple[str, float]]:
    counts: Counter[str] = Counter()
    for w in _words(blob):
        low = w.lower()
        if low in _STOP or len(low) < 4:
            continue
        weight = 2 if low in _STYLE_WORDS else 1
        counts[low] += weight
    return [(w, float(n) + 2.0) for w, n in counts.most_common(40)]


def _candidate_pool(blob: str) -> list[tuple[str, float]]:
    pool: dict[str, float] = {}

    def add(word: str, sem: float) -> None:
        tw = _title_case(word)
        if not tw or tw.lower() in _STOP or len(tw) < 3:
            return
        pool[tw] = max(pool.get(tw, 0.0), sem)

    for label, sem in _pick_topics(blob):
        add(label, sem + 8)
    for label, sem in _pick_tasks(blob):
        add(label, sem + 7)
    for word, sem in _keyword_pool(blob):
        add(word, sem)
    for i, word in enumerate(_DEFAULT_WORDS):
        add(word, 3.5 - i * 0.15)
    return list(pool.items())


def _rank_candidates(candidates: list[tuple[str, float]]) -> list[tuple[str, float]]:
    ranked = sorted(candidates, key=lambda x: -x[1])
    return ranked


def _two_word_clear(messages: list[dict[str, str]]) -> str:
    """Pick the two most suitable Title Case words for this dialog."""
    blob = _dialog_blob(messages)
    if not blob.strip():
        return "Fresh Thread"

    ranked = _rank_candidates(_candidate_pool(blob))
    picked: list[str] = []

    for word, _score in ranked:
        if word.lower() in {w.lower() for w in picked}:
            continue
        # Skip near-duplicate stems (Assess / Assessment)
        stem = word.lower()[:5]
        if any(w.lower()[:5] == stem for w in picked):
            continue
        picked.append(word)
        if len(picked) >= _TITLE_WORDS:
            break

    while len(picked) < _TITLE_WORDS:
        for fallback in _DEFAULT_WORDS:
            if fallback.lower() not in {w.lower() for w in picked}:
                picked.append(fallback)
                break
        else:
            picked.append(["Signalcraft", "Blueprint"][len(picked) % 2])

    return " ".join(picked[:_TITLE_WORDS])


def normalize_three_word_title(raw: str, fallback: str = "Fresh Thread") -> str:
    """Normalize an LLM/local title to two Title Case words (name kept for API compat)."""
    cleaned = re.sub(r"[\"'`#*_]+", "", (raw or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.split("\n", 1)[0].strip()
    parts = [p for p in re.split(r"\s+", cleaned) if p]
    if len(parts) >= _TITLE_WORDS:
        ranked = _rank_candidates([(_title_case(p), 5.0 + (len(parts) - i) * 0.1) for i, p in enumerate(parts[:8])])
        clear = " ".join(w for w, _ in ranked[:_TITLE_WORDS])
        if len(clear.split()) < _TITLE_WORDS:
            clear = " ".join(_title_case(p) for p in parts[:_TITLE_WORDS])
    elif len(parts) == 1:
        clear = f"{_title_case(parts[0])} Digest"
    else:
        clear = fallback
    return mumblz_title(clear)


normalize_two_word_title = normalize_three_word_title


def mumblz_name_thread(messages: list[dict[str, str]]) -> str:
    """Mumblz: dialog → two most suitable Title Case words."""
    return mumblz_title(_two_word_clear(messages))


interpret_thread_title = mumblz_name_thread


async def mumblz_name_thread_llm(messages: list[dict[str, str]]) -> str | None:
    """Optional LLM polish: reply with two Title Case words."""
    local_clear = _two_word_clear(messages)
    blob = _dialog_blob(messages)
    if len(blob) < 40:
        return mumblz_title(local_clear)
    prompt = (
        "Read this chat and reply with ONLY two Title Case words for a history title.\n"
        "Pick the two most suitable, specific words that capture the topic and task.\n"
        "No quotes, punctuation, or explanation.\n\n"
        f"CHAT:\n{blob[:3500]}\n\n"
        f"Local Mumblz draft (improve if needed): {local_clear}"
    )
    try:
        from tokenish_engine.dispatch import chat_complete, resolve_model, resolve_provider

        provider = resolve_provider("auto", None, "gemini-3.5-flash")
        model = resolve_model(provider, None, "gemini-3.5-flash")
        text = await chat_complete(
            provider=provider,
            model=model,
            envelope=prompt,
            history=[],
        )
        return normalize_two_word_title(text, fallback=local_clear)
    except Exception:
        return None


interpret_thread_title_llm = mumblz_name_thread_llm
