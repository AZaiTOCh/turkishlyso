"""
Provider dispatch + Argus-style fallback chain.

Order when preferred provider fails / missing key:
  ChatGPT (gpt-4o) → Gemini 3.5 → OpenRouter free roster
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from tokenish_engine.config import gemini_key, openai_key, settings
from tokenish_engine.dispatch.argus import run_preflight
from tokenish_engine.models import ProviderStatus

_ROUTING_PATH = Path(__file__).resolve().parent.parent / "routing.json"


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
        ("openai", settings.openai_primary_model),
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
        if _provider_active("openai"):
            return "openai"
    if "groq" in blob or "llama-3" in blob:
        if _provider_active("groq"):
            return "groq"
    active = _first_active_fallback()
    if active:
        return active[0]
    if openai_key():
        return "openai"
    if gemini_key():
        return "gemini"
    if settings.openrouter_api_key:
        return "openrouter"
    return "gemini"


def resolve_model(provider: str, model: str | None, target_engine: str) -> str:
    m = (model or target_engine or "").strip()
    if provider == "openai":
        return m if m and _provider_active("openai") else settings.openai_primary_model
    if provider == "gemini":
        return settings.gemini_model if not m or "gpt" in m.lower() else m
    if provider == "openrouter":
        return settings.openrouter_free_model if not m or "gpt" in m.lower() else m
    return m or target_engine or settings.openai_primary_model


def _provider_has_key(name: str) -> bool:
    if name == "groq":
        return bool(settings.groq_api_key)
    if name == "gemini":
        return bool(gemini_key())
    if name == "openrouter":
        return bool(settings.openrouter_api_key)
    if name == "perplexity":
        return bool(settings.perplexity_api_key)
    if name == "openai":
        return bool(openai_key())
    if name == "anthropic":
        return bool(settings.anthropic_api_key)
    return False


def _provider_active(name: str) -> bool:
    if not _provider_has_key(name):
        return False
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        prov = data.get("providers", {}).get(name, {})
        if "is_active" in prov:
            return bool(prov["is_active"])
    except Exception:
        pass
    return True


def _provider_ready(name: str) -> bool:
    return _provider_active(name)


async def preflight() -> list[ProviderStatus]:
    """Argus live health + key roster (Groq 70B/8B, Gemini 3.5, OpenRouter free)."""
    statuses, _ = await run_preflight()
    return statuses


async def preflight_full() -> tuple[list[ProviderStatus], dict]:
    return await run_preflight()


def _mark_provider_error(name: str, err: str) -> None:
    if "402" not in err and "429" not in err and "quota" not in err.lower() and "credit" not in err.lower():
        return
    try:
        data = json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
        prov = data.setdefault("providers", {}).setdefault(name, {})
        prov["is_active"] = False
        prov["error"] = err[:160]
        _ROUTING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _completion_body(model: str, messages: list, *, provider: str, stream: bool) -> dict[str, Any]:
    max_tokens = 2048 if provider == "openrouter" else 4096
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if stream:
        body["stream"] = True
    return body


def _user_content(envelope: str, image_b64: str | None, image_mime: str | None) -> Any:
    if image_b64:
        return [
            {"type": "text", "text": envelope},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image_mime or 'image/png'};base64,{image_b64}"},
            },
        ]
    return envelope


def _fallback_chain(provider: str, model: str) -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = [(provider, model)]
    for prov, mdl in _load_fallbacks():
        if (prov, mdl) not in chain:
            chain.append((prov, mdl))
    ready = [(p, m) for p, m in chain if _provider_active(p)]
    return ready or chain


async def chat_complete(
    *,
    provider: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]] | None = None,
    image_b64: str | None = None,
    image_mime: str | None = None,
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
            )
        except Exception as exc:
            errors.append(f"{prov}/{mdl}: {exc}")
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
    session: StreamSession | None = None,
) -> AsyncIterator[str]:
    history = history or []
    requested = (provider, model)
    chain = _fallback_chain(provider, model)
    last_err = ""
    if chain and chain[0] != requested:
        last_err = _provider_skip_reason(requested[0])
    for prov, mdl in chain:
        try:
            if prov in {"openai", "groq", "openrouter", "perplexity"}:
                async for delta in _openai_compatible_stream(
                    provider=prov,
                    base_url=_base_url(prov),
                    api_key=_api_key(prov) or "",
                    model=mdl,
                    envelope=envelope,
                    history=history,
                    image_b64=image_b64 if prov == "openai" else None,
                    image_mime=image_mime if prov == "openai" else None,
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
            last_err = f"{prov}: {str(exc)[:120]}"
            _mark_provider_error(prov, str(exc))
            if session:
                session.fallback_reason = last_err
            continue
    raise RuntimeError("all providers failed during stream" + (f" — {last_err}" if last_err else ""))


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
        return settings.groq_api_key
    if provider == "openrouter":
        return settings.openrouter_api_key
    if provider == "perplexity":
        return settings.perplexity_api_key
    if provider == "openai":
        return openai_key()
    if provider == "gemini":
        return gemini_key()
    if provider == "anthropic":
        return settings.anthropic_api_key
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
) -> str:
    if provider == "anthropic":
        return await _anthropic_chat(model, envelope, history, image_b64, image_mime)
    if provider == "gemini":
        return await _gemini_chat(model, envelope, history, image_b64, image_mime)
    if provider in {"groq", "openai", "openrouter", "perplexity"}:
        return await _openai_compatible(
            provider=provider,
            base_url=_base_url(provider),
            api_key=_api_key(provider) or "",
            model=model,
            envelope=envelope,
            history=history,
            image_b64=image_b64 if provider == "openai" else None,
            image_mime=image_mime if provider == "openai" else None,
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
    extra_headers: dict[str, str] | None = None,
) -> str:
    if not api_key:
        raise RuntimeError(f"API key missing for {base_url}")
    messages: list[dict[str, Any]] = [
        {"role": h["role"], "content": h["content"]} for h in history
    ]
    messages.append(
        {"role": "user", "content": _user_content(envelope, image_b64, image_mime)}
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
            _mark_provider_error(provider, err)
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
    extra_headers: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    if not api_key:
        raise RuntimeError(f"API key missing for {base_url}")
    messages: list[dict[str, Any]] = [
        {"role": h["role"], "content": h["content"]} for h in history
    ]
    messages.append(
        {"role": "user", "content": _user_content(envelope, image_b64, image_mime)}
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
                _mark_provider_error(provider, err)
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
) -> str:
    key = gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY missing")
    contents = []
    for h in history:
        role = "user" if h["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h["content"]}]})
    user_parts: list[dict[str, Any]] = []
    if image_b64:
        user_parts.append(
            {
                "inline_data": {
                    "mime_type": image_mime or "image/jpeg",
                    "data": image_b64,
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

    r = await _call(model)
    if r.status_code == 404 and model != settings.gemini_model_fallback:
        r = await _call(settings.gemini_model_fallback)
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
) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    messages: list[dict[str, Any]] = []
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    if image_b64:
        content: Any = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_mime or "image/png",
                    "data": image_b64,
                },
            },
            {"type": "text", "text": envelope},
        ]
    else:
        content = envelope
    messages.append({"role": "user", "content": content})
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": model, "max_tokens": 4096, "messages": messages},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"anthropic HTTP {r.status_code}: {r.text[:240]}")
        blocks = r.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
