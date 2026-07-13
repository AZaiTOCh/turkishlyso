from __future__ import annotations

from tokenish_engine.compile import (
    assemble_envelope,
    baseline_prompt,
    compress_instructions,
    document_verbatim_in_envelope,
    instruction_follow_envelope,
    naive_baseline_prompt,
    pick_cheapest_envelope,
    wants_instruction_following,
)
from tokenish_engine.compress import compress_context, maybe_hi0_json_block
from tokenish_engine.config import settings
from tokenish_engine.ingest import IngestResult, ingest_file, merge_ingests
from tokenish_engine.meters import compute_tokex
from tokenish_engine.meters.tokens import count_tokens
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
    kiosk_mode: bool | None = None,
) -> CompileResult:
    stages: list[str] = ["ingest", "lcs"]
    use_pxpipe = settings.enable_pxpipe if enable_pxpipe is None else enable_pxpipe
    use_headroom = settings.enable_headroom if enable_headroom is None else enable_headroom
    use_its = settings.enable_its if enable_its is None else enable_its
    use_kiosk = settings.kiosk_mode if kiosk_mode is None else kiosk_mode
    its_meta: dict = {}
    kiosk_blocked = False

    parts: list[IngestResult] = []
    for name, data in files or []:
        parts.append(ingest_file(name, data, prompt=prompt, page_range=page_range))
    ingested = merge_ingests(parts) if parts else IngestResult()

    raw_doc = ingested.raw_text or ""
    image_b64 = ingested.image_b64
    image_mime = ingested.image_mime
    data_type = ingested.data_type or "text"
    original_doc = ingested.raw_text or ""

    stripped = raw_doc.strip()
    if raw_doc and (data_type == "json" or stripped.startswith("{") or stripped.startswith("[")):
        packed, applied = maybe_hi0_json_block(raw_doc)
        if applied:
            raw_doc = packed
            stages.append("hi0")

    has_attachment = bool(raw_doc.strip() or image_b64)
    follow_mode = wants_instruction_following(prompt, has_attachment and bool(raw_doc.strip()))

    if use_headroom and not follow_mode and data_type in {"log", "txt", "csv", "pdf"} and len(raw_doc) > 4000:
        compressed, applied, stage = compress_context(raw_doc)
        if applied:
            raw_doc = compressed
            stages.append(stage)

    if use_its and raw_doc:
        gated = gate_document(
            prompt,
            raw_doc,
            enabled=True,
            kiosk_mode=use_kiosk if not follow_mode else False,
        )
        its_meta = {
            "dropped": gated.dropped,
            "kept": gated.kept,
            "scores": gated.scores,
            "labels": gated.labels,
            "kiosk_blocked": gated.kiosk_blocked,
        }
        if gated.kiosk_blocked and not follow_mode:
            kiosk_blocked = True
            raw_doc = ""
            stages.append("its_kiosk_block")
        elif gated.dropped > 0 and gated.text != raw_doc:
            raw_doc = gated.text
            stages.append(f"its_drop_{gated.dropped}")

    px_applied = False
    px_surcharge = 0
    px_pointer = ""
    if use_pxpipe and raw_doc and not image_b64 and not kiosk_blocked:
        pointer, pb64, pmime, px_applied = maybe_pack(
            raw_doc,
            model=model,
            target_engine=target_engine,
            enabled=True,
        )
        if px_applied:
            px_pointer = pointer
            image_b64, image_mime = pb64, pmime
            px_surcharge = settings.pxpipe_image_tokens
            stages.append("pxpipe")

    nodes = compress_instructions(prompt, follow_attachment=follow_mode)

    if not raw_doc and not image_b64 and count_tokens(prompt) < 32:
        envelope = prompt.strip()
        stages.append("passthrough_short")
        tokex = compute_tokex(
            baseline_text=baseline_prompt(prompt, ""),
            optimized_text=envelope,
            stages=stages,
            fact_notes=["short prompt — optimizer skipped (nothing to compress)"],
        )
        return CompileResult(
            envelope=envelope,
            nodes=nodes,
            meter=tokex,
            tokex=tokex,
            data_type=data_type,
            image_b64=image_b64,
            image_mime=image_mime,
            stages=stages,
            pxpipe_applied=False,
            its=its_meta,
            kiosk_blocked=kiosk_blocked,
        )

    if kiosk_blocked:
        envelope = (
            "#C Expert[HonestyGate]\n"
            "#L 1.RefuseGuess -> 2.AskForBetterSource\n"
            "#O Format:StaticUnknown\n\n"
            "Kiosk Mode: ITS skill scores fell below threshold. "
            "No low-relevance context was injected."
        )
    elif raw_doc or image_b64:
        candidates: list[tuple[str, str]] = []
        clean = nodes.get("clean_prompt") or prompt.strip()

        if follow_mode:
            candidates.append(
                ("instruction_follow", instruction_follow_envelope(prompt, raw_doc, data_type, nodes))
            )

        candidates.append(
            (
                "split_exec",
                assemble_envelope(
                    nodes,
                    raw_doc,
                    data_type,
                    target_engine=model or target_engine,
                    page_range=page_range,
                ),
            )
        )

        if raw_doc:
            candidates.append(("bare", f"{prompt.strip()}\n\n{raw_doc}"))
            candidates.append(
                (
                    "minimal",
                    f"{clean}\n\n#D[{data_type}]\n{raw_doc}",
                )
            )
            candidates.append(
                (
                    "naive_block",
                    f"{clean}\n\n### DATA_SOURCE_BLOCK [Type: {data_type.upper()}] (#D)\n```text\n{raw_doc}\n```",
                )
            )

        if px_applied and px_pointer:
            candidates.append(("pxpipe_pointer", f"{clean}\n\n{px_pointer}"))

        stage_pick, envelope = pick_cheapest_envelope(candidates)
        stages.append(stage_pick)
    else:
        envelope = nodes.get("clean_prompt") or prompt.strip()
        stages.append("prompt_only")

    baseline = (
        naive_baseline_prompt(prompt, original_doc)
        if original_doc
        else baseline_prompt(prompt, original_doc)
    )

    if not px_applied and not kiosk_blocked and raw_doc:
        if not document_verbatim_in_envelope(envelope, raw_doc):
            raise RuntimeError("Split-Execution violation: document text missing from envelope")

    tokex = compute_tokex(
        baseline_text=baseline,
        optimized_text=envelope,
        stages=stages,
        pxpipe_image_tokens=px_surcharge,
        fact_notes=[
            "TOTAL_TOKEX = tokens(naive prompt + raw attachment)",
            "TOKEX_THIS_RUN = tokens(optimized envelope)"
            + (f" + pxpipe_image({px_surcharge})" if px_surcharge else ""),
            "SAVED_TOKEX = max(0, TOTAL_TOKEX - TOKEX_THIS_RUN)",
        ],
    )

    return CompileResult(
        envelope=envelope,
        nodes=nodes,
        meter=tokex,
        tokex=tokex,
        data_type=data_type,
        image_b64=image_b64,
        image_mime=image_mime,
        stages=stages,
        pxpipe_applied=px_applied,
        its=its_meta,
        kiosk_blocked=kiosk_blocked,
    )
