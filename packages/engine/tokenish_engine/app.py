from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tokenish_engine import __version__
from tokenish_engine.agents import mumblz_name_thread, mumblz_name_thread_llm, normalize_three_word_title
from tokenish_engine.dispatch import chat_complete, chat_stream, preflight_full, resolve_model, resolve_provider
from tokenish_engine.dispatch.providers import StreamSession
from tokenish_engine.history import compress_history
from tokenish_engine.pipeline import optimize
from tokenish_engine.retrieve import memtrove_available
from tokenish_engine.settings_store import (
    apply_saved_keys_to_environ,
    load_keys,
    load_prefs,
    save_keys,
    save_prefs,
    tokenish_home,
)

apply_saved_keys_to_environ()

app = FastAPI(title="tokenish", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC = Path(__file__).resolve().parent / "static"
if _STATIC.is_dir():
    app.mount("/ui", StaticFiles(directory=str(_STATIC)), name="ui")


class KeysPayload(BaseModel):
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    PERPLEXITY_API_KEY: str | None = None
    fallback_preference: str | None = None
    hide_key_wizard: bool | None = None


class MumblzPayload(BaseModel):
    messages: list[dict[str, str]] = []
    use_llm: bool = False


@app.get("/")
async def root_ui():
    index = _STATIC / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"status": "ok", "version": __version__})


@app.post("/mumblz")
@app.post("/title")
async def mumblz_thread(payload: MumblzPayload) -> dict[str, Any]:
    """Mumblz agent: whole-dialog → two most suitable lowercase words for History."""
    apply_saved_keys_to_environ()
    local = mumblz_name_thread(payload.messages)
    title = local
    source = "mumblz"
    if payload.use_llm:
        polished = await mumblz_name_thread_llm(payload.messages)
        if polished:
            title = normalize_three_word_title(polished, fallback=local)
            source = "mumblz+llm" if title != local else "mumblz"
    return {"title": title, "local": local, "source": source, "agent": "Mumblz"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__, "memtrove_sdk": memtrove_available()}


@app.get("/settings/keys")
async def get_key_status() -> dict[str, Any]:
    apply_saved_keys_to_environ(overwrite=True)
    keys = load_keys()
    prefs = load_prefs()
    has = {
        "gemini": bool(keys.get("GEMINI_API_KEY") or keys.get("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "openrouter": bool(keys.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")),
        "openai": bool(keys.get("OPENAI_API_KEY") or keys.get("GPT_TOKENISH") or os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(keys.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
        "groq": bool(keys.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")),
        "perplexity": bool(keys.get("PERPLEXITY_API_KEY") or os.getenv("PERPLEXITY_API_KEY")),
    }
    return {
        **has,
        "has": has,
        "prefs": prefs,
        "home": str(tokenish_home()),
        "version": __version__,
    }


@app.post("/settings/keys")
async def set_keys(payload: KeysPayload):
    raw = payload.model_dump()
    allowed = {
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "PERPLEXITY_API_KEY",
    }
    data = {k: str(v).strip() for k, v in raw.items() if k in allowed and v and str(v).strip()}
    prefs_in = {}
    if payload.fallback_preference is not None:
        prefs_in["fallback_preference"] = payload.fallback_preference.strip()
    if payload.hide_key_wizard is not None:
        prefs_in["hide_key_wizard"] = bool(payload.hide_key_wizard)
    if prefs_in:
        save_prefs(prefs_in)
        if prefs_in.get("fallback_preference"):
            try:
                from tokenish_engine.config import settings as _settings
                object.__setattr__(_settings, "fallback_preference", prefs_in["fallback_preference"])
            except Exception:
                pass
    existing = load_keys()
    if not data and not existing and not prefs_in:
        return JSONResponse({"ok": False, "error": "paste at least one AI key"}, status_code=400)
    if not data and not existing:
        # prefs-only when no keys yet — still require a key for first-time use
        if not prefs_in.get("hide_key_wizard"):
            return JSONResponse({"ok": False, "error": "paste at least one AI key"}, status_code=400)
    if data:
        save_keys(data)
        for key, value in data.items():
            os.environ[key] = value
        try:
            routing_path = Path(__file__).resolve().parent / "routing.json"
            routing = json.loads(routing_path.read_text(encoding="utf-8")) if routing_path.exists() else {}
            providers = routing.setdefault("providers", {})
            mapping = {
                "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
                "openrouter": ("OPENROUTER_API_KEY",),
                "openai": ("OPENAI_API_KEY",),
                "anthropic": ("ANTHROPIC_API_KEY",),
                "groq": ("GROQ_API_KEY",),
                "perplexity": ("PERPLEXITY_API_KEY",),
            }
            for pname, key_names in mapping.items():
                if any(data.get(k) for k in key_names):
                    providers.setdefault(pname, {})["is_active"] = True
                    providers[pname].pop("error", None)
            routing_path.write_text(json.dumps(routing, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    return {"ok": True, "home": str(tokenish_home()), "saved": list(data.keys()), "prefs": load_prefs()}


@app.get("/providers")
async def providers() -> dict[str, Any]:
    apply_saved_keys_to_environ()
    statuses, meta = await preflight_full()
    return {
        "providers": [s.model_dump() for s in statuses],
        "preferred": meta.get("preferred"),
        "fallback_chain": meta.get("fallback_chain"),
        "openrouter_free_roster": meta.get("openrouter_free_roster"),
    }


async def _read_uploads(files: list[UploadFile] | None) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for f in files or []:
        data = await f.read()
        out.append((f.filename or "upload.bin", data))
    return out


def _parse_history(history: str | None) -> list[dict[str, str]]:
    if not history:
        return []
    try:
        data = json.loads(history)
        return [
            {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
            for m in data
            if isinstance(m, dict)
        ]
    except Exception:
        return []


def _tokex_payload(compiled) -> dict[str, Any]:
    t = compiled.tokex or compiled.meter
    return t.model_dump()


@app.post("/compile")
async def compile_endpoint(
    prompt: str = Form(...),
    target_engine: str = Form("gpt-4o"),
    model: str | None = Form(None),
    page_range: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
) -> JSONResponse:
    uploads = await _read_uploads(files)
    result = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
    )
    return JSONResponse(result.model_dump())


@app.post("/chat")
async def chat_endpoint(
    prompt: str = Form(...),
    target_engine: str = Form("gpt-4o"),
    model: str | None = Form(None),
    provider: str | None = Form("auto"),
    history: str | None = Form(None),
    page_range: str | None = Form(None),
    stream: bool = Form(False),
    enable_its: str | None = Form("false"),
    files: list[UploadFile] | None = File(None),
):
    apply_saved_keys_to_environ()
    uploads = await _read_uploads(files)
    its_flag = str(enable_its or "").strip().lower() in {"1", "true", "yes", "on"}
    compiled = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
        enable_its=its_flag,
    )
    hist = compress_history(_parse_history(history))
    prov = resolve_provider(provider, model, target_engine)
    mdl = resolve_model(prov, model, target_engine)
    tokex = _tokex_payload(compiled)

    if stream:
        async def gen():
            use_prov = prov
            use_mdl = mdl
            meta = {
                "type": "meta",
                "provider": use_prov,
                "model": use_mdl,
                "tokex": tokex,
                "meter": tokex,
                "stages": compiled.stages,
                "kiosk_blocked": compiled.kiosk_blocked,
                "attachment_chars": len(compiled.envelope or ""),
                "data_type": compiled.data_type,
                "images_sent": len(compiled.images or ([] if not compiled.image_b64 else [1])),
                "attachment_warning": compiled.attachment_warning,
                "rainman": compiled.rainman,
                "agatha": compiled.agatha,
                "fidelity_mode": compiled.fidelity_mode,
                "neoborg": {
                    "broadcast": (compiled.neoborg or {}).get("broadcast"),
                    "clock_preview": (compiled.neoborg or {}).get("clock_preview"),
                },
            }
            yield json.dumps(meta) + "\n"
            if compiled.kiosk_blocked:
                yield json.dumps(
                    {
                        "type": "delta",
                        "text": (
                            "honesty gate: retrieval skill scores were too low. "
                            "no hedged answer was generated from weak context."
                        ),
                    }
                ) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
                return
            try:
                session = StreamSession()
                routing_sent = False
                async for delta in chat_stream(
                    provider=use_prov,
                    model=use_mdl,
                    envelope=compiled.envelope,
                    history=hist,
                    image_b64=compiled.image_b64,
                    image_mime=compiled.image_mime,
                    images=compiled.images or None,
                    session=session,
                ):
                    if session.provider and not routing_sent:
                        routing_sent = True
                        if session.fallback_used or session.provider != use_prov:
                            yield json.dumps(
                                {
                                    "type": "routing",
                                    "provider": session.provider,
                                    "model": session.model,
                                    "fallback_used": session.fallback_used,
                                    "fallback_reason": session.fallback_reason,
                                }
                            ) + "\n"
                            use_prov = session.provider
                            use_mdl = session.model or use_mdl
                    yield json.dumps({"type": "delta", "text": delta}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
            except Exception as exc:
                yield json.dumps({"type": "error", "error": str(exc)}) + "\n"

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    if compiled.kiosk_blocked:
        return JSONResponse(
            {
                "reply": (
                    "honesty gate: retrieval skill scores were too low. "
                    "no hedged answer was generated from weak context."
                ),
                "provider": prov,
                "model": mdl,
                "tokex": tokex,
                "compile": compiled.model_dump(),
            }
        )

    try:
        reply = await chat_complete(
            provider=prov,
            model=mdl,
            envelope=compiled.envelope,
            history=hist,
            image_b64=compiled.image_b64,
            image_mime=compiled.image_mime,
            images=compiled.images or None,
        )
    except Exception as exc:
        return JSONResponse(
            {
                "error": str(exc),
                "tokex": tokex,
                "compile": compiled.model_dump(),
                "provider": prov,
                "model": mdl,
            },
            status_code=502,
        )

    return JSONResponse(
        {
            "reply": reply,
            "provider": prov,
            "model": mdl,
            "tokex": tokex,
            "compile": compiled.model_dump(),
        }
    )
