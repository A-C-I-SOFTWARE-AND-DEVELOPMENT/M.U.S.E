# MUSE — Current Research Dossier

Purpose: ground MUSE's safety, routing, and memory design in current
primary sources. **Verified facts** are separated from **recommendations**;
vendor benchmark claims are marked **vendor-reported**. No copyrighted or
private materials were downloaded; no credentials are stored here.

_Last refreshed: 2026-05-29. Items marked "verify before relying" were
written from assistant knowledge (cutoff 2026-01) and should be checked
against the cited primary source._

## 1. OWASP Top 10 for LLM Applications (2025) — VERIFIED

Verified via WebSearch on 2026-05-29 against the OWASP Gen AI Security
Project. The 2025 list (prompt injection remains #1 for a second edition):

1. LLM01 Prompt Injection
2. LLM02 Sensitive Information Disclosure
3. LLM03 Supply Chain
4. LLM04 Data and Model Poisoning
5. LLM05 Improper Output Handling
6. LLM06 Excessive Agency
7. LLM07 System Prompt Leakage
8. LLM08 Vector and Embedding Weaknesses
9. LLM09 Misinformation / Model issues
10. LLM10 Unbounded Consumption

**How MUSE maps to these:**
- LLM01/LLM07: owner gates + `route_request` blocking of bypass/exfiltration
  prompts; system prompts are not stored in memory.
- LLM02: Memory Tree write policy rejects secrets/credentials/cookies and
  chain-of-thought; TokenJuice re-screens snippets.
- LLM03/LLM04: clean-room modules, no heavyweight deps, provenance-first
  memory with source trust tiers; vendor claims marked unverified.
- LLM06 Excessive Agency: bounded work packets, builder/reviewer split,
  eight verification gates, no owner-gated execution by MUSE.
- LLM08: Memory Tree is deterministic lexical retrieval (no vector store);
  contested facts excluded from context packs.
- LLM10: TokenJuice hard token budget; monitors track unbounded growth.

Sources:
- [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)
- [OWASP LLM project (OWASP Foundation)](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

## 2. NIST AI RMF & GenAI Profile — verify before relying

- NIST AI Risk Management Framework (AI RMF 1.0) organizes risk work into
  **Govern, Map, Measure, Manage**. MUSE's owner gates + audit ledger +
  decision provenance align with Govern/Manage; monitors + scorecards align
  with Measure.
- NIST also published a Generative AI Profile (NIST-AI-600-1) as a
  companion. Verify current revision before citing specifics.
- Primary source to verify: https://www.nist.gov/itl/ai-risk-management-framework

## 3. Claude / Anthropic models & Claude Code — verify before relying

- Latest family is Claude 4.x (Opus / Sonnet / Haiku). Use the newest,
  most capable model for builder/reviewer lanes; reserve an independent
  frontier model for RC3+ review.
- Claude Code supports memory (CLAUDE.md), subagents, hooks, permissions,
  and skills. MUSE adds `.claude/agents/jarvis-*` (read-only reviewers)
  and `.claude/skills/jarvis-*` without depending on Claude memory as
  enforcement.
- Verify against https://docs.anthropic.com (models, Claude Code, Agent SDK).

## 4. OpenAI / Codex agent & approval patterns — verify before relying

- Codex-style agents use background/eval/approval patterns. MUSE treats
  Codex (or a different model family) as the **independent reviewer** for
  RC2+ changes so builder ≠ reviewer.
- Verify current capabilities against official OpenAI docs before relying.

## 5. OSS / local model serving — verify before relying; benchmarks vendor-reported

- vLLM (continuous batching), SGLang, Ollama, and llama.cpp expose
  OpenAI-compatible endpoints; MUSE emits `local_endpoint_packet` with
  `status="wired_not_confirmed"` and never claims a model is running
  without a smoke request.
- Qwen (coder), DeepSeek, Kimi, GLM family weights are catalogued as lanes.
  Any benchmark numbers are **vendor-reported** until independently
  reproduced and recorded in a `ModelScorecard`.
- Primary sources to verify: https://docs.vllm.ai , https://github.com/sgl-project/sglang ,
  https://ollama.com , https://github.com/ggml-org/llama.cpp

## Recommendations (not facts)
1. Re-run a live primary-source pass (Anthropic, OpenAI, NIST, vendor
   model cards) before any release that cites specifics, and store each
   finding as a `ResearchArtifact` with a freshness date.
2. Treat all model benchmark numbers as vendor-reported until a local
   `ModelScorecard` reproduces them.
3. Keep prompt-injection defenses (LLM01) as the top routing concern: the
   packetizer already blocks bypass/exfiltration intents.
