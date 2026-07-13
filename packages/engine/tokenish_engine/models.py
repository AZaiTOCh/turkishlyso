from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MeterReport(BaseModel):
    original_tokens: int
    optimized_tokens: int
    saved_tokens: int
    saved_pct: float
    stages: list[str] = Field(default_factory=list)


class IngestResult(BaseModel):
    raw_text: str = ""
    data_type: str = "text"
    page_count: int | None = None
    image_b64: str | None = None
    image_mime: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompileResult(BaseModel):
    envelope: str
    nodes: dict[str, str]
    meter: MeterReport
    data_type: str
    image_b64: str | None = None
    image_mime: str | None = None
    stages: list[str] = Field(default_factory=list)
    pxpipe_applied: bool = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ProviderStatus(BaseModel):
    name: str
    available: bool
    detail: str = ""
    models: list[str] = Field(default_factory=list)
