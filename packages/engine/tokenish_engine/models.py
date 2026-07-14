from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokexReport(BaseModel):
    """Fact-checked Token Expenditure rollup for one optimize/chat run."""

    total_tokex: int = Field(description="Counterfactual tokens without optimization")
    tokex_this_run: int = Field(description="Actual optimized tokens for this run")
    saved_tokex: int = Field(description="TOTAL_TOKEX - TOKEX_THIS_RUN (floored at 0)")
    saved_pct: float = Field(description="100 * saved_tokex / total_tokex")
    stages: list[str] = Field(default_factory=list)
    fact_notes: list[str] = Field(default_factory=list)
    # Aliases for older clients
    original_tokens: int = 0
    optimized_tokens: int = 0
    saved_tokens: int = 0


# Back-compat name
MeterReport = TokexReport


class IngestResult(BaseModel):
    raw_text: str = ""
    data_type: str = "text"
    page_count: int | None = None
    image_b64: str | None = None
    image_mime: str | None = None
    # All vision payloads for this ingest (multi-image). image_b64 mirrors images[0].
    images: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompileResult(BaseModel):
    envelope: str
    nodes: dict[str, str]
    meter: TokexReport
    tokex: TokexReport | None = None
    data_type: str
    image_b64: str | None = None
    image_mime: str | None = None
    images: list[dict[str, str]] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    pxpipe_applied: bool = False
    its: dict[str, Any] = Field(default_factory=dict)
    kiosk_blocked: bool = False
    attachment_warning: str | None = None
    rainman: dict[str, Any] = Field(default_factory=dict)
    agatha: dict[str, Any] = Field(default_factory=dict)
    mrs_brown: dict[str, Any] = Field(default_factory=dict)
    neoborg: dict[str, Any] = Field(default_factory=dict)
    fidelity_mode: str = "loyalty"


class ChatMessage(BaseModel):
    role: str
    content: str


class ProviderStatus(BaseModel):
    name: str
    available: bool
    detail: str = ""
    models: list[str] = Field(default_factory=list)
