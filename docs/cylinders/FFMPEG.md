# ffmpeg / Clop media cylinder

**Status:** **ON by default** (v0.4.4) — Clop-inspired still + ffmpeg temporal sampling for vision.

## Behaviour (ported from Clop semantics)

Clop (macOS, GPLv3) uses pngquant / jpegoptim / gifsicle / ffmpeg / libvips. tokenish reimplements the **relevant OptComp behaviour** in Python:

| Path | What runs |
|------|-----------|
| **Still images** | Downscale (never upscale) → JPEG quality ladder → keep only if smaller; optional `pngquant` / `jpegoptim` if on PATH |
| **GIF** | Optional `gifsicle -O3` then ffmpeg frame sample |
| **Video** | ffmpeg `fps` + `scale=min(max,iw)` → JPEG keyframes → Clop still each frame |

**Code:** `packages/engine/tokenish_engine/media/clop_opt.py`  
**Form flag:** `enable_ffmpeg` (default **true**; set `false` to disable)

## Binaries

- **Required for video/GIF multi-frame:** `ffmpeg` — [download](https://www.ffmpeg.org/download.html) (Windows: gyan.dev / BtbN). Set `TOKENISH_FFMPEG` or PATH.
- **Optional (Clop tools):** `pngquant`, `jpegoptim`, `gifsicle` — used when found.

Without ffmpeg, temporal files fall back to Clop still on the first frame.
