"""
TOKEX — Token Expenditure accounting (fact-checked).

Definitions (per run):
  TOTAL_TOKEX     Counterfactual prompt size if no optimizer ran
                  (raw human prompt + raw extracted attachment text).
  TOKEX_THIS_RUN  Actual optimized prompt size sent / prepared for the LLM
                  (compiled envelope text tokens; + flat vision image estimate
                  when pxpipe packs context into an image).
  SAVED_TOKEX     max(0, TOTAL_TOKEX - TOKEX_THIS_RUN)
  SAVED_PCT       100 * SAVED_TOKEX / TOTAL_TOKEX   (0 if TOTAL_TOKEX == 0)

Tokenizer: tiktoken cl100k_base when available (OpenAI-family proxy).
Fallback: ceil(chars/4) only if tiktoken cannot load — flagged in report.

Image path: when pxpipe applies, TOKEX_THIS_RUN includes a documented flat
vision surcharge (config.pxpipe_image_tokens), not a free-form guess.
"""

from __future__ import annotations

from tokenish_engine.meters.tokens import count_tokens, tokenizer_name
from tokenish_engine.models import TokexReport


def compute_tokex(
    *,
    baseline_text: str,
    optimized_text: str,
    stages: list[str] | None = None,
    pxpipe_image_tokens: int = 0,
    fact_notes: list[str] | None = None,
) -> TokexReport:
    total = count_tokens(baseline_text)
    run = count_tokens(optimized_text) + max(0, int(pxpipe_image_tokens))
    saved = max(0, total - run)
    pct = round((saved / total) * 100.0, 2) if total > 0 else 0.0
    notes = list(fact_notes or [])
    notes.append(f"tokenizer={tokenizer_name()}")
    if pxpipe_image_tokens:
        notes.append(f"pxpipe_image_surcharge={pxpipe_image_tokens}")
    return TokexReport(
        total_tokex=total,
        tokex_this_run=run,
        saved_tokex=saved,
        saved_pct=pct,
        stages=list(stages or []),
        fact_notes=notes,
        # backward-compatible aliases used by older UI fields
        original_tokens=total,
        optimized_tokens=run,
        saved_tokens=saved,
    )
