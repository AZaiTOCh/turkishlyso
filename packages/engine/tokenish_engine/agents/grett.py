"""
Grett — LLM protoprompter, qualifier, and router (v0.4.1).

Keeps talk short for everyday users. Chooses from a *curated* capability map
and Argus-linked providers. Does NOT invent “latest news winners” from raw
web scrapes — that path is high hallucination risk. Optional curated-feed
hooks can be added later with an allowlist only.
"""

from __future__ import annotations

from typing import Any


# Curated strengths only — reviewed, not scraped. Update deliberately.
_CAPABILITY_MAP: list[dict[str, Any]] = [
    {
        "provider": "openai",
        "model": "gpt-4o",
        "good_for": (
            "logo",
            "brand",
            "design",
            "creative",
            "image gen",
            "illustrat",
            "artwork",
            "company logo",
            "code",
            "plan",
            "brainstorm",
            "json",
            "api",
        ),
        "blurb": "ChatGPT gpt-4o — strong for creative briefs and design work",
    },
    {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "good_for": (
            "rewrite",
            "edit",
            "essay",
            "careful",
            "long write",
            "code review",
            "summar",
            "summary",
            "legal",
            "contract",
            "brief",
            "assess",
        ),
        "blurb": "Claude Sonnet — strong at careful writing and rewrites",
    },
    {
        "provider": "perplexity",
        "model": "sonar",
        "good_for": ("news", "current", "today", "market", "research", "what happened"),
        "blurb": "Perplexity sonar — strong at fresh web-backed answers",
    },
    {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "good_for": ("general", "search", "explain", "document", "pdf", "photo"),
        "blurb": "gemini-3.5-flash — fast everyday helper with live-web access",
    },
    {
        "provider": "grok",
        "model": "grok-3",
        "good_for": ("twitter", "x.com", "edgy", "opinion", "humor"),
        "blurb": "grok-3 — more conversational takes",
    },
    {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "good_for": ("fast", "quick", "speed"),
        "blurb": "Groq llama-3.3-70b — very fast when speed matters",
    },
    {
        "provider": "openrouter",
        "model": "openrouter/free",
        "good_for": ("free", "try", "budget"),
        "blurb": "OpenRouter free models — when you just want to try",
    },
]

_FALLBACK = {
    "provider": "gemini",
    "model": "gemini-3.5-flash",
    "blurb": "gemini-3.5-flash — reliable everyday default on tokenish",
}


def protoprompt(user_need: str) -> str:
    """Turn plain user words into one short, efficient model prompt."""
    need = " ".join((user_need or "").strip().split())
    if not need:
        return "Help the user in plain language with their next question."
    return (
        "Answer in plain everyday language. Be concise (3-6 short sentences unless asked for more). "
        f"User need: {need}"
    )


def _score(need: str, entry: dict[str, Any]) -> int:
    text = need.lower()
    return sum(1 for kw in entry["good_for"] if kw in text)


def recommend(
    user_need: str,
    *,
    linked: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """
    Pick a suitable provider/model from curated strengths + linked keys.

    Returns a short user-facing note (≤3 sentences). Never claims live scrape certainty.
    """
    need = (user_need or "").strip()
    linked = linked or {}
    any_linked = any(bool(v) for v in linked.values())
    ranked = sorted(_CAPABILITY_MAP, key=lambda e: _score(need, e), reverse=True)
    ideal = ranked[0] if ranked and _score(need, ranked[0]) > 0 else dict(_FALLBACK, **{"good_for": ()})

    # Line up only among APIs the user has linked when possible.
    pick = None
    if any_linked:
        for entry in ranked:
            if linked.get(entry.get("provider") or "", False):
                pick = entry
                break
        if pick is None and linked.get("gemini"):
            pick = next((e for e in _CAPABILITY_MAP if e["provider"] == "gemini"), _FALLBACK)
        if pick is None:
            for entry in _CAPABILITY_MAP:
                if linked.get(entry["provider"], False):
                    pick = entry
                    break
    if pick is None:
        pick = ideal if (not any_linked or linked.get(ideal.get("provider") or "", False)) else _FALLBACK

    ideal_prov = ideal.get("provider")
    pick_prov = pick.get("provider")
    available = (not linked) or bool(linked.get(pick_prov, False))

    lines: list[str] = []
    if ideal_prov and ideal_prov != pick_prov:
        lines.append(
            f"Ok — {ideal_prov} fits that need best ({ideal.get('blurb')})."
        )
        if not linked.get(str(ideal_prov), False):
            lines.append(
                f"That API isn’t linked here, so we lined up {pick_prov} ({pick.get('blurb')})."
            )
        else:
            lines.append(f"We lined up {pick_prov} instead ({pick.get('blurb')}).")
    else:
        lines.append(f"Ok — {pick_prov} is lined up for you ({pick.get('blurb')}).")

    note = " ".join(lines[:3])
    return {
        "agent": "Grett",
        "truthful": True,
        "method": "curated_capability_map",
        "scrape_used": False,
        "user_need": need,
        "protoprompt": protoprompt(need),
        "ideal": {"provider": ideal_prov, "model": ideal.get("model"), "blurb": ideal.get("blurb")},
        "selected": {
            "provider": pick_prov,
            "model": pick.get("model"),
            "blurb": pick.get("blurb"),
            "linked": available,
        },
        "note": note,
        "caveat": (
            "Grett does not scrape the live web to crown a ‘best model’ — "
            "choices use a curated map plus your linked APIs."
        ),
    }
