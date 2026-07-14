"""
TOKEX — Token Expenditure accounting (fact-checked).

Definitions (per run):
  TOTAL_TOKEX     Counterfactual prompt size if no optimizer ran
                  (raw human prompt + raw extracted attachment text)
                  + counterfactual vision estimate when images are attached.
  TOKEX_THIS_RUN  Actual optimized prompt size + billed vision surcharge
                  (pxpipe and/or per attached vision image).
  SAVED_TOKEX     max(0, TOTAL_TOKEX - TOKEX_THIS_RUN)
  SAVED_PCT       100 * SAVED_TOKEX / TOTAL_TOKEX   (0 if TOTAL_TOKEX == 0)

Never claim vision savings without billing vision tokens on BOTH sides.
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
    vision_image_tokens: int = 0,
    baseline_vision_tokens: int = 0,
    fact_notes: list[str] | None = None,
) -> TokexReport:
    vision_run = max(0, int(pxpipe_image_tokens)) + max(0, int(vision_image_tokens))
    vision_base = max(0, int(baseline_vision_tokens))
    # If run bills vision but baseline did not, mirror so % cannot invent savings.
    if vision_run and not vision_base:
        vision_base = vision_run
    total = count_tokens(baseline_text) + vision_base
    run = count_tokens(optimized_text) + vision_run
    saved = max(0, total - run)
    pct = round((saved / total) * 100.0, 2) if total > 0 else 0.0
    notes = list(fact_notes or [])
    notes.append(f"tokenizer={tokenizer_name()}")
    if pxpipe_image_tokens:
        notes.append(f"pxpipe_image_surcharge={pxpipe_image_tokens}")
    if vision_image_tokens:
        notes.append(f"vision_image_surcharge={vision_image_tokens}")
    if vision_base:
        notes.append(f"baseline_vision_tokens={vision_base}")
    return TokexReport(
        total_tokex=total,
        tokex_this_run=run,
        saved_tokex=saved,
        saved_pct=pct,
        stages=list(stages or []),
        fact_notes=notes,
        original_tokens=total,
        optimized_tokens=run,
        saved_tokens=saved,
    )
