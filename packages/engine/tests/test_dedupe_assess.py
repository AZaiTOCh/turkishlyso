from tokenish_engine.compile import wants_instruction_following
from tokenish_engine.compress.dedupe import dedupe_document_sections
from tokenish_engine.meters.tokens import count_tokens
from tokenish_engine.pipeline import optimize


def test_assess_is_not_follow_mode():
    assert wants_instruction_following("Assess the attached doc.", True) is False
    assert wants_instruction_following("Analyze this PDF", True) is False


def test_follow_instructions_is_follow_mode():
    assert wants_instruction_following(
        "Deeply follow the instructions in the attached document", True
    ) is True


def test_dedupe_near_duplicate_pages_with_page_numbers():
    body = (
        "Grounded Visual Exhaustion Benchmark v1.0. "
        "Analyze Bosch Waldo Raphael exhaustively. Never guess. Unknown if uncertain. "
    ) * 25
    doc = (
        f"{body}\nPage 1\n--- PAGE BREAK ---\n"
        f"{body}\nPage 2\n--- PAGE BREAK ---\n"
        f"{body}\nPage 3\n"
    )
    out, dropped, stage = dedupe_document_sections(doc)
    assert dropped >= 2
    assert count_tokens(out) < count_tokens(doc) * 0.5
    assert "Bosch" in out


def test_dedupe_form_feed_pages():
    body = ("GVEB benchmark grounded visual exhaustion. " * 40)
    doc = f"{body}\f{body}\f{body}"
    out, dropped, stage = dedupe_document_sections(doc)
    assert dropped >= 2
    assert count_tokens(out) < count_tokens(doc)



def test_assess_duplicate_doc_saves_tokens():
    block = (
        "Grounded Visual Exhaustion Benchmark v1.0. "
        "Analyze Bosch Waldo Raphael exhaustively. Never guess. "
    ) * 40
    doc = "\n--- PAGE BREAK ---\n".join([block, block, block, block])
    result = optimize(
        prompt="Assess the attached doc.",
        files=[("gveb.txt", doc.encode("utf-8"))],
        target_engine="gemini-3.5-flash",
        model="gemini-3.5-flash",
        enable_pxpipe=False,
    )
    assert result.tokex.saved_tokex > 100
    assert result.tokex.saved_pct > 5
    assert any(s.startswith("dedupe_drop_") for s in result.stages)
    assert "its_skipped_assess" in result.stages
    assert not any(s.startswith("its_drop_") for s in result.stages)


def test_assess_keeps_unique_document_body():
    # Unique paragraphs must survive (no ITS gutting on assess).
    paras = [
        f"Section {i}: freefactorial G-Triangle pattern definition and recurrence. " * 8
        for i in range(12)
    ]
    doc = "\n\n".join(paras)
    result = optimize(
        prompt="Deeply assess the attached. then generate a one page exec summary after fact checking everything.",
        files=[("math.txt", doc.encode("utf-8"))],
        target_engine="gemini-3.5-flash",
        model="gemini-3.5-flash",
        enable_pxpipe=False,
        enable_its=True,
    )
    assert "its_skipped_assess" in result.stages
    assert "Freefactorial" in result.envelope or "freefactorial" in result.envelope.lower()
    assert result.tokex.tokex_this_run > 200

