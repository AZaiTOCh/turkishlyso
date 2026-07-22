# [vToPU](https://github.com/AZaiTOCh/turkishlyso/blob/main/docs/cylinders/CYLINDER_REGISTER.md) Register (OptComp)

**[vToPU](https://github.com/AZaiTOCh/turkishlyso/blob/main/docs/cylinders/CYLINDER_REGISTER.md)** = [Virtual](https://www.ibm.com/docs/en/power8/9080-MHE?topic=processors-virtual) [Token Optimization](https://developer.ibm.com/articles/awb-token-optimization-backbone-of-effective-prompt-engineering/) [Processing Unit](https://medium.com/@ramu.mangalarapu1622/the-story-of-processing-units-understanding-the-brains-behind-modern-machines-39ebbdc83578).

A **tokopt cylinder** is one working stage (virtual core) inside **OptComp** / **[vToPU](https://github.com/AZaiTOCh/turkishlyso/blob/main/docs/cylinders/CYLINDER_REGISTER.md)**.

| # | Cylinders ([virtual cores](https://blog.coolicehost.com/what-is-virtual-core-and-how-does-it-differ-from-physical-core/)) | Type | Status | Since |
|---|----------|------|--------|-------|
| 1 | *Ingestly* | [ingest](INGEST.md) | ON w/ files | v0.1 |
| 2 | *Luxy* | [LCS](LCS.md) | ON | v0.1 |
| 3 | *Volpe* | [split-exec / envelope](SPLIT_EXEC.md) | ON w/ material | v0.1 |
| 4 | *Highzero* | [Hi0](HI0.md) | ON when JSON-ish | v0.2 |
| 5 | *Slimz* | [dedupe](DEDUPE.md) | ON when doc text | v0.2 |
| 6 | *Forciv* | [format_csv](FORMAT_CSV.md) | situational | v0.2 |
| 7 | *Max* | [headroom](https://github.com/headroomlabs-ai/headroom) ([profile](HEADROOM.md)) | ON (gated) | v0.2 |
| 8 | *Chunkdrop* | [ITS](ITS.md) | OFF (consent) | v0.2 |
| 9 | *Chump* | [FAISS / MIB](FAISS_MIB.md) | standby w/ ITS | v0.2 |
| 10 | *Pixish* | [pxpipe](PXPIPE.md) | OFF | v0.1–v0.2 |
| 11 | *Tokegater* | [tokenizer gate](TOKENIZER_GATE.md) | ON | v0.2 |
| 12 | *Previsioner* | [vision (Pillow)](VISION.md) | ON w/ images | v0.1 |
| 13 | *Passopter* | [passthrough](PASSTHROUGH.md) | ON when triggered | v0.1 |
| 14 | *Fidelvid* | [ffmpeg / Clop media](FFMPEG.md) | **ON** (disable with `enable_ffmpeg=false`) | v0.4.3 / ON v0.4.4 |
| 15 | *Memtrove* | [Memtrove](MEMTROVE.md) ([Moorcheh](https://github.com/moorcheh-ai)) | not in optimize path | probe v0.2 |

## Rejected / parked

| # | Item | Status |
|---|------|--------|
| 1 | [Alcubierre](REJECTED_ALCUBIERRE.md) | rejected |
| 2 | [Latents](PARKED_LATENTS.md) | parked |
| 3 | MicrOpt / UltraOpt / AtoOpt (whitespace·font atomism) | assess only — see peer notes |
| 4 | OKF (Google Open Knowledge Format) | park — knowledge catalog, not TOKEX compressor |
