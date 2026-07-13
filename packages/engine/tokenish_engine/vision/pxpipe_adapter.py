"""
pxpipe-inspired vision packing: render dense text as an image when cheaper.

Only applied when the selected model is vision-capable AND estimated image
tokens beat text tokens.
"""

from __future__ import annotations

import base64
import io
import textwrap

from tokenish_engine.config import settings
from tokenish_engine.meters.tokens import count_tokens


VISION_MODEL_HINTS = (
    "gpt-4o",
    "gpt-4.1",
    "gpt-5",
    "claude-3",
    "claude-4",
    "claude-sonnet",
    "claude-opus",
    "gemini",
    "fable",
    "vision",
    "llava",
)


def model_supports_vision(model: str | None, target_engine: str | None = None) -> bool:
    blob = f"{model or ''} {target_engine or ''}".lower()
    return any(h in blob for h in VISION_MODEL_HINTS)


def should_pxpipe(text: str, model: str | None, target_engine: str | None, enabled: bool) -> bool:
    if not enabled or not text:
        return False
    if not model_supports_vision(model, target_engine):
        return False
    text_tokens = count_tokens(text)
    if text_tokens < settings.pxpipe_min_text_tokens:
        return False
    return text_tokens > settings.pxpipe_image_tokens


def render_text_image(text: str, *, cols: int = 120, font_size: int = 12) -> tuple[str, str]:
    """Return (base64_png, mime). Uses Pillow monospace rendering."""
    from PIL import Image, ImageDraw, ImageFont

    wrapped = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            wrapped.append("")
        else:
            wrapped.extend(textwrap.wrap(paragraph, width=cols) or [""])
    # Cap lines to keep image bounded
    max_lines = 180
    if len(wrapped) > max_lines:
        wrapped = wrapped[: max_lines - 1] + ["…[truncated for pxpipe packing]"]

    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("consola.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    line_h = font_size + 4
    width = cols * (font_size * 6 // 10) + 24
    height = max(64, len(wrapped) * line_h + 24)
    # Bound max dimension roughly like pxpipe dense frames
    width = min(width, 1920)
    height = min(height, 1920)

    img = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    y = 12
    for line in wrapped:
        draw.text((12, y), line, fill=(20, 20, 20), font=font)
        y += line_h
        if y > height - line_h:
            break

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/png"


def maybe_pack(
    document_text: str,
    *,
    model: str | None,
    target_engine: str | None,
    enabled: bool,
) -> tuple[str, str | None, str | None, bool]:
    """
    Returns (text_for_envelope, image_b64, image_mime, applied).
    When applied, envelope text becomes a short pointer; image carries densetext.
    """
    if not should_pxpipe(document_text, model, target_engine, enabled):
        return document_text, None, None, False
    b64, mime = render_text_image(document_text)
    pointer = (
        "[PXPIPE] Dense document context packed as image for vision model. "
        "Read the attached image as the full verbatim #D payload."
    )
    return pointer, b64, mime, True
