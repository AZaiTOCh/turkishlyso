"""Media OptComp helpers (ffmpeg / temporal attachments)."""

from tokenish_engine.media.ffmpeg_cylinder import (
    VIDEO_EXTS,
    ffmpeg_available,
    is_temporal_media,
    resolve_ffmpeg,
    sample_media_frames,
)

__all__ = [
    "VIDEO_EXTS",
    "ffmpeg_available",
    "is_temporal_media",
    "resolve_ffmpeg",
    "sample_media_frames",
]
