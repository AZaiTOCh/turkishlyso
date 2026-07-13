from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    ollama_host: str = "http://127.0.0.1:11434"
    max_pdf_pages_full: int = 40
    vision_max_dimension: int = 768
    jpeg_quality: int = 82
    its_threshold: float = 0.4
    enable_pxpipe: bool = True
    enable_headroom: bool = True
    enable_its: bool = True
    # Flat vision token estimate for a packed PNG (pxpipe-style)
    pxpipe_image_tokens: int = 4761
    pxpipe_min_text_tokens: int = 6000


settings = Settings()
