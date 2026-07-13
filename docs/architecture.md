# Tokenish architecture (v0.2)

## Split-Execution

1. **Upstream ingest** — pdf / docx / xlsx / text / image
2. **Evidence LCS** — compress human instructions only (delete filler; never vowel shorthand)
3. **Optional format rewrite** — flat JSON tables → CSV when cheaper
4. **#D** — verbatim document text (follow-mode never lossy-compresses)
5. **Optional** — Hi0 (JSON), Headroom (non-follow), Memtrove ITS + FAISS binary MIB gate, pxpipe vision pack
6. **Tokenizer gate** — keep a transform only if tokens drop
7. **Dispatch** — Gemini **3.5 flash only** / OpenRouter (Argus preflight)

## Install surface

- `pip install tokenish` → `tokenish` CLI starts daemon + UI
- Windows `.exe` via PyInstaller (`packages/engine/packaging`)

## Golden rule

Never run uploaded document bodies through semantic instruction compression in follow mode. Never treat character-level stenography as a token saver. Never route to non-3.5 Gemini models.
