"""
Provider dispatch + Argus-style fallback chain.

Auto order (skip missing keys): Claude → ChatGPT → Gemini → OpenRouter free
→ Groq 70b/8b → Perplexity. Gemini leads the unpaid/free path.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from tokenish_engine.config import (
    anthropic_key,
    gemini_key,
    groq_key,
    openai_key,
    openrouter_key,
    perplexity_key,
    settings,
)
from tokenish_engine.dispatch.argus import run_preflight
from tokenish_engine.models import ProviderStatus

_ROUTING_PATH = Path(__file__).resolve().parent.parent / "routing.json"

# Per-model cooldowns (provider/model -> unix time until retry). Do NOT kill whole providers.
_MODEL_COOLDOWN: dict[str, float] = {}
_COOLDOWN_SECS = 90.0

_OR_SKIP_SUBSTRINGS = (
    "lyria",
    "content-safety",
    "whisper",
    "tts",
    "embed",
    "moderation",
    "hy3",
    "-vl:",
    "vl:",
)


def _cooldown_key(provider: str, model: str) -> str:
    return f"{provider}/{model}"


def _model_on_cooldown(provider: str, model: str) -> bool:
    import time

    until = _MODEL_COOLDOWN.get(_cooldown_key(provider, model), 0.0)
    return time.time() < until


def _set_model_cooldown(provider: str, model: str, seconds: float | None = None) -> None:
    import time

    _MODEL_COOLDOWN[_cooldown_key(provider, model)] = time.time() + (seconds or _COOLDOWN_SECS)


def _openrouter_roster_models() -> list[str]:
    """Chat-capable free models from routing roster, preferred first."""
    preferred = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "qwen/qwen3-coder:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        settings.openrouter_free_model,
    ]
    roster: list[str] = []
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        roster = list(data.get("openrouter_free_roster", {}).get("verified_active", []) or [])
    except Exception:
        roster = []
    merged = list(dict.fromkeys([*preferred, *roster]))
    out: list[str] = []
    for mid in merged:
        low = mid.lower()
        # Meta-router picks random free upstream (often rate-limited); use concrete IDs.
        if mid.strip() == "openrouter/free":
            continue
        if any(s in low for s in _OR_SKIP_SUBSTRINGS):
            continue
        if _model_on_cooldown("openrouter", mid):
            continue
        out.append(mid)
    if not out:
        # Last resort: cooled models + meta-router
        for mid in merged:
            if mid.strip() == "openrouter/free" or not _model_on_cooldown("openrouter", mid):
                out.append(mid)
                if len(out) >= 3:
                    break
    return out or [settings.openrouter_free_model]


@dataclass
class StreamSession:
    """Filled when chat_stream successfully connects to a provider."""
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


def _load_fallbacks() -> list[tuple[str, str]]:
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        raw = data.get("tasks", {}).get("chat", {}).get("fallbacks", [])
        out: list[tuple[str, str]] = []
        for item in raw:
            if "/" not in item:
                continue
            prov, model = item.split("/", 1)
            out.append((prov, model))
        if out:
            return out
    except Exception:
        pass
    return [
        ("gemini", settings.gemini_model),
        ("openrouter", settings.openrouter_free_model),
    ]


def _first_active_fallback() -> tuple[str, str] | None:
    for prov, mdl in _load_fallbacks():
        if _provider_active(prov):
            return prov, mdl
    return None


def resolve_provider(provider: str | None, model: str | None, target_engine: str) -> str:
    if provider and provider != "auto":
        p = provider.lower().strip()
        if p in {"google"}:
            return "gemini"
        if p in {"pplx"}:
            return "perplexity"
        return p
    blob = f"{model or ''} {target_engine or ''}".lower()
    if "claude" in blob or "anthropic" in blob:
        return "anthropic"
    if "gemini" in blob or "google" in blob:
        return "gemini"
    if "perplexity" in blob or "sonar" in blob:
        return "perplexity"
    if "openrouter" in blob or ":free" in blob:
        return "openrouter"
    if any(x in blob for x in ("gpt", "openai", "o1", "o3", "o4", "chatgpt")):
        # OpenAI removed from UI; map to auto fallback chain.
        pass
    if "groq" in blob or "llama-3" in blob:
        if _provider_active("groq"):
            return "groq"
    active = _first_active_fallback()
    if active:
        return active[0]
    if gemini_key():
        return "gemini"
    if openrouter_key():
        return "openrouter"
    return "gemini"


def resolve_model(provider: str, model: str | None, target_engine: str) -> str:
    m = (model or target_engine or "").strip()
    if provider == "gemini":
        return settings.gemini_model  # always gemini-3.5-flash
    if provider == "openrouter":
        return settings.openrouter_free_model if not m or "gpt" in m.lower() or m.startswith("gemini") else m
    if provider == "openai":
        return settings.openai_primary_model
    if provider == "anthropic":
        return settings.anthropic_model
    if provider == "groq":
        if "8b" in m.lower() or "instant" in m.lower():
            return settings.groq_fast_model
        return settings.groq_primary_model
    if provider == "perplexity":
        return settings.perplexity_model
    return m or target_engine or settings.gemini_model


def _provider_has_key(name: str) -> bool:
    if name == "groq":
        return bool(groq_key())
    if name == "gemini":
        return bool(gemini_key())
    if name == "openrouter":
        return bool(openrouter_key())
    if name == "perplexity":
        return bool(perplexity_key())
    if name == "openai":
        return bool(openai_key())
    if name == "anthropic":
        return bool(anthropic_key())
    return False


def _pref_list() -> list[str]:
    raw = (settings.fallback_preference or "").strip()
    if not raw:
        return ["anthropic", "openai", "gemini", "openrouter", "groq", "perplexity"]
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _fallback_chain(provider: str, model: str) -> list[tuple[str, str]]:
    """
    Auto stack (everyday explanation):
    1) Paid APIs you added (Claude, then ChatGPT) go first.
    2) Free stack: Gemini 3.5 Flash first (large free allowance),
       then OpenRouter free models, then Groq 70b → 8b, then Perplexity.
    Explicit provider selection still jumps that provider to the front when usable.
    """
    if provider == "gemini" or (model or "").startswith("gemini"):
        provider, model = "gemini", settings.gemini_model
    if provider == "auto":
        provider, model = "gemini", settings.gemini_model

    chain: list[tuple[str, str]] = []

    def add(prov: str, mdl: str) -> None:
        item = (prov, mdl)
        if item in chain:
            return
        if not _provider_usable(prov):
            return
        if _model_on_cooldown(prov, mdl):
            return
        chain.append(item)

    for name in _pref_list():
        if name == "anthropic":
            add("anthropic", settings.anthropic_model)
        elif name == "openai":
            add("openai", settings.openai_primary_model)
        elif name == "gemini":
            add("gemini", settings.gemini_model)
        elif name == "openrouter":
            if openrouter_key():
                for mid in _openrouter_roster_models()[:10]:
                    add("openrouter", mid)
        elif name == "groq":
            add("groq", settings.groq_primary_model)  # 70b
            add("groq", settings.groq_fast_model)  # 8b
        elif name == "perplexity":
            add("perplexity", settings.perplexity_model)

    # Always ensure Gemini appears in free path if keyed and somehow missed.
    add("gemini", settings.gemini_model)

    if provider not in {"auto"} and _provider_usable(provider):
        if provider == "gemini":
            first = ("gemini", settings.gemini_model)
        elif provider == "groq":
            first = ("groq", model if model else settings.groq_primary_model)
        elif provider == "anthropic":
            first = ("anthropic", settings.anthropic_model)
        elif provider == "openai":
            first = ("openai", settings.openai_primary_model)
        elif provider == "perplexity":
            first = ("perplexity", settings.perplexity_model)
        else:
            first = (provider, model or settings.openrouter_free_model)
        chain = [first] + [x for x in chain if x != first]

    if chain:
        return chain
    if openrouter_key():
        return [("openrouter", settings.openrouter_free_model)]
    return [("gemini", settings.gemini_model)]


async def preflight() -> list[ProviderStatus]:
    """Argus live health + key roster."""
    statuses, _ = await run_preflight()
    return statuses


async def preflight_full() -> tuple[list[ProviderStatus], dict]:
    return await run_preflight()


def _provider_active(name: str) -> bool:
    if not _provider_has_key(name):
        return False
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        provid = data.get("providers", {}).get(name, {})
        if "is_active" in provid:
            return bool(provid["is_active"])
    except Exception:
        pass
    return True


def _mark_provider_error(name: str, err: str, *, model: str | None = None) -> None:
    """
    Record failures without nuking the whole provider on a single free-model 429.
    OpenRouter: cooldown that model only. Gemini 503: transient, keep active.
    Gemini hard quota 429: mark inactive until key/billing recovers.
    """
    err_l = (err or "").lower()
    is_429 = "429" in err_l or "rate" in err_l
    is_503 = "503" in err_l or "high demand" in err_l
    is_402 = "402" in err_l or "credit" in err_l

    if name == "openrouter":
        if model:
            _set_model_cooldown("openrouter", model, 120 if is_429 or is_503 else 60)
        # Keep provider active so other free models can be tried.
        try:
            data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
            prov = data.setdefault("providers", {}).setdefault("openrouter", {})
            prov["is_active"] = True
            prov["error"] = (f"{model}: {err}" if model else err)[:160]
            _ROUTING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
        return

    if name == "gemini":
        if is_503:
            _set_model_cooldown("gemini", settings.gemini_model, 45)
            try:
                data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
                prov = data.setdefault("providers", {}).setdefault("gemini", {})
                prov["is_active"] = True  # key still valid; spike is transient
                prov["error"] = err[:160]
                _ROUTING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
            return
        if is_429 or "quota" in err_l:
            try:
                data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
                prov = data.setdefault("providers", {}).setdefault("gemini", {})
                prov["is_active"] = False
                prov["error"] = err[:160]
                _ROUTING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
        return

    if not (is_402 or is_429 or "quota" in err_l or "credit" in err_l):
        return
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        prov = data.setdefault("providers", {}).setdefault(name, {})
        prov["is_active"] = False
        prov["error"] = err[:160]
        _ROUTING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _provider_usable(name: str) -> bool:
    """Key present and not hard-disabled (OpenRouter stays usable if keyed)."""
    if not _provider_has_key(name):
        return False
    if name == "openrouter":
        return True
    if name == "gemini":
        # Allow gemini attempt even if last ping said inactive, unless quota error.
        try:
            data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
            err = str(data.get("providers", {}).get("gemini", {}).get("error") or "").lower()
            if "quota" in err and "429" in err:
                return False
        except Exception:
            pass
        return True
    return _provider_active(name)


def _completion_body(model: str, messages: list, *, provider: str, stream: bool) -> dict[str, Any]:
    max_tokens = 2048 if provider == "openrouter" else 4096
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if stream:
        body["stream"] = True
    return body


def _normalize_images(
    image_b64: str | None = None,
    image_mime: str | None = None,
    images: list[dict[str, str]] | None = None,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if images:
        for im in images:
            b64 = (im.get("b64") or im.get("image_b64") or "").strip()
            if not b64:
                continue
            mime = im.get("mime") or im.get("image_mime") or "image/jpeg"
            out.append((b64, mime))
    elif image_b64:
        out.append((image_b64, image_mime or "image/jpeg"))
    return out


def _user_content(
    envelope: str,
    image_b64: str | None,
    image_mime: str | None,
    images: list[dict[str, str]] | None = None,
) -> Any:
    parts = _normalize_images(image_b64, image_mime, images)
    if parts:
        content: list[dict[str, Any]] = [{"type": "text", "text": envelope}]
        for b64, mime in parts:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime or 'image/png'};base64,{b64}"},
                }
            )
        return content
    return envelope


async def chat_complete(
    *,
    provider: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]] | None = None,
    image_b64: str | None = None,
    image_mime: str | None = None,
    images: list[dict[str, str]] | None = None,
) -> str:
    history = history or []
    errors: list[str] = []
    for prov, mdl in _fallback_chain(provider, model):
        try:
            return await _dispatch_once(
                provider=prov,
                model=mdl,
                envelope=envelope,
                history=history,
                image_b64=image_b64,
                image_mime=image_mime,
                images=images,
            )
        except Exception as exc:
            errors.append(f"{prov}/{mdl}: {exc}")
            _mark_provider_error(prov, str(exc), model=mdl)
            continue
    raise RuntimeError("all providers failed — " + " | ".join(errors[:6]))


def _provider_skip_reason(name: str) -> str:
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        prov = data.get("providers", {}).get(name, {})
        err = prov.get("error") or ""
        if err:
            return f"{name}: {err}"
        if prov.get("is_active") is False:
            return f"{name}: unavailable"
    except Exception:
        pass
    if not _provider_has_key(name):
        return f"{name}: API key missing"
    return f"{name}: unavailable"


async def chat_stream(
    *,
    provider: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]] | None = None,
    image_b64: str | None = None,
    image_mime: str | None = None,
    images: list[dict[str, str]] | None = None,
    session: StreamSession | None = None,
) -> AsyncIterator[str]:
    history = history or []
    requested = (provider, model)
    chain = _fallback_chain(provider, model)
    last_err = ""
    errors: list[str] = []
    if chain and chain[0] != requested:
        last_err = _provider_skip_reason(requested[0])
    for prov, mdl in chain:
        try:
            if prov in {"openai", "groq", "openrouter", "perplexity"}:
                vision_ok = prov in {"openai", "openrouter"}
                async for delta in _openai_compatible_stream(
                    provider=prov,
                    base_url=_base_url(prov),
                    api_key=_api_key(prov) or "",
                    model=mdl,
                    envelope=envelope,
                    history=history,
                    image_b64=image_b64 if vision_ok else None,
                    image_mime=image_mime if vision_ok else None,
                    images=images if vision_ok else None,
                    extra_headers=_extra_headers(prov),
                ):
                    if session and session.provider is None:
                        session.provider = prov
                        session.model = mdl
                        session.fallback_used = (prov, mdl) != requested
                        if session.fallback_used and last_err:
                            session.fallback_reason = last_err
                        last_err = ""
                    yield delta
                if session and session.provider is None:
                    session.provider = prov
                    session.model = mdl
                    session.fallback_used = (prov, mdl) != requested
                    if session.fallback_used and last_err:
                        session.fallback_reason = last_err
                return
            text = await _dispatch_once(
                provider=prov,
                model=mdl,
                envelope=envelope,
                history=history,
                image_b64=image_b64,
                image_mime=image_mime,
                images=images,
            )
            if session:
                session.provider = prov
                session.model = mdl
                session.fallback_used = (prov, mdl) != requested
                if session.fallback_used and last_err:
                    session.fallback_reason = last_err
            yield text
            return
        except Exception as exc:
            last_err = f"{prov}/{mdl}: {str(exc)[:160]}"
            errors.append(last_err)
            _mark_provider_error(prov, str(exc), model=mdl)
            if session:
                session.fallback_reason = last_err
            continue
    detail = " | ".join(errors[:5]) if errors else last_err
    raise RuntimeError("all providers failed during stream" + (f" — {detail}" if detail else ""))


def _base_url(provider: str) -> str:
    if provider == "groq":
        return "https://api.groq.com/openai/v1"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    if provider == "perplexity":
        return "https://api.perplexity.ai"
    return "https://api.openai.com/v1"


def _api_key(provider: str) -> str | None:
    if provider == "groq":
        return groq_key()
    if provider == "openrouter":
        return openrouter_key()
    if provider == "perplexity":
        return perplexity_key()
    if provider == "gemini":
        return gemini_key()
    if provider == "openai":
        return openai_key()
    if provider == "anthropic":
        return anthropic_key()
    return None


def _extra_headers(provider: str) -> dict[str, str]:
    if provider == "openrouter":
        return {
            "HTTP-Referer": "https://github.com/AZaiTOCh/tokenish",
            "X-Title": "tokenish",
        }
    return {}


async def _dispatch_once(
    *,
    provider: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
    image_mime: str | None,
    images: list[dict[str, str]] | None = None,
) -> str:
    if provider == "anthropic":
        return await _anthropic_chat(model, envelope, history, image_b64, image_mime, images)
    if provider == "gemini":
        return await _gemini_chat(model, envelope, history, image_b64, image_mime, images)
    if provider in {"groq", "openai", "openrouter", "perplexity"}:
        vision_ok = provider in {"openai", "openrouter"}
        return await _openai_compatible(
            provider=provider,
            base_url=_base_url(provider),
            api_key=_api_key(provider) or "",
            model=model,
            envelope=envelope,
            history=history,
            image_b64=image_b64 if vision_ok else None,
            image_mime=image_mime if vision_ok else None,
            images=images if vision_ok else None,
            extra_headers=_extra_headers(provider),
        )
    raise RuntimeError(f"unknown provider: {provider}")


async def _openai_compatible(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
    image_mime: str | None,
    images: list[dict[str, str]] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> str:
    if not api_key:
        raise RuntimeError(f"API key missing for {base_url}")
    messages: list[dict[str, Any]] = [
        {"role": h["role"], "content": h["content"]} for h in history
    ]
    messages.append(
        {"role": "user", "content": _user_content(envelope, image_b64, image_mime, images)}
    )
    headers = {"Authorization": f"Bearer {api_key}", **(extra_headers or {})}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=_completion_body(model, messages, provider=provider, stream=False),
        )
        if r.status_code >= 400:
            err = f"HTTP {r.status_code}: {r.text[:240]}"
            _mark_provider_error(provider, err, model=model)
            raise RuntimeError(err)
        return r.json()["choices"][0]["message"]["content"]


async def _openai_compatible_stream(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
    image_mime: str | None,
    images: list[dict[str, str]] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    if not api_key:
        raise RuntimeError(f"API key missing for {base_url}")
    messages: list[dict[str, Any]] = [
        {"role": h["role"], "content": h["content"]} for h in history
    ]
    messages.append(
        {"role": "user", "content": _user_content(envelope, image_b64, image_mime, images)}
    )
    headers = {"Authorization": f"Bearer {api_key}", **(extra_headers or {})}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=_completion_body(model, messages, provider=provider, stream=True),
        ) as r:
            if r.status_code >= 400:
                body = await r.aread()
                err = f"HTTP {r.status_code}: {body[:240]!r}"
                _mark_provider_error(provider, err, model=model)
                raise RuntimeError(err)
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                    delta = data["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except Exception:
                    continue


async def _gemini_chat(
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None = None,
    image_mime: str | None = None,
    images: list[dict[str, str]] | None = None,
) -> str:
    key = gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY missing")
    contents = []
    for h in history:
        role = "user" if h["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h["content"]}]})
    user_parts: list[dict[str, Any]] = []
    for b64, mime in _normalize_images(image_b64, image_mime, images):
        user_parts.append(
            {
                "inline_data": {
                    "mime_type": mime or "image/jpeg",
                    "data": b64,
                }
            }
        )
    user_parts.append({"text": envelope})
    contents.append({"role": "user", "parts": user_parts})

    async def _call(mdl: str) -> httpx.Response:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{mdl}:generateContent?key={key}"
        )
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }
        if "Execute#D_Only" in envelope or "DoNotRewriteOrSummarize#D" in envelope:
            body["systemInstruction"] = {
                "parts": [
                    {
                        "text": (
                            "Execute the attached document (#D) exactly. "
                            "Do not rewrite, summarize, or reproduce #D. "
                            "Reply with only what #D instructs you to produce."
                        )
                    }
                ]
            }
        async with httpx.AsyncClient(timeout=120.0) as client:
            return await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=body,
            )

    r = await _call(settings.gemini_model if model.startswith("gemini") else model)
    if r.status_code >= 400:
        raise RuntimeError(f"gemini HTTP {r.status_code}: {r.text[:240]}")
    data = r.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


async def _anthropic_chat(
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
    image_mime: str | None,
    images: list[dict[str, str]] | None = None,
) -> str:
    if not settings.anthropic_api_key and not anthropic_key():
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    key = anthropic_key() or settings.anthropic_api_key
    messages: list[dict[str, Any]] = []
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    vision = _normalize_images(image_b64, image_mime, images)
    if vision:
        content: Any = []
        for b64, mime in vision:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime or "image/png",
                        "data": b64,
                    },
                }
            )
        content.append({"type": "text", "text": envelope})
    else:
        content = envelope
    messages.append({"role": "user", "content": content})
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": model, "max_tokens": 4096, "messages": messages},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"anthropic HTTP {r.status_code}: {r.text[:240]}")
        blocks = r.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
