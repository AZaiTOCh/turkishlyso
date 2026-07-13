"""
Argus preflight — ported from AZ Signal Engine argus_watchdog.py (slim).

Live health checks for Groq 70B/8B, Gemini 3.5, OpenRouter free roster.
Updates routing.json openrouter_free_roster when OR key is present.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from tokenish_engine.config import gemini_key, openrouter_key, settings
# openai kept only for optional offline tests; not used in product surface
try:
    from tokenish_engine.config import openai_key  # noqa: F401
except Exception:  # pragma: no cover
    def openai_key():  # type: ignore
        return None
from tokenish_engine.models import ProviderStatus

_ROUTING_PATH = Path(__file__).resolve().parent.parent / "routing.json"
_DUMMY = "Reply with the single word: OK"
_TEST_TIMEOUT = 10.0
_OR_COOLDOWN_SECS = 43200  # 12h between OR test calls
_GEMINI_COOLDOWN_SECS = 43200


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_routing() -> dict[str, Any]:
    try:
        return json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_routing(data: dict[str, Any]) -> None:
    data["last_updated"] = _now()
    _ROUTING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _cooldown_expired(roster: dict[str, Any]) -> bool:
    last = roster.get("last_test_called") or ""
    if not last:
        return True
    try:
        ts = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() >= _OR_COOLDOWN_SECS
    except Exception:
        return True


def _gemini_ping_due(routing: dict[str, Any]) -> bool:
    prov = routing.get("providers", {}).get("gemini", {})
    last = prov.get("last_ping") or ""
    if not last:
        return True
    try:
        ts = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() >= _GEMINI_COOLDOWN_SECS
    except Exception:
        return True


async def _test_openai(model: str) -> tuple[bool, int, str]:
    key = openai_key()
    if not key:
        return False, 0, "GPT_TOKENISH missing"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": _DUMMY}],
                    "max_tokens": 5,
                    "temperature": 0,
                },
            )
        ms = int((time.time() - t0) * 1000)
        if r.status_code == 200:
            return True, ms, ""
        return False, ms, f"HTTP {r.status_code}"
    except Exception as exc:
        return False, 0, str(exc)[:80]


async def _test_groq(model: str) -> tuple[bool, int, str]:
    key = settings.groq_api_key
    if not key:
        return False, 0, "GROQ_API_KEY missing"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": _DUMMY}],
                    "max_tokens": 5,
                    "temperature": 0,
                },
            )
        ms = int((time.time() - t0) * 1000)
        if r.status_code == 200:
            return True, ms, ""
        return False, ms, f"HTTP {r.status_code}"
    except Exception as exc:
        return False, 0, str(exc)[:80]


async def _test_gemini(model: str) -> tuple[bool, int, str]:
    key = gemini_key()
    if not key:
        return False, 0, "GEMINI_API_KEY missing"
    t0 = time.time()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    try:
        async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
            r = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": _DUMMY}]}],
                    "generationConfig": {"maxOutputTokens": 5, "temperature": 0},
                },
            )
        ms = int((time.time() - t0) * 1000)
        if r.status_code == 200:
            return True, ms, ""
        return False, ms, f"HTTP {r.status_code}"
    except Exception as exc:
        return False, 0, str(exc)[:80]


async def _poll_openrouter_free() -> list[str]:
    key = openrouter_key()
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code != 200:
            return []
        free: list[str] = []
        for m in r.json().get("data", []):
            p = m.get("pricing", {})
            if str(p.get("prompt", "1")) in ("0", "0.0") and str(
                p.get("completion", "1")
            ) in ("0", "0.0"):
                free.append(m["id"])
        return free
    except Exception:
        return []


async def _test_openrouter(model_id: str) -> tuple[bool, int, str]:
    key = openrouter_key()
    if not key:
        return False, 0, "OPENROUTER_API_KEY missing"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/AZaiTOCh/tokenish",
                    "X-Title": "tokenish",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": _DUMMY}],
                    "max_tokens": 5,
                    "temperature": 0,
                },
            )
        ms = int((time.time() - t0) * 1000)
        if r.status_code == 200:
            return True, ms, ""
        return False, ms, f"HTTP {r.status_code}"
    except Exception as exc:
        return False, 0, str(exc)[:80]


def _is_rate_limited(err: str) -> bool:
    e = (err or "").upper()
    return "HTTP 429" in e or "HTTP 503" in e or ("RATE" in e and "LIMIT" in e)


async def _refresh_openrouter_roster(routing: dict[str, Any]) -> list[str]:
    live = await _poll_openrouter_free()
    roster = routing.setdefault("openrouter_free_roster", {})
    current = roster.get("verified_active", [])

    if not live:
        return current or [settings.openrouter_free_model]

    if not _cooldown_expired(roster):
        merged = list(dict.fromkeys([m for m in live if m in current or m in live]))
        if settings.openrouter_free_model not in merged:
            merged.append(settings.openrouter_free_model)
        roster["verified_active"] = merged
        roster["last_verified"] = _now()
        _save_routing(routing)
        return merged

    priority = [
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "openai/gpt-oss-120b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        settings.openrouter_free_model,
    ]
    to_test = [m for m in priority if m in live][:3]
    validated: list[str] = []
    for mid in to_test:
        ok, _, err = await _test_openrouter(mid)
        if ok:
            validated.append(mid)
        elif _is_rate_limited(err) and mid in live:
            validated.append(mid)

    live_set = set(live)
    prior = [m for m in current if m in live_set or m == settings.openrouter_free_model]
    merged = list(dict.fromkeys(validated + prior))
    if settings.openrouter_free_model not in merged:
        merged.append(settings.openrouter_free_model)

    roster["verified_active"] = merged
    roster["last_verified"] = _now()
    roster["last_test_called"] = _now()
    _save_routing(routing)
    return merged


_PREFLIGHT_CACHE: dict[str, Any] = {"at": 0.0, "statuses": [], "meta": {}}
_PREFLIGHT_TTL_SECS = 120.0


async def run_preflight(*, force: bool = False) -> tuple[list[ProviderStatus], dict[str, Any]]:
    """Argus preflight: live probes + routing refresh. Returns statuses + routing meta."""
    now = time.time()
    if (
        not force
        and _PREFLIGHT_CACHE["statuses"]
        and now - float(_PREFLIGHT_CACHE["at"]) < _PREFLIGHT_TTL_SECS
    ):
        return _PREFLIGHT_CACHE["statuses"], _PREFLIGHT_CACHE["meta"]

    routing = _load_routing()
    providers_cfg = routing.setdefault("providers", {})
    meta: dict[str, Any] = {"argus": True, "fallback_chain": _fallback_list()}

    # Gemini
    gemini_model = settings.gemini_model
    gemini_ok = bool(gemini_key())
    gemini_ms = 0
    gemini_err = ""
    if gemini_key():
        if _gemini_ping_due(routing):
            ok, gemini_ms, gemini_err = await _test_gemini(gemini_model)
            gemini_ok = ok
            if not ok and _is_quota_error(gemini_err):
                gemini_err = "quota exceeded"
            # 503 high demand is transient — keep provider active for alt-model retries
            if not ok and "503" in (gemini_err or ""):
                gemini_ok = True
                gemini_err = "high demand (will retry alt models)"
            providers_cfg.setdefault("gemini", {})["last_ping"] = _now()
            providers_cfg["gemini"].update(
                {
                    "is_active": True if gemini_key() else False,
                    "model_name": gemini_model,
                    "latency_ms": gemini_ms,
                    "error": gemini_err or None,
                }
            )
        else:
            gemini_ms = int(providers_cfg.get("gemini", {}).get("latency_ms", 0))
            gemini_ok = bool(gemini_key())

    # OpenRouter roster
    or_models = await _refresh_openrouter_roster(routing)
    or_ok = bool(openrouter_key()) and bool(or_models)
    providers_cfg.setdefault("openrouter", {})["is_active"] = or_ok

    _save_routing(routing)
    meta["openrouter_free_roster"] = or_models
    meta["preferred"] = _pick_preferred(False, gemini_ok, or_ok)

    statuses = [
        ProviderStatus(
            name="gemini",
            available=bool(gemini_key()),
            detail=(
                f"{gemini_model} OK {gemini_ms}ms"
                if gemini_ok and gemini_ms
                else (gemini_err or ("key set" if gemini_key() else "GEMINI_API_KEY missing"))
            ),
            models=[settings.gemini_model],
        ),
        ProviderStatus(
            name="openrouter",
            available=or_ok,
            detail=(
                f"{len(or_models)} free models"
                if or_ok
                else ("OPENROUTER_API_KEY missing" if not openrouter_key() else "no free models")
            ),
            models=(or_models[:8] or [settings.openrouter_free_model]),
        ),
    ]
    _PREFLIGHT_CACHE.update({"at": time.time(), "statuses": statuses, "meta": meta})
    return statuses, meta


def _is_quota_error(err: str) -> bool:
    e = (err or "").lower()
    return (
        "429" in e
        or "402" in e
        or "quota" in e
        or "credit" in e
        or "resource_exhausted" in e
    )


def _should_deactivate(err: str) -> bool:
    e = (err or "").lower()
    return (
        "invalid" in e
        or "401" in e
        or "403" in e
        or "api key" in e
        or _is_quota_error(err)
    )


def _fallback_list() -> list[str]:
    try:
        data = _load_routing()
        return data.get("tasks", {}).get("chat", {}).get("fallbacks", [])
    except Exception:
        return []


def _pick_preferred(openai_ok: bool, gemini_ok: bool, or_ok: bool) -> dict[str, str]:
    if gemini_ok or gemini_key():
        return {"provider": "gemini", "model": settings.gemini_model}
    if or_ok or openrouter_key():
        return {"provider": "openrouter", "model": settings.openrouter_free_model}
    return {"provider": "auto", "model": settings.gemini_model}
