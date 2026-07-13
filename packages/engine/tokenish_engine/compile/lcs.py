from __future__ import annotations

import re


_FILLER = re.compile(
    r"\b(please|could you|can you help me|can you look at this|"
    r"summarize the attached|analyze this|thank you|kindly|i want you to|"
    r"would you|i need you to|help me)\b",
    re.IGNORECASE,
)


def compress_instructions(human_prompt: str) -> dict[str, str]:
    """LCS-style instruction compression — never touch document bodies."""
    clean = _FILLER.sub("", human_prompt or "").strip()
    clean = re.sub(r"\s+", " ", clean)
    lower = clean.lower()

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
    elif any(w in lower for w in ("summary", "summarize", "bullet")):
        output = "Format:BulletPoints[Dense]"
    elif "table" in lower:
        output = "Format:MarkdownTable"
    else:
        output = "Format:DenseExecutiveSummary"

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


def document_verbatim_in_envelope(envelope: str, raw_document_text: str) -> bool:
    """Lossless guard: raw #D payload must appear unchanged in the envelope."""
    if not raw_document_text:
        return True
    return raw_document_text in envelope
