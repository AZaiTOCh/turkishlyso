from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from tokenish_engine import __version__
from tokenish_engine.dispatch import chat_complete, chat_stream, preflight, resolve_provider
from tokenish_engine.pipeline import optimize

app = FastAPI(title="Tokenish Optimizer Engine", version=__version__)
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
    return JSONResponse(
        {"status": "ok", "version": __version__, "ui": "missing static/index.html"}
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


@app.get("/providers")
async def providers() -> dict[str, Any]:
    statuses = await preflight()
    return {"providers": [s.model_dump() for s in statuses]}


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


@app.post("/compile")
async def compile_endpoint(
    prompt: str = Form(...),
    target_engine: str = Form("gpt-4o"),
    model: str | None = Form(None),
    page_range: str | None = Form(None),
    enable_pxpipe: bool | None = Form(None),
    enable_headroom: bool | None = Form(None),
    enable_its: bool | None = Form(None),
    files: list[UploadFile] | None = File(None),
) -> JSONResponse:
    uploads = await _read_uploads(files)
    result = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
        enable_pxpipe=enable_pxpipe,
        enable_headroom=enable_headroom,
        enable_its=enable_its,
    )
    payload = result.model_dump()
    # Don't echo huge base64 in compile-only unless needed — keep it
    return JSONResponse(payload)


@app.post("/chat")
async def chat_endpoint(
    prompt: str = Form(...),
    target_engine: str = Form("gpt-4o"),
    model: str | None = Form(None),
    provider: str | None = Form("auto"),
    history: str | None = Form(None),
    page_range: str | None = Form(None),
    stream: bool = Form(False),
    show_envelope: bool = Form(False),
    enable_pxpipe: bool | None = Form(None),
    enable_headroom: bool | None = Form(None),
    enable_its: bool | None = Form(None),
    files: list[UploadFile] | None = File(None),
):
    uploads = await _read_uploads(files)
    compiled = optimize(
        prompt=prompt,
        target_engine=target_engine,
        model=model,
        files=uploads,
        page_range=page_range,
        enable_pxpipe=enable_pxpipe,
        enable_headroom=enable_headroom,
        enable_its=enable_its,
    )
    hist = _parse_history(history)
    prov = resolve_provider(provider, model, target_engine)
    mdl = model or target_engine

    if stream:
        async def gen():
            meta = {
                "type": "meta",
                "provider": prov,
                "model": mdl,
                "meter": compiled.meter.model_dump(),
                "stages": compiled.stages,
                "pxpipe_applied": compiled.pxpipe_applied,
            }
            if show_envelope:
                meta["envelope"] = compiled.envelope
            yield json.dumps(meta) + "\n"
            try:
                async for delta in chat_stream(
                    provider=prov,
                    model=mdl,
                    envelope=compiled.envelope,
                    history=hist,
                    image_b64=compiled.image_b64,
                    image_mime=compiled.image_mime,
                ):
                    yield json.dumps({"type": "delta", "text": delta}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
            except Exception as exc:
                yield json.dumps({"type": "error", "error": str(exc)}) + "\n"

        return StreamingResponse(gen(), media_type="application/x-ndjson")

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
                "compile": compiled.model_dump(),
                "provider": prov,
                "model": mdl,
            },
            status_code=502,
        )

    body = {
        "reply": reply,
        "provider": prov,
        "model": mdl,
        "compile": compiled.model_dump(),
    }
    if not show_envelope:
        body["compile"]["envelope"] = compiled.envelope[:500] + (
            "…" if len(compiled.envelope) > 500 else ""
        )
    return JSONResponse(body)
