from __future__ import annotations

from tokenish_engine.compile import (
    assemble_envelope,
    baseline_prompt,
    compress_instructions,
    document_verbatim_in_envelope,
)
from tokenish_engine.compress import compress_context, maybe_hi0_json_block
from tokenish_engine.config import settings
from tokenish_engine.ingest import IngestResult, ingest_file, merge_ingests
from tokenish_engine.meters import make_meter
from tokenish_engine.models import CompileResult
from tokenish_engine.retrieve import gate_document
from tokenish_engine.vision import maybe_pack


def optimize(
    *,
    prompt: str,
    target_engine: str = "gpt-4o",
    model: str | None = None,
    files: list[tuple[str, bytes]] | None = None,
    page_range: str | None = None,
    enable_pxpipe: bool | None = None,
    enable_headroom: bool | None = None,
    enable_its: bool | None = None,
) -> CompileResult:
    """
    Full Split-Execution optimizer pipeline.
    Document body stays verbatim in #D unless ITS drops irrelevant chunks
    or pxpipe packs dense text into a vision image (pointer + image).
    """
    stages: list[str] = ["ingest", "lcs"]
    use_pxpipe = settings.enable_pxpipe if enable_pxpipe is None else enable_pxpipe
    use_headroom = settings.enable_headroom if enable_headroom is None else enable_headroom
    use_its = settings.enable_its if enable_its is None else enable_its

    parts: list[IngestResult] = []
    for name, data in files or []:
        parts.append(ingest_file(name, data, prompt=prompt, page_range=page_range))
    ingested = merge_ingests(parts) if parts else IngestResult()

    raw_doc = ingested.raw_text or ""
    image_b64 = ingested.image_b64
    image_mime = ingested.image_mime
    data_type = ingested.data_type or "text"

    # Hi0 only for JSON-shaped attachments (structured), never arbitrary prose docs
    stripped = raw_doc.strip()
    if raw_doc and (data_type == "json" or stripped.startswith("{") or stripped.startswith("[")):
        packed, applied = maybe_hi0_json_block(raw_doc)
        if applied:
            raw_doc = packed
            stages.append("hi0")

    # Headroom on large non-primary? For Split-Execution golden rule we do NOT
    # semantically compress #D. Headroom is only applied to compressible tool/log-like
    # CSV/log dumps when savings are positive AND type looks like logs.
    if use_headroom and data_type in {"log", "txt", "csv"} and len(raw_doc) > 4000:
        compressed, applied, stage = compress_context(raw_doc)
        if applied:
            # Still preserve content via whitespace/dedupe only
            raw_doc = compressed
            stages.append(stage)

    # ITS gate for multi-chunk docs
    if use_its and raw_doc:
        gated = gate_document(prompt, raw_doc, enabled=True)
        if gated.dropped > 0 and gated.text != raw_doc:
            raw_doc = gated.text
            stages.append(f"its_drop_{gated.dropped}")

    # Conditional pxpipe (vision pack) — replaces dense #D text with pointer+image
    px_applied = False
    if use_pxpipe and raw_doc and not image_b64:
        pointer, pb64, pmime, px_applied = maybe_pack(
            raw_doc,
            model=model,
            target_engine=target_engine,
            enabled=True,
        )
        if px_applied:
            # Keep original in metadata path: envelope gets pointer; image carries text
            # Verbatim guarantee: original text is encoded in the image pixels.
            raw_doc = pointer
            image_b64, image_mime = pb64, pmime
            stages.append("pxpipe")

    nodes = compress_instructions(prompt)
    envelope = assemble_envelope(
        nodes,
        raw_doc,
        data_type,
        target_engine=model or target_engine,
        page_range=page_range,
    )

    baseline = baseline_prompt(prompt, ingested.raw_text or "")
    from tokenish_engine.meters.tokens import count_tokens

    # Mode picker: if LCS scaffolding costs more than the cleaned prompt (common on
    # short chats with no attachments), fall back to cleaned instruction + raw #D.
    if not px_applied:
        clean = nodes.get("clean_prompt") or prompt
        if raw_doc:
            fallback = (
                f"{clean}\n\n### DATA_SOURCE_BLOCK [Type: {data_type.upper()}] (#D)\n"
                f"```text\n{raw_doc}\n```"
            )
        else:
            fallback = clean
        if count_tokens(fallback) < count_tokens(envelope):
            envelope = fallback
            stages.append("lcs_fallback_cheaper")

    # Lossless check for non-pxpipe path
    if not px_applied and raw_doc and not document_verbatim_in_envelope(envelope, raw_doc):
        raise RuntimeError("Split-Execution violation: document text missing from envelope")

    # For meter when pxpipe: compare baseline text tokens vs pointer+flat image token estimate
    if px_applied:
        from tokenish_engine.config import settings as st
        from tokenish_engine.models import MeterReport

        opt_tokens = count_tokens(envelope) + st.pxpipe_image_tokens
        orig = count_tokens(baseline)
        saved = max(0, orig - opt_tokens)
        pct = (saved / orig * 100.0) if orig else 0.0
        meter = MeterReport(
            original_tokens=orig,
            optimized_tokens=opt_tokens,
            saved_tokens=saved,
            saved_pct=round(pct, 2),
            stages=stages,
        )
    else:
        meter = make_meter(baseline, envelope, stages)

    return CompileResult(
        envelope=envelope,
        nodes=nodes,
        meter=meter,
        data_type=data_type,
        image_b64=image_b64,
        image_mime=image_mime,
        stages=stages,
        pxpipe_applied=px_applied,
    )
