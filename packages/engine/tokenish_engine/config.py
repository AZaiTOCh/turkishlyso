from __future__ import annotations

import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENGINE_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _ENGINE_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GPT_TOKENISH", "OPENAI_API_KEY"),
    )
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    google_api_key: str | None = None
    openrouter_api_key: str | None = None
    perplexity_api_key: str | None = None

    max_pdf_pages_full: int = 40
    vision_max_dimension: int = 768
    jpeg_quality: int = 82
    its_threshold: float = 0.4
    enable_pxpipe: bool = True
    enable_headroom: bool = True
    enable_its: bool = True
    enable_faiss_mib: bool = True
    kiosk_mode: bool = False
    memtrove_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MEMTROVE_API_KEY", "MOORCHEH_API_KEY"),
    )
    pxpipe_image_tokens: int = 4761
    pxpipe_min_text_tokens: int = 4000

    openai_primary_model: str = "gpt-4o"
    groq_primary_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    # ONLY gemini-3.5-flash — never other Gemini versions
    gemini_model: str = "gemini-3.5-flash"
    openrouter_free_model: str = "openrouter/free"
    perplexity_model: str = "sonar"
    faiss_mib_bits: int = 512
    faiss_top_k: int = 24


settings = Settings()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def gemini_key() -> str | None:
    return _clean(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or settings.gemini_api_key
        or settings.google_api_key
    )


def openai_key() -> str | None:
    return _clean(
        os.environ.get("GPT_TOKENISH")
        or os.environ.get("OPENAI_API_KEY")
        or settings.openai_api_key
    )


def openrouter_key() -> str | None:
    return _clean(os.environ.get("OPENROUTER_API_KEY") or settings.openrouter_api_key)


def groq_key() -> str | None:
    return _clean(os.environ.get("GROQ_API_KEY") or settings.groq_api_key)


def memtrove_key() -> str | None:
    return _clean(
        os.environ.get("MEMTROVE_API_KEY")
        or os.environ.get("MOORCHEH_API_KEY")
        or settings.memtrove_api_key
    )
