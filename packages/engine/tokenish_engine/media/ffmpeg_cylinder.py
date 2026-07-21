"""
ffmpeg / media cylinder (Clop-inspired toolchain pattern).

Uses a local ffmpeg binary when present to sample frames from GIF/video
before Pillow normalize + multimodal send. Default OFF (lossy → consent),
same loyalty posture as ITS.

FFmpeg is not vendored. Resolve via TOKENISH_FFMPEG / settings.ffmpeg_path / PATH.
Windows builds: https://www.gyan.dev/ffmpeg/builds/ or BtbN (see ffmpeg.org/download.html).
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tokenish_engine.config import settings

VIDEO_EXTS = frozenset({"gif", "mp4", "mov", "webm", "mkv", "m4v", "avi", "mpeg", "mpg"})
IMAGE_STILL_EXTS = frozenset({"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"})


def resolve_ffmpeg() -> str | None:
    explicit = (settings.ffmpeg_path or os.environ.get("TOKENISH_FFMPEG") or "").strip()
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return str(p)
    return shutil.which("ffmpeg")


def ffmpeg_available() -> bool:
    return resolve_ffmpeg() is not None


def is_temporal_media(filename: str) -> bool:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in VIDEO_EXTS


def _run_ffmpeg(args: list[str], *, timeout: float = 120.0) -> bool:
    bin_path = resolve_ffmpeg()
    if not bin_path:
        return False
    try:
        proc = subprocess.run(
            [bin_path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def sample_media_frames(
    filename: str,
    data: bytes,
    *,
    enabled: bool | None = None,
    target_fps: float | None = None,
    max_frames: int | None = None,
    max_width: int | None = None,
) -> dict[str, Any]:
    """
    Sample keyframes from GIF/video into JPEG vision payloads.

    Returns dict with keys: applied, images, stage, meta, warning.
    When disabled / unavailable / failed → applied=False and empty images
    (caller falls back to Pillow still-path).
    """
    use = settings.enable_ffmpeg if enabled is None else bool(enabled)
    fps = float(settings.ffmpeg_target_fps if target_fps is None else target_fps)
    cap = int(settings.ffmpeg_max_frames if max_frames is None else max_frames)
    width = int(settings.ffmpeg_max_width if max_width is None else max_width)
    cap = max(1, min(cap, int(settings.max_vision_images)))

    empty = {
        "applied": False,
        "images": [],
        "stage": "",
        "meta": {},
        "warning": None,
    }

    if not use:
        return {**empty, "stage": "ffmpeg_disabled_consent"}
    if not is_temporal_media(filename):
        return empty

    bin_path = resolve_ffmpeg()
    if not bin_path:
        return {
            **empty,
            "stage": "ffmpeg_skipped_no_binary",
            "warning": (
                "ffmpeg not found — install a build from https://www.ffmpeg.org/download.html "
                "(Windows: gyan.dev or BtbN) and set TOKENISH_FFMPEG or PATH"
            ),
        }

    ext = Path(filename).suffix.lower().lstrip(".") or "bin"
    with tempfile.TemporaryDirectory(prefix="tokenish_ffmpeg_") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / f"input.{ext}"
        src.write_bytes(data)
        pattern = tmp_path / "frame_%04d.jpg"
        # Scene-ish sampling: fps filter + scale. Prefer temporal down-sample over dumping all frames.
        vf = f"fps={max(0.2, fps)},scale='min({width},iw)':-2"
        ok = _run_ffmpeg(
            [
                "-y",
                "-i",
                str(src),
                "-vf",
                vf,
                "-frames:v",
                str(cap),
                "-q:v",
                "5",
                str(pattern),
            ]
        )
        if not ok:
            return {
                **empty,
                "stage": "ffmpeg_failed",
                "warning": "ffmpeg frame sample failed; falling back to still ingest",
            }

        frames = sorted(tmp_path.glob("frame_*.jpg"))
        if not frames:
            return {
                **empty,
                "stage": "ffmpeg_no_frames",
                "warning": "ffmpeg produced no frames; falling back to still ingest",
            }

        images: list[dict[str, str]] = []
        for frame in frames[:cap]:
            b64 = base64.b64encode(frame.read_bytes()).decode("ascii")
            images.append({"b64": b64, "mime": "image/jpeg"})

        return {
            "applied": True,
            "images": images,
            "stage": f"ffmpeg_keyframes_{len(images)}",
            "meta": {
                "ffmpeg": bin_path,
                "fps": fps,
                "frames": len(images),
                "max_width": width,
                "source_ext": ext,
                "source_bytes": len(data),
                "toolchain": "clop-inspired (ffmpeg sample → jpeg)",
            },
            "warning": None,
        }
