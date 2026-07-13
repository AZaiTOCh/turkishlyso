from __future__ import annotations

import re

from tokenish_engine.meters.tokens import count_tokens


_FILLER = re.compile(
    r"\b(please|could you|can you help me|can you look at this|"
    r"summarize the attached|analyze this|thank you|kindly|i want you to|"
    r"would you|i need you to|help me)\b",
    re.IGNORECASE,
)


def compress_instructions(human_prompt: str, *, follow_attachment: bool = False) -> dict[str, str]:
    """LCS-style instruction compression — never touch document bodies."""
    clean = _FILLER.sub("", human_prompt or "").strip()
    clean = re.sub(r"\s+", " ", clean)
    lower = clean.lower()

    if follow_attachment:
        context = "Expert[InstructionExecutor]"
        logic = "1.Read(#D)->2.Execute->3.ReplyActionOnly"
        output = "Format:Execute#D_NoRewrite"
        inputs = f"goal={clean[:200]}" if clean else "goal=execute_attachment"
        return {
            "context": context,
            "inputs": inputs,
            "logic": logic,
            "output": output,
            "clean_prompt": clean or (human_prompt or "").strip(),
        }

    if any(w in lower for w in ("read", "ocr", "transcribe", "extract")):
        context = "Expert[VisionOCR/DataExtractor]"
        logic = "1.ScanTarget(#D) -> 2.ParseKeyValues -> 3.Normalize"
    elif any(w in lower for w in ("audit", "financial", "excel", "numbers", "spreadsheet")):
        context = "Expert[FinancialAuditor]"
        logic = "1.ScanMatrix(#D) -> 2.AuditDiscrepancies -> 3.FlagRisks"
    elif any(w in lower for w in ("analyze", "document", "pdf")):
        context = "Expert[DocumentIntelligence]"
        logic = "1.ReadSemanticStructure(#D) -> 2.SynthesizeCoreArcs"
    elif any(w in lower for w in ("code", "refactor", "debug", "implement")):
        context = "Expert[SoftwareEngineer]"
        logic = "1.Parse(#D) -> 2.Plan -> 3.Execute"
    else:
        context = "Expert[GeneralTaskEngine]"
        logic = "1.ParseInput -> 2.ExecuteTransform"

    if "json" in lower:
        output = "Format:ValidJSON"
    elif "table" in lower:
        output = "Format:MarkdownTable"
    else:
        # Prefer clean chat prose — avoid ### / ** markdown report chrome.
        output = "Format:PlainProse;NoMarkdownHeaders;NoBoldDecoration"

    inputs = f"goal={clean[:240]}" if clean else "goal=unspecified"
    return {
        "context": context,
        "inputs": inputs,
        "logic": logic,
        "output": output,
        "clean_prompt": clean or (human_prompt or "").strip(),
    }


def assemble_envelope(
    nodes: dict[str, str],
    raw_document_text: str,
    data_type: str,
    target_engine: str,
    page_range: str | None = None,
) -> str:
    """Split-Execution envelope: compressed control plane + verbatim #D."""
    engine = (target_engine or "").lower()
    doc = raw_document_text or ""
    d_label = f"#D[{page_range}]" if page_range else "#D"

    if "claude" in engine or "anthropic" in engine:
        pages_attr = f' pages="{page_range}"' if page_range else ""
        return (
            f"<context>{nodes['context']}</context>\n"
            f"<inputs>{nodes.get('inputs', '')}</inputs>\n"
            f"<logic>{nodes['logic']}</logic>\n"
            f"<output_format>{nodes['output']}</output_format>\n\n"
            f'<document_source type="{data_type}" id="D"{pages_attr}>\n'
            f"{doc}\n"
            f"</document_source>"
        )

    return (
        f"#C {nodes['context']}\n"
        f"#I {nodes.get('inputs', '')}\n"
        f"#L {nodes['logic']}\n"
        f"#O {nodes['output']}\n\n"
        f"### DATA_SOURCE_BLOCK [Type: {data_type.upper()}] ({d_label})\n"
        f"```text\n{doc}\n```"
    )


def baseline_prompt(human_prompt: str, raw_document_text: str) -> str:
    if raw_document_text:
        return f"{human_prompt}\n\n[Raw Document Context]:\n{raw_document_text}"
    return human_prompt or ""


def wants_full_document_context(human_prompt: str) -> bool:
    """Assess / summarize / fact-check need the whole #D — do not ITS-gut it."""
    lower = (human_prompt or "").strip().lower()
    cues = (
        "assess",
        "analyze",
        "analyse",
        "summarize",
        "summarise",
        "executive summary",
        "exec summary",
        "fact check",
        "fact-check",
        "factchecking",
        "vetting",
        "review",
        "evaluate",
        "critique",
        "one-page",
        "one page",
    )
    return any(c in lower for c in cues)


def wants_instruction_following(human_prompt: str, has_attachment: bool) -> bool:
    """True only when the user wants the model to *execute* attachment instructions."""
    if not has_attachment:
        return False
    lower = (human_prompt or "").strip().lower()
    if not lower:
        return False

    # Analysis / review tasks must NOT lock follow-mode (need ITS + dedupe).
    if wants_full_document_context(human_prompt):
        return False
    analyze_cues = (
        "explain",
        "what does",
        "tell me about",
    )
    if any(c in lower for c in analyze_cues):
        return False

    execute_cues = (
        "follow the instruction",
        "follow instructions",
        "follow the attached",
        "execute the",
        "as written",
        "per the document",
        "per the file",
        "do exactly what",
        "carry out the",
        "run the benchmark",
        "obey the",
    )
    return any(c in lower for c in execute_cues)


def instruction_follow_envelope(
    human_prompt: str,
    raw_document_text: str,
    data_type: str,
    nodes: dict[str, str] | None = None,
) -> str:
    """Minimal split-execution envelope: compact instruction + verbatim #D."""
    clean = (nodes or {}).get("clean_prompt") or (human_prompt or "").strip()
    doc = raw_document_text or ""
    return (
        f"#C {nodes.get('context', 'Expert[InstructionExecutor]') if nodes else 'Expert[InstructionExecutor]'}\n"
        f"#O Execute#D_Only;DoNotRewriteOrSummarize#D\n"
        f"{clean}\n\n"
        f"#D[{data_type}]\n{doc}"
    )


def naive_baseline_prompt(human_prompt: str, raw_document_text: str) -> str:
    """What users typically paste: prompt + full file inline (no optimizer)."""
    if raw_document_text:
        return f"{human_prompt}\n\n---ATTACHED FILE---\n{raw_document_text}"
    return human_prompt or ""


def pick_cheapest_envelope(candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """Return (stage_name, envelope_text) with lowest token count."""
    if not candidates:
        return ("empty", "")
    best_stage, best_text = candidates[0]
    best_n = count_tokens(best_text)
    for stage, text in candidates[1:]:
        n = count_tokens(text)
        if n < best_n:
            best_stage, best_text, best_n = stage, text, n
    return best_stage, best_text


def document_verbatim_in_envelope(envelope: str, raw_document_text: str) -> bool:
    """Lossless guard: raw #D payload must appear unchanged in the envelope."""
    if not raw_document_text:
        return True
    return raw_document_text in envelope
