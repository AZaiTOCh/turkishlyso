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
        return "openai"
    if "groq" in blob or "llama-3" in blob:
        return "groq"
    # Auto: prefer configured fallback order
    if openai_key():
        return "openai"
    if gemini_key():
        return "gemini"
    if settings.openrouter_api_key:
        return "openrouter"
    if settings.perplexity_api_key:
        return "perplexity"
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.groq_api_key:
        return "groq"
    return "openai"


def _provider_ready(name: str) -> bool:
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


async def preflight() -> list[ProviderStatus]:
    """Argus live health + key roster (Groq 70B/8B, Gemini 3.5, OpenRouter free)."""
    statuses, _ = await run_preflight()
    return statuses


async def preflight_full() -> tuple[list[ProviderStatus], dict]:
    return await run_preflight()


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
    # Only keep providers that have keys configured
    ready = [(p, m) for p, m in chain if _provider_ready(p)]
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
    for prov, mdl in _fallback_chain(provider, model):
        try:
            if prov in {"openai", "groq", "openrouter", "perplexity"}:
                async for delta in _openai_compatible_stream(
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
                    yield delta
                if session and session.provider is None:
                    session.provider = prov
                    session.model = mdl
                    session.fallback_used = (prov, mdl) != requested
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
            yield text
            return
        except Exception:
            continue
    raise RuntimeError("all providers failed during stream")


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
        return await _gemini_chat(model, envelope, history)
    if provider in {"groq", "openai", "openrouter", "perplexity"}:
        return await _openai_compatible(
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
            json={"model": model, "messages": messages},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:240]}")
        return r.json()["choices"][0]["message"]["content"]


async def _openai_compatible_stream(
    *,
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
            json={"model": model, "messages": messages, "stream": True},
        ) as r:
            if r.status_code >= 400:
                body = await r.aread()
                raise RuntimeError(f"HTTP {r.status_code}: {body[:240]!r}")
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


async def _gemini_chat(model: str, envelope: str, history: list[dict[str, str]]) -> str:
    key = gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY missing")
    contents = []
    for h in history:
        role = "user" if h["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h["content"]}]})
    contents.append({"role": "user", "parts": [{"text": envelope}]})

    async def _call(mdl: str) -> httpx.Response:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{mdl}:generateContent?key={key}"
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            return await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": contents,
                    "generationConfig": {"temperature": 0.2},
                },
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
