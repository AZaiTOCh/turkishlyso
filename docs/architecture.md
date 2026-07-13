# Tokenish architecture (v0.1)

## Split-Execution

1. **Upstream ingest** — pdf / docx / xlsx / text / image (+ OCR intent)
2. **LCS** — compress human instructions only (`#C #I #L #O` or Claude XML)
3. **#D** — verbatim extracted document text
4. **Optional** — Hi0 (JSON), Headroom (log/csv whitespace), ITS chunk gate, pxpipe vision pack
5. **Dispatch** — Ollama / OpenAI / Anthropic / Groq

## Golden rule

Never run uploaded document bodies through semantic instruction compression.
