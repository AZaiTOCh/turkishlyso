from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from tokenish_engine.config import settings
from tokenish_engine.models import ProviderStatus


def resolve_provider(provider: str | None, model: str | None, target_engine: str) -> str:
    if provider and provider != "auto":
        return provider.lower()
    blob = f"{model or ''} {target_engine or ''}".lower()
    if "claude" in blob or "anthropic" in blob:
        return "anthropic"
    if "groq" in blob or "llama" in blob and "ollama" not in blob:
        if "groq" in blob:
            return "groq"
    if any(x in blob for x in ("gpt", "openai", "o1", "o3", "o4")):
        return "openai"
    if "ollama" in blob or blob.startswith("llama") or "mistral" in blob or "qwen" in blob:
        # Prefer ollama for local-style names when no cloud key implied
        return "ollama"
    # Default: ollama if up, else openai
    return "ollama"


async def preflight() -> list[ProviderStatus]:
    """Argus-style provider health check."""
    statuses: list[ProviderStatus] = []

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_host.rstrip('/')}/api/tags")
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                statuses.append(
                    ProviderStatus(name="ollama", available=True, detail="ok", models=models)
                )
            else:
                statuses.append(
                    ProviderStatus(name="ollama", available=False, detail=f"HTTP {r.status_code}")
                )
    except Exception as exc:
        statuses.append(ProviderStatus(name="ollama", available=False, detail=str(exc)))

    statuses.append(
        ProviderStatus(
            name="openai",
            available=bool(settings.openai_api_key),
            detail="key set" if settings.openai_api_key else "OPENAI_API_KEY missing",
            models=["gpt-4o", "gpt-4.1-mini", "gpt-4o-mini"],
        )
    )
    statuses.append(
        ProviderStatus(
            name="anthropic",
            available=bool(settings.anthropic_api_key),
            detail="key set" if settings.anthropic_api_key else "ANTHROPIC_API_KEY missing",
            models=["claude-sonnet-4-20250514", "claude-3-5-haiku-latest"],
        )
    )
    statuses.append(
        ProviderStatus(
            name="groq",
            available=bool(settings.groq_api_key),
            detail="key set" if settings.groq_api_key else "GROQ_API_KEY missing",
            models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        )
    )
    return statuses


def _user_content(
    envelope: str,
    image_b64: str | None,
    image_mime: str | None,
) -> Any:
    if image_b64:
        return [
            {"type": "text", "text": envelope},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image_mime or 'image/png'};base64,{image_b64}"},
            },
        ]
    return envelope


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
    if provider == "ollama":
        return await _ollama_chat(model, envelope, history, image_b64)
    if provider == "anthropic":
        return await _anthropic_chat(model, envelope, history, image_b64, image_mime)
    if provider == "groq":
        return await _openai_compatible(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key or "",
            model=model,
            envelope=envelope,
            history=history,
            image_b64=None,  # groq text path
            image_mime=None,
        )
    # openai default
    return await _openai_compatible(
        base_url="https://api.openai.com/v1",
        api_key=settings.openai_api_key or "",
        model=model,
        envelope=envelope,
        history=history,
        image_b64=image_b64,
        image_mime=image_mime,
    )


async def chat_stream(
    *,
    provider: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]] | None = None,
    image_b64: str | None = None,
    image_mime: str | None = None,
) -> AsyncIterator[str]:
    """Yield text deltas. Falls back to one-shot if streaming unsupported."""
    # Simple reliable path: complete then yield once (UI still works).
    # Streaming for ollama/openai implemented below.
    history = history or []
    if provider == "ollama":
        async for chunk in _ollama_stream(model, envelope, history, image_b64):
            yield chunk
        return
    if provider == "openai" and settings.openai_api_key:
        async for chunk in _openai_stream(
            "https://api.openai.com/v1",
            settings.openai_api_key,
            model,
            envelope,
            history,
            image_b64,
            image_mime,
        ):
            yield chunk
        return
    text = await chat_complete(
        provider=provider,
        model=model,
        envelope=envelope,
        history=history,
        image_b64=image_b64,
        image_mime=image_mime,
    )
    yield text


async def _ollama_chat(
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
) -> str:
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    msg: dict[str, Any] = {"role": "user", "content": envelope}
    if image_b64:
        msg["images"] = [image_b64]
    messages.append(msg)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{settings.ollama_host.rstrip('/')}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")


async def _ollama_stream(
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
) -> AsyncIterator[str]:
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    msg: dict[str, Any] = {"role": "user", "content": envelope}
    if image_b64:
        msg["images"] = [image_b64]
    messages.append(msg)
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_host.rstrip('/')}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                content = data.get("message", {}).get("content")
                if content:
                    yield content


async def _openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
    image_mime: str | None,
) -> str:
    if not api_key:
        raise RuntimeError(f"API key missing for {base_url}")
    messages: list[dict[str, Any]] = [
        {"role": h["role"], "content": h["content"]} for h in history
    ]
    messages.append(
        {"role": "user", "content": _user_content(envelope, image_b64, image_mime)}
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _openai_stream(
    base_url: str,
    api_key: str,
    model: str,
    envelope: str,
    history: list[dict[str, str]],
    image_b64: str | None,
    image_mime: str | None,
) -> AsyncIterator[str]:
    messages: list[dict[str, Any]] = [
        {"role": h["role"], "content": h["content"]} for h in history
    ]
    messages.append(
        {"role": "user", "content": _user_content(envelope, image_b64, image_mime)}
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "stream": True},
        ) as r:
            r.raise_for_status()
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
    content: Any
    if image_b64:
        media = (image_mime or "image/png").split("/")[-1]
        if media == "jpg":
            media = "jpeg"
        content = [
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
        r.raise_for_status()
        blocks = r.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
