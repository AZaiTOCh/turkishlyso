from tokenish_engine.meters.tokens import count_tokens, tokenizer_name
from tokenish_engine.meters.tokex import compute_tokex
from tokenish_engine.models import TokexReport


def make_meter(original: str, optimized: str, stages: list[str] | None = None) -> TokexReport:
    return compute_tokex(
        baseline_text=original,
        optimized_text=optimized,
        stages=stages,
    )


__all__ = ["count_tokens", "tokenizer_name", "compute_tokex", "make_meter", "TokexReport"]
