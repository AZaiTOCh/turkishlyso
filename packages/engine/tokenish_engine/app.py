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
from tokenish_engine.key_inventory import linked_inventory, linked_provider_status
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
    XAI_API_KEY: str | None = None
    GROK_API_KEY: str | None = None
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


class HiveOptInPayload(BaseModel):
    hive_opt_in: bool = True
    hive_url: str | None = None


class HiveContributePayload(BaseModel):
    node_id: str
    saved_tokex: int
    total_tokex: int
    ts: float | None = None
    agent: str | None = None


class HiveSyncPayload(BaseModel):
    saved_tokex: int
    total_tokex: int


@app.get("/tokex-clock")
@app.get("/hive/clock")
async def tokex_clock_get() -> dict[str, Any]:
    """Live World Counter Clock — always read collective tally (engine or remote hive)."""
    from tokenish_engine.agents.tokex_clock import fetch_live_clock

    return await fetch_live_clock()


@app.post("/hive/contribute")
async def hive_contribute(payload: HiveContributePayload) -> dict[str, Any]:
    """Accept a vetted Neoborg contribution into the engine-local hive store."""
    from tokenish_engine import hive_store

    try:
        return {
            "ok": True,
            **hive_store.contribute(payload.node_id, payload.saved_tokex, payload.total_tokex),
        }
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/hive/sync")
@app.post("/tokex-clock/sync")
async def hive_sync_lifetime(payload: HiveSyncPayload) -> dict[str, Any]:
    """Push absolute lifetime TOKEX for this node (keeps sole-user global % on par)."""
    from tokenish_engine.agents.tokex_clock import sync_lifetime_sync

    result = sync_lifetime_sync(payload.saved_tokex, payload.total_tokex)
    if not result.get("ok"):
        return JSONResponse({"ok": False, "error": result.get("reason") or "sync failed"}, status_code=400)
    return result


@app.post("/hive/heartbeat")
async def hive_heartbeat(payload: HiveContributePayload) -> dict[str, Any]:
    from tokenish_engine import hive_store

    try:
        return {
            "ok": True,
            **hive_store.heartbeat(payload.node_id, payload.saved_tokex, payload.total_tokex),
        }
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/tokex-clock/opt-in")
async def tokex_clock_opt_in(payload: HiveOptInPayload) -> dict[str, Any]:
    from tokenish_engine.agents.tokex_clock import set_hive_opt_in

    return {"ok": True, **set_hive_opt_in(payload.hive_opt_in, url=payload.hive_url)}


@app.get("/tokex-clock/status")
async def tokex_clock_status() -> dict[str, Any]:
    from tokenish_engine.agents.tokex_clock import fetch_live_clock, hive_opt_in, hive_url, node_id

    clock = await fetch_live_clock()
    return {
        "ok": True,
        "hive_opt_in": hive_opt_in(),
        "hive_url": hive_url(),
        "node_id": node_id(),
        "clock": clock,
    }


@app.get("/scoreboard")
async def get_scoreboard() -> dict[str, Any]:
    from tokenish_engine.agents.agatha import scoreboard_payload

    return {"ok": True, **scoreboard_payload()}


class GrettaPayload(BaseModel):
    need: str = ""


@app.post("/gretta/recommend")
async def gretta_recommend_route(payload: GrettaPayload) -> dict[str, Any]:
    try:
        from tokenish_engine.agents.gretta import recommend

        return {"ok": True, **recommend(payload.need, linked=_provider_key_status())}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


def _provider_key_status() -> dict[str, bool]:
    """Which providers already have a key (config + env + Settings/.env helpers)."""
    return linked_provider_status()


@app.get("/settings/keys")
async def get_key_status() -> dict[str, Any]:
    has = _provider_key_status()
    prefs = load_prefs()
    inv = linked_inventory()
    return {
        **has,
        "has": has,
        "linked": inv["linked"],
        "linked_count": inv["linked_count"],
        "any_linked": inv["any_linked"],
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
        "XAI_API_KEY",
        "GROK_API_KEY",
        "PERPLEXITY_API_KEY",
    }
    # Only persist non-empty values — blank fields never wipe existing keys.
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

    already = _provider_key_status()
    any_already = any(already.values())
    # Gemini / OpenRouter are optional. Any single linked provider (or new paste) is enough.
    if not data and not any_already and not prefs_in:
        return JSONResponse(
            {"ok": False, "error": "paste at least one AI key (any provider — Gemini and OpenRouter are optional)"},
            status_code=400,
        )
    if not data and not any_already:
        return JSONResponse(
            {"ok": False, "error": "paste at least one AI key (any provider — Gemini and OpenRouter are optional)"},
            status_code=400,
        )
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
                "grok": ("XAI_API_KEY", "GROK_API_KEY"),
                "perplexity": ("PERPLEXITY_API_KEY",),
            }
            for pname, key_names in mapping.items():
                if any(data.get(k) for k in key_names):
                    providers.setdefault(pname, {})["is_active"] = True
                    providers[pname].pop("error", None)
            routing_path.write_text(json.dumps(routing, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    linked_after = _provider_key_status()
    inv = linked_inventory()
    return {
        "ok": True,
        "home": str(tokenish_home()),
        "saved": list(data.keys()),
        "has": linked_after,
        "linked": inv["linked"],
        "linked_count": inv["linked_count"],
        "any_linked": inv["any_linked"],
        "prefs": load_prefs(),
    }


@app.get("/providers")
async def providers(force: bool = False) -> dict[str, Any]:
    apply_saved_keys_to_environ()
    if force:
        from tokenish_engine.dispatch.argus import bust_preflight_cache

        bust_preflight_cache()
    statuses, meta = await preflight_full()
    inv = linked_inventory()
    return {
        "providers": [s.model_dump() for s in statuses],
        "preferred": meta.get("preferred"),
        "fallback_chain": meta.get("fallback_chain"),
        "openrouter_free_roster": meta.get("openrouter_free_roster"),
        "linked_keys": inv,
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
    enable_its: str | None = Form("false"),
    enable_ffmpeg: str | None = Form("true"),
    files: list[UploadFile] | None = File(None),
) -> JSONResponse:
    uploads = await _read_uploads(files)
    its_flag = str(enable_its or "").strip().lower() in {"1", "true", "yes", "on"}
    ffmpeg_raw = str(enable_ffmpeg if enable_ffmpeg is not None else "true").strip().lower()
    ffmpeg_flag = ffmpeg_raw not in {"0", "false", "no", "off"}
    result = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
        enable_its=its_flag,
        enable_ffmpeg=ffmpeg_flag,
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
    enable_ffmpeg: str | None = Form("true"),
    files: list[UploadFile] | None = File(None),
):
    apply_saved_keys_to_environ()
    uploads = await _read_uploads(files)
    its_flag = str(enable_its or "").strip().lower() in {"1", "true", "yes", "on"}
    # Default ON: blank / missing → True; only explicit false disables.
    ffmpeg_raw = str(enable_ffmpeg if enable_ffmpeg is not None else "true").strip().lower()
    ffmpeg_flag = ffmpeg_raw not in {"0", "false", "no", "off"}
    compiled = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
        enable_its=its_flag,
        enable_ffmpeg=ffmpeg_flag,
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
