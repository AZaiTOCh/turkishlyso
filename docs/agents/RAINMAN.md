# Rainman

**Role:** After each optimize seal, fact-checks which tokopt cylinders fired and what TOKEX measured — **no LLM**.

**Code:** `packages/engine/tokenish_engine/agents/rainman.py`

**Attribution (v0.4.3+):** prefers **sequential stage deltas** when the pipeline records them; otherwise equal-share of run savings (always caveated).

**Owns:** cylinder ledger for the run.  
**Must not:** invent causal A/B without deltas; call an LLM.

**Incepted:** v0.3
