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

from tokenish_engine.config import gemini_key, grok_key, groq_key, openrouter_key, settings
from tokenish_engine.config import anthropic_key, openai_key, perplexity_key
from tokenish_engine.key_inventory import PROVIDER_ORDER, linked_inventory, linked_provider_status
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

_HARD_BLOCK_HINTS = (
    "credit",
    "quota",
    "429",
    "402",
    "403",
    "license",
    "resource_exhausted",
    "permission-denied",
)


def bust_preflight_cache() -> None:
    """Drop Argus cache so /providers reflects chat-time quota/credit failures."""
    _PREFLIGHT_CACHE["at"] = 0.0
    _PREFLIGHT_CACHE["statuses"] = []


def _is_quota_error(err: str) -> bool:
    e = (err or "").lower()
    return (
        "429" in e
        or "402" in e
        or "quota" in e
        or "credit" in e
        or "resource_exhausted" in e
    )


def _is_no_credits_error(err: str) -> bool:
    e = (err or "").lower()
    return (
        "credit" in e
        or "license" in e
        or "402" in e
        or ("403" in e and ("permission" in e or "team" in e))
    )


def classify_provider_health(name: str, has_key: bool, slot: dict[str, Any] | None = None) -> tuple[bool, str, str]:
    """
    Returns (usable, reason, hint) for UI soft grey-out.
    reason: ok | missing_key | quota | no_credits | error
    """
    del name  # reserved for per-provider nuance later
    slot = slot or {}
    if not has_key:
        return False, "missing_key", "link a key in manage connections"
    err = str(slot.get("error") or "")
    err_l = err.lower()
    active = slot.get("is_active")
    if _is_no_credits_error(err):
        return False, "no_credits", "add credits on the provider site"
    if "429" in err_l or "resource_exhausted" in err_l or "quota" in err_l:
        return False, "quota", "out of calls — check back soon"
    if active is False and err_l:
        if "rate" in err_l:
            return False, "quota", "out of calls — check back soon"
        return False, "error", "check back soon"
    return True, "ok", ""


def _hard_block_error(err: str) -> bool:
    e = (err or "").lower()
    return any(k in e for k in _HARD_BLOCK_HINTS)


async def run_preflight(*, force: bool = False) -> tuple[list[ProviderStatus], dict[str, Any]]:
    """Argus preflight: live probes + linked-API inventory + routing refresh."""
    now = time.time()
    if (
        not force
        and _PREFLIGHT_CACHE["statuses"]
        and now - float(_PREFLIGHT_CACHE["at"]) < _PREFLIGHT_TTL_SECS
    ):
        # Cheap path: refresh linked keys + re-classify from live routing.json
        # so chat-time quota marks show without waiting for TTL.
        meta = dict(_PREFLIGHT_CACHE["meta"] or {})
        meta["linked_keys"] = linked_inventory()
        routing = _load_routing()
        providers_cfg = routing.get("providers", {})
        linked = linked_provider_status()
        refreshed: list[ProviderStatus] = []
        for s in _PREFLIGHT_CACHE["statuses"]:
            slot = providers_cfg.get(s.name, {})
            has_key = bool(linked.get(s.name))
            usable, reason, hint = classify_provider_health(s.name, has_key, slot)
            detail = s.detail
            if reason == "missing_key":
                detail = "no key linked"
            elif hint and reason != "ok":
                detail = hint
            refreshed.append(
                ProviderStatus(
                    name=s.name,
                    available=usable,
                    detail=detail,
                    models=list(s.models or []),
                    reason=reason,
                    hint=hint,
                    usable=usable,
                )
            )
        return refreshed, meta

    routing = _load_routing()
    providers_cfg = routing.setdefault("providers", {})
    linked = linked_provider_status()
    meta: dict[str, Any] = {
        "argus": True,
        "fallback_chain": _fallback_list(),
        "linked_keys": linked_inventory(),
    }

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
                gemini_ok = False
            # 503 high demand is transient — keep provider active for alt-model retries
            if not ok and "503" in (gemini_err or ""):
                gemini_ok = True
                gemini_err = "high demand (will retry alt models)"
            providers_cfg.setdefault("gemini", {})["last_ping"] = _now()
            providers_cfg["gemini"].update(
                {
                    "is_active": bool(gemini_key()) and gemini_ok,
                    "model_name": gemini_model,
                    "latency_ms": gemini_ms,
                    "error": gemini_err or None,
                }
            )
        else:
            slot_g = providers_cfg.get("gemini", {})
            gemini_ms = int(slot_g.get("latency_ms", 0))
            gemini_err = str(slot_g.get("error") or "")
            if slot_g.get("is_active") is False or _is_quota_error(gemini_err):
                gemini_ok = False
            else:
                gemini_ok = bool(gemini_key())

    # OpenRouter roster
    or_models = await _refresh_openrouter_roster(routing)
    or_ok = bool(openrouter_key()) and bool(or_models)
    or_slot = providers_cfg.setdefault("openrouter", {})
    # Don't wipe a hard failure just because roster fetch looked fine.
    if or_ok and not _hard_block_error(str(or_slot.get("error") or "")):
        or_slot["is_active"] = True
    elif not openrouter_key():
        or_slot["is_active"] = False
    else:
        or_slot["is_active"] = bool(or_ok) and or_slot.get("is_active", True) is not False

    # Sync key_linked; preserve hard quota/credit blocks from chat failures.
    for pname, has_key in linked.items():
        slot = providers_cfg.setdefault(pname, {})
        slot["key_linked"] = bool(has_key)
        if pname in {"gemini", "openrouter"}:
            # Live probe owns is_active for these; inventory only stamps key_linked.
            continue
        if not has_key:
            slot["is_active"] = False
            continue
        if slot.get("is_active") is False and _hard_block_error(str(slot.get("error") or "")):
            continue
        slot["is_active"] = True

    _save_routing(routing)
    meta["openrouter_free_roster"] = or_models
    meta["preferred"] = _pick_preferred(False, gemini_ok, or_ok)

    def _detail_for(name: str) -> tuple[bool, str, list[str], bool, str, str]:
        slot = providers_cfg.get(name, {})
        if name == "gemini":
            has_key = bool(gemini_key())
            usable, reason, hint = classify_provider_health(name, has_key, slot)
            if reason == "ok" and gemini_ok and gemini_ms:
                detail = f"{gemini_model} OK {gemini_ms}ms"
            elif reason == "missing_key":
                detail = "no key linked"
            elif hint:
                detail = hint
            else:
                detail = gemini_err or ("key linked" if has_key else "no key linked")
            return has_key, detail, [settings.gemini_model], usable, reason, hint
        if name == "openrouter":
            has_key = bool(openrouter_key())
            usable, reason, hint = classify_provider_health(name, has_key, slot)
            if reason == "ok" and or_ok:
                detail = f"{len(or_models)} free models"
            elif reason == "missing_key":
                detail = "no key linked"
            elif hint:
                detail = hint
            else:
                detail = "no free models" if has_key else "no key linked"
            # Roster empty still means not really usable for chat.
            if reason == "ok" and has_key and not or_ok:
                usable, reason, hint = False, "error", "check back soon"
                detail = "no free models"
            return has_key, detail, (or_models[:8] or [settings.openrouter_free_model]), usable, reason, hint
        key_fns = {
            "openai": openai_key,
            "anthropic": anthropic_key,
            "perplexity": perplexity_key,
            "groq": groq_key,
            "grok": grok_key,
        }
        models = {
            "openai": [settings.openai_primary_model],
            "anthropic": [settings.anthropic_model],
            "perplexity": [settings.perplexity_model],
            "groq": [settings.groq_primary_model, settings.groq_fast_model],
            "grok": [settings.grok_model],
        }
        fn = key_fns.get(name)
        has_key = bool(fn()) if fn else False
        usable, reason, hint = classify_provider_health(name, has_key, slot)
        if reason == "missing_key":
            detail = "no key linked"
        elif hint:
            detail = hint
        else:
            detail = "key linked"
        return has_key, detail, models.get(name, []), usable, reason, hint

    statuses: list[ProviderStatus] = []
    for name in PROVIDER_ORDER:
        _avail, detail, models, usable, reason, hint = _detail_for(name)
        statuses.append(
            ProviderStatus(
                name=name,
                available=usable,
                detail=detail,
                models=models,
                reason=reason,
                hint=hint,
                usable=usable,
            )
        )

    _PREFLIGHT_CACHE.update({"at": time.time(), "statuses": statuses, "meta": meta})
    return statuses, meta


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
    # Never prefer a door we already know is quota-dead.
    if gemini_ok:
        return {"provider": "gemini", "model": settings.gemini_model}
    if or_ok:
        return {"provider": "openrouter", "model": settings.openrouter_free_model}
    if openrouter_key():
        return {"provider": "openrouter", "model": settings.openrouter_free_model}
    if gemini_key():
        return {"provider": "gemini", "model": settings.gemini_model}
    return {"provider": "auto", "model": settings.gemini_model}
