from __future__ import annotations

import io
import json

import pytest
from openpyxl import Workbook

from tokenish_engine.compile import assemble_envelope, compress_instructions, document_verbatim_in_envelope
from tokenish_engine.compress.hi0 import serialize_for_llm
from tokenish_engine.ingest import extract_excel, extract_text_file, ingest_file
from tokenish_engine.pipeline import optimize
from tokenish_engine.retrieve import gate_document, its_skill_score
from tokenish_engine.vision.pxpipe_adapter import should_pxpipe


def test_lcs_strips_filler_and_keeps_doc_verbatim():
    prompt = "Please could you help me analyze this financial report and summarize in JSON"
    nodes = compress_instructions(prompt)
    assert "please" not in nodes["clean_prompt"].lower()
    doc = "Revenue was $4.2M in Q4. Exact figure: 4200000"
    env = assemble_envelope(nodes, doc, "pdf", "gpt-4o")
    assert document_verbatim_in_envelope(env, doc)
    assert "#C" in env and "#D" in env or "DATA_SOURCE_BLOCK" in env


def test_claude_xml_envelope():
    nodes = compress_instructions("Summarize the attached PDF")
    doc = "Hello world document body"
    env = assemble_envelope(nodes, doc, "pdf", "claude-sonnet")
    assert "<document_source" in env
    assert doc in env


def test_excel_pipe_matrix():
    wb = Workbook()
    ws = wb.active
    ws.title = "PNL"
    ws.append(["Item", "Amount"])
    ws.append(["Revenue", 42])
    buf = io.BytesIO()
    wb.save(buf)
    result = extract_excel(buf.getvalue())
    assert "Sheet Name: PNL" in result.raw_text
    assert "Revenue | 42" in result.raw_text
    assert result.data_type == "excel_matrix"


def test_hi0_json_smaller_or_equal():
    payload = {"a": 1, "b": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
    text, saved = serialize_for_llm(payload)
    assert "Hi0" in text
    assert saved >= 0


def test_optimize_prompt_only_saves_tokens():
    long_prompt = (
        "Please could you help me kindly analyze this and thank you "
        "would you summarize the key points as bullet points?"
    )
    result = optimize(prompt=long_prompt, target_engine="gpt-4o", enable_pxpipe=False)
    assert result.meter.optimized_tokens <= result.meter.original_tokens
    assert "lcs" in result.stages


def test_optimize_with_text_attachment_preserves_body():
    body = "UNIQUE_TOKEN_XYZ_999 exact contract clause"
    result = optimize(
        prompt="Please analyze this document",
        files=[("note.txt", body.encode("utf-8"))],
        enable_pxpipe=False,
        enable_its=False,
    )
    assert body in result.envelope


def test_its_scores_related_higher():
    q = "quarterly revenue growth financial audit"
    good = "The quarterly revenue growth accelerated in Q4 financial results"
    bad = "The recipe for chocolate cake requires flour sugar and butter"
    assert its_skill_score(q, good) > its_skill_score(q, bad)


def test_its_gate_keeps_something():
    doc = (
        "Alpha revenue metrics and financial audit notes.\n\n"
        "Beta chocolate cake recipe with flour and sugar.\n\n"
        "Gamma more revenue growth and financial statements."
    )
    gated = gate_document("financial revenue audit", doc, threshold=0.0)
    assert gated.text
    assert gated.kept >= 1


def test_pxpipe_threshold_logic():
    small = "hello " * 10
    assert should_pxpipe(small, "gpt-4o", "gpt-4o", True) is False
    # huge text
    huge = ("code line with dense json {\"a\":1}\n" * 2000)
    assert should_pxpipe(huge, "gpt-4o", "gpt-4o", True) is True
    assert should_pxpipe(huge, "llama3", "ollama", True) is False


def test_ingest_json():
    data = json.dumps({"hello": "world", "n": 1}).encode()
    r = ingest_file("data.json", data)
    assert r.data_type == "json"
    assert "hello" in r.raw_text
