from tokenish_engine.meters.tokens import count_tokens
from tokenish_engine.models import MeterReport


def make_meter(original: str, optimized: str, stages: list[str] | None = None) -> MeterReport:
    orig = count_tokens(original)
    opt = count_tokens(optimized)
    saved = max(0, orig - opt)
    pct = (saved / orig * 100.0) if orig else 0.0
    return MeterReport(
        original_tokens=orig,
        optimized_tokens=opt,
        saved_tokens=saved,
        saved_pct=round(pct, 2),
        stages=list(stages or []),
    )
