from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from tokenish_engine import __version__
from tokenish_engine.dispatch import chat_complete, chat_stream, preflight, preflight_full, resolve_provider
from tokenish_engine.dispatch.providers import StreamSession
from tokenish_engine.pipeline import optimize
from tokenish_engine.retrieve import moorcheh_available

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


@app.get("/")
async def root_ui():
    index = _STATIC / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"status": "ok", "version": __version__})


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__, "moorcheh_sdk": moorcheh_available()}


@app.get("/providers")
async def providers() -> dict[str, Any]:
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
    files: list[UploadFile] | None = File(None),
):
    uploads = await _read_uploads(files)
    compiled = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
    )
    hist = _parse_history(history)
    prov = resolve_provider(provider, model, target_engine)
    mdl = model or target_engine
    tokex = _tokex_payload(compiled)

    if stream:
        async def gen():
            meta = {
                "type": "meta",
                "provider": prov,
                "model": mdl,
                "tokex": tokex,
                "meter": tokex,
                "stages": compiled.stages,
                "kiosk_blocked": compiled.kiosk_blocked,
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
                    provider=prov,
                    model=mdl,
                    envelope=compiled.envelope,
                    history=hist,
                    image_b64=compiled.image_b64,
                    image_mime=compiled.image_mime,
                    session=session,
                ):
                    if session.provider and not routing_sent:
                        routing_sent = True
                        if session.fallback_used or session.provider != prov:
                            yield json.dumps(
                                {
                                    "type": "routing",
                                    "provider": session.provider,
                                    "model": session.model,
                                    "fallback_used": session.fallback_used,
                                }
                            ) + "\n"
                            prov = session.provider
                            mdl = session.model or mdl
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
