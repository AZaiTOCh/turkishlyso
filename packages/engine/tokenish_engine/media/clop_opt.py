"""
Clop-inspired media OptComp for tokenish (Python port of Clop semantics).

Clop (GPLv3, macOS) wraps pngquant / jpegoptim / gifsicle / ffmpeg / libvips.
We reimplement the *relevant behaviour* for LLM vision prep — not the Swift UI:

  Image: convert → downscale (never upscale) → compress → keep only if smaller
  Video/GIF: ffmpeg single-pass scale+fps sample → JPEG frames → still-optimize each

External CLIs used when present (same tools Clop uses):
  ffmpeg, pngquant, jpegoptim, gifsicle

Pure-Pillow / pure-ffmpeg paths always work without those extras.
"""

from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tokenish_engine.config import settings

VIDEO_EXTS = frozenset({"gif", "mp4", "mov", "webm", "mkv", "m4v", "avi", "mpeg", "mpg"})
STILL_EXTS = frozenset({"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff", "heic"})


def _which(name: str) -> str | None:
    return shutil.which(name)


def resolve_ffmpeg() -> str | None:
    explicit = (settings.ffmpeg_path or os.environ.get("TOKENISH_FFMPEG") or "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    return _which("ffmpeg")


def ffmpeg_available() -> bool:
    return resolve_ffmpeg() is not None


def media_opt_enabled(enabled: bool | None = None) -> bool:
    """Clop+ffmpeg media path — ON by default (settings.enable_ffmpeg)."""
    if enabled is not None:
        return bool(enabled)
    return bool(settings.enable_ffmpeg)


def is_temporal_media(filename: str) -> bool:
    return Path(filename).suffix.lower().lstrip(".") in VIDEO_EXTS


def _run(cmd: list[str], *, timeout: float = 120.0) -> bool:
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _pillow_clop_still(
    data: bytes,
    *,
    max_dim: int | None = None,
    quality: int | None = None,
    aggressive: bool | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """
    Clop image semantics: downscale (never enlarge) → JPEG ladder → keep if smaller.
    """
    from PIL import Image

    max_dim = int(max_dim if max_dim is not None else settings.vision_max_dimension)
    base_q = int(quality if quality is not None else settings.jpeg_quality)
    aggressive = bool(settings.clop_aggressive if aggressive is None else aggressive)
    meta: dict[str, Any] = {"toolchain": "clop-pillow", "source_bytes": len(data)}

    img = Image.open(io.BytesIO(data))
    # Animated GIF first frame only on still path (temporal path handles multi-frame).
    if getattr(img, "is_animated", False):
        img.seek(0)
        meta["animated_first_frame_only"] = True

    w, h = img.size
    meta["source_size"] = [w, h]
    long_edge = max(w, h)
    if long_edge > max_dim:
        # Clop: never upscale; long-edge cap
        scale = max_dim / float(long_edge)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        meta["downscale"] = [nw, nh]
    else:
        meta["downscale"] = [w, h]

    rgb = img.convert("RGB")
    qualities = [base_q]
    if aggressive:
        qualities.extend([max(40, base_q - 10), max(35, base_q - 20)])

    best = data
    best_meta = dict(meta)
    for q in qualities:
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=q, optimize=True)
        out = buf.getvalue()
        if len(out) < len(best):
            best = out
            best_meta = {**meta, "jpeg_quality": q, "out_bytes": len(out), "mime": "image/jpeg"}

    # Optional jpegoptim pass (Clop tool) when available
    jopt = _which("jpegoptim")
    if jopt and best_meta.get("mime") == "image/jpeg":
        with tempfile.TemporaryDirectory(prefix="tokenish_jopt_") as tmp:
            p = Path(tmp) / "in.jpg"
            p.write_bytes(best)
            if _run([jopt, "--strip-all", "--max=85", "--quiet", str(p)]):
                cand = p.read_bytes()
                if 0 < len(cand) < len(best):
                    best = cand
                    best_meta["jpegoptim"] = True
                    best_meta["out_bytes"] = len(best)

    # Optional pngquant for PNG sources that stay better as PNG (rare after JPEG ladder)
    # Skipped when JPEG already smaller — Clop keeps whichever wins.

    # Clop: reject if not smaller than original (allow equal only if we changed dims)
    if len(best) >= len(data) and best_meta.get("downscale") == meta.get("source_size"):
        best_meta["kept_original"] = True
        best_meta["out_bytes"] = len(data)
        return data, best_meta

    best_meta["applied"] = True
    best_meta["out_bytes"] = len(best)
    return best, best_meta


def _pngquant_then_pillow(data: bytes, ext: str) -> tuple[bytes, dict[str, Any]]:
    """Clop PNG path: pngquant when present, then pillow ladder."""
    pq = _which("pngquant")
    working = data
    meta: dict[str, Any] = {}
    if pq and ext == "png":
        with tempfile.TemporaryDirectory(prefix="tokenish_pq_") as tmp:
            src = Path(tmp) / "in.png"
            dst = Path(tmp) / "out.png"
            src.write_bytes(data)
            # Clop-like: quality band, skip if larger
            if _run([pq, "--quality=65-80", "--skip-if-larger", "--force", "--output", str(dst), str(src)]):
                if dst.is_file() and 0 < dst.stat().st_size < len(data):
                    working = dst.read_bytes()
                    meta["pngquant"] = True
    out, pmeta = _pillow_clop_still(working)
    pmeta.update(meta)
    return out, pmeta


def optimize_still_bytes(data: bytes, filename: str = "image.jpg") -> dict[str, Any]:
    """Return {applied, bytes, mime, b64, meta, stage}."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "png":
        out, meta = _pngquant_then_pillow(data, ext)
    else:
        out, meta = _pillow_clop_still(data)

    mime = "image/jpeg"
    if meta.get("kept_original") and ext == "png":
        mime = "image/png"
    elif meta.get("mime"):
        mime = str(meta["mime"])

    applied = bool(meta.get("applied") or meta.get("pngquant") or meta.get("jpegoptim") or meta.get("downscale") != meta.get("source_size"))
    stage = "clop_still" if applied else "clop_still_noop"
    return {
        "applied": applied,
        "bytes": out,
        "mime": mime,
        "b64": base64.b64encode(out).decode("ascii"),
        "meta": meta,
        "stage": stage,
    }


def _gifsicle_shrink(data: bytes) -> tuple[bytes, dict[str, Any]]:
    """Clop GIF tool when present — lossy-safe optimize, keep if smaller."""
    gs = _which("gifsicle")
    if not gs:
        return data, {}
    with tempfile.TemporaryDirectory(prefix="tokenish_gif_") as tmp:
        src = Path(tmp) / "in.gif"
        dst = Path(tmp) / "out.gif"
        src.write_bytes(data)
        ok = _run([gs, "-O3", "--careful", str(src), "-o", str(dst)])
        if ok and dst.is_file() and 0 < dst.stat().st_size < len(data):
            return dst.read_bytes(), {"gifsicle": True, "out_bytes": dst.stat().st_size}
    return data, {}


def sample_temporal_for_vision(
    filename: str,
    data: bytes,
    *,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """
    Clop video semantics adapted for LLM vision:
    ffmpeg scale (never upscale intent via min(iw,max)) + fps → JPEG frames → clop still each.
    """
    empty = {"applied": False, "images": [], "stage": "", "meta": {}, "warning": None}
    if not media_opt_enabled(enabled):
        return {**empty, "stage": "clop_media_disabled"}
    if not is_temporal_media(filename):
        return empty

    # GIF: optional gifsicle shrink before frame extract
    meta: dict[str, Any] = {"source_bytes": len(data), "toolchain": "clop-ffmpeg"}
    working = data
    if Path(filename).suffix.lower().lstrip(".") == "gif":
        working, gmeta = _gifsicle_shrink(data)
        meta.update(gmeta)

    bin_path = resolve_ffmpeg()
    if not bin_path:
        # Fallback: first-frame clop still
        still = optimize_still_bytes(working, filename)
        return {
            "applied": still["applied"],
            "images": [{"b64": still["b64"], "mime": still["mime"]}],
            "stage": "clop_media_no_ffmpeg_still",
            "meta": {**meta, **still["meta"], "ffmpeg": None},
            "warning": (
                "ffmpeg not found — used Clop still path on first frame. "
                "Install from https://www.ffmpeg.org/download.html and set TOKENISH_FFMPEG"
            ),
        }

    fps = float(settings.ffmpeg_target_fps)
    cap = max(1, min(int(settings.ffmpeg_max_frames), int(settings.max_vision_images)))
    width = int(settings.ffmpeg_max_width)
    ext = Path(filename).suffix.lower().lstrip(".") or "bin"

    with tempfile.TemporaryDirectory(prefix="tokenish_clop_vid_") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / f"input.{ext}"
        src.write_bytes(working)
        pattern = tmp_path / "frame_%04d.jpg"
        # Clop Video.optimise compiles resize into one ffmpeg pass; we sample for vision.
        vf = f"fps={max(0.2, fps)},scale='min({width},iw)':-2:force_original_aspect_ratio=decrease"
        ok = _run(
            [
                bin_path,
                "-y",
                "-i",
                str(src),
                "-vf",
                vf,
                "-frames:v",
                str(cap),
                "-q:v",
                "4" if settings.clop_aggressive else "5",
                str(pattern),
            ]
        )
        if not ok:
            still = optimize_still_bytes(working, filename)
            return {
                "applied": still["applied"],
                "images": [{"b64": still["b64"], "mime": still["mime"]}],
                "stage": "clop_ffmpeg_failed_still",
                "meta": {**meta, **still["meta"]},
                "warning": "ffmpeg sample failed; Clop still fallback",
            }

        frames = sorted(tmp_path.glob("frame_*.jpg"))[:cap]
        if not frames:
            return {**empty, "stage": "clop_ffmpeg_no_frames", "warning": "no frames"}

        images: list[dict[str, str]] = []
        for frame in frames:
            still = optimize_still_bytes(frame.read_bytes(), "frame.jpg")
            images.append({"b64": still["b64"], "mime": still["mime"]})

        meta.update(
            {
                "ffmpeg": bin_path,
                "fps": fps,
                "frames": len(images),
                "max_width": width,
                "source_ext": ext,
            }
        )
        return {
            "applied": True,
            "images": images,
            "stage": f"clop_ffmpeg_keyframes_{len(images)}",
            "meta": meta,
            "warning": None,
        }


# Back-compat aliases used by ingest / earlier ffmpeg_cylinder API
def sample_media_frames(filename: str, data: bytes, *, enabled: bool | None = None, **_kwargs) -> dict[str, Any]:
    return sample_temporal_for_vision(filename, data, enabled=enabled)
