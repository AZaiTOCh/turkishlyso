# Nemean — Privacy Middleware

**Class:** Privacy Middleware (not a subengine plug-in)  
**Product surface:** TOKISH (= free tokenish + Nemean)  
**Incepted (taxonomy):** v0.5.0

## Definition

**Privacy Middleware:** software that sits between the core engine and other applications or data layers to enforce privacy controls, masking, or encryption.

Nemean is that layer for TOKISH — it is **not** an inserted agent and **not** a subengine plug-in.

## Modes (policy)

| Mode | Name | Behavior |
|------|------|----------|
| **C (default)** | Sovereign | Fully local (e.g. Ollama on device) |
| **A (optional)** | Direct | Device → your Azure OpenAI region; **no TOKISH prompt proxy** |

## Product one-liner

TOKISH is free tokenish plus Nemean data privacy on your device — keep AI fully local, or talk straight to your Azure region. We never sit in the middle of your prompts and uploads.

## Relationship to engine menu

Under **engine → middleware**, Nemean is the first Privacy Middleware entry. Resgents and cylinders remain separate native classes.
