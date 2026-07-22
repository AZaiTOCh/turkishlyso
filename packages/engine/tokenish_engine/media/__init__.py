"""Media OptComp — Clop-inspired stills + ffmpeg temporal sampling."""

from tokenish_engine.media.clop_opt import (
    STILL_EXTS,
    VIDEO_EXTS,
    ffmpeg_available,
    is_temporal_media,
    media_opt_enabled,
    optimize_still_bytes,
    resolve_ffmpeg,
    sample_media_frames,
    sample_temporal_for_vision,
)

__all__ = [
    "STILL_EXTS",
    "VIDEO_EXTS",
    "ffmpeg_available",
    "is_temporal_media",
    "media_opt_enabled",
    "optimize_still_bytes",
    "resolve_ffmpeg",
    "sample_media_frames",
    "sample_temporal_for_vision",
]
