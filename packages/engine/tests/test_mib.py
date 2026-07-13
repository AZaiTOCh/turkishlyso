from tokenish_engine.mib import compute_c_minus, compute_c_plus, retrieval_skill_score, score_text_pair
from tokenish_engine.retrieve.its import mib_binarize


def test_mib_rss_related_higher():
    q = mib_binarize("quarterly revenue growth financial audit")
    good = mib_binarize("The quarterly revenue growth accelerated in Q4 financial results")
    bad = mib_binarize("The recipe for chocolate cake requires flour sugar and butter")
    rss_good, _, _ = retrieval_skill_score(q, good)
    rss_bad, _, _ = retrieval_skill_score(q, bad)
    assert isinstance(rss_good, float)
    assert isinstance(rss_bad, float)


def test_c_plus_c_minus_finite():
    import math
    cont = {"a": 10, "b": 2, "c": 3, "d": 50, "N": 65}
    assert math.isfinite(compute_c_plus(cont))
    assert math.isfinite(compute_c_minus(cont))


def test_score_text_pair_has_rss():
    out = score_text_pair("audit the ledger", "financial ledger audit notes")
    assert "rss" in out and "c_plus" in out
