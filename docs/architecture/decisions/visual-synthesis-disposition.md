# Decision: Visual synthesis — keep the multi-provider stack, decline a bespoke MGT

This follows the M.U.S.E decision-ledger format
([`../../orchestration/decision-ledger.md`](../../orchestration/decision-ledger.md)),
adapted for an architecture decision.

## Decision

Keep and extend M.U.S.E's existing **multi-provider image/video generation**
stack. Do **not** build or vendor a bespoke masked-generative-transformer (MGT)
image model as proposed in the "Omni-Agent" evaluation.

## Plain English Summary

We already generate images and video through several swappable providers. Building
our own image model would be a large effort that duplicates what we have, on the
strength of speed claims we could not verify. We decline it and keep the plug-in
approach, which lets us add any future model — including an MGT — as a backend
without touching the agent core.

## Context

An external evaluation proposed anchoring M.U.S.E's visual synthesis on a custom
Google-"Muse"-style MGT, citing large speed advantages over diffusion models.
M.U.S.E is a local-first, provider-agnostic agent; visual synthesis is already a
plugin domain.

## Evidence Reviewed

- [`plugins/image_gen/`](../../../plugins/image_gen/) — OpenAI `gpt-image-2`,
  Google Gemini, xAI `grok-imagine`, FAL (flux-2, nano-banana-pro, recraft,
  ideogram, qwen-image, …).
- [`plugins/video_gen/`](../../../plugins/video_gen/) — xAI `grok-imagine-video`,
  FAL (Veo 3.1, Kling v3 4K, Pixverse v6, Seedance 2.0, LTX).
- [`toolsets.py`](../../../toolsets.py) — `image_generate` / `video_generate` /
  `vision_analyze` tools wired into the default toolsets.
- The cited MGT latency/throughput figures are **vendor-reported and
  unverified** against primary sources.

## Options Considered

1. **Keep the multi-provider plugin stack** (recommended).
2. Build/vendor a bespoke MGT image model and make it the default.
3. Add a hosted MGT endpoint as one more provider plugin if/when a credible one
   exists.

## Why This Choice

Option 1 already delivers state-of-the-art outputs across many models, is
opt-in/owner-controlled, costs no engineering to maintain, and keeps the agent
core untouched. The plugin seam means Option 3 stays open at near-zero cost — a
future MGT is just another backend behind `image_generate`.

## Rejected Alternatives

- **Bespoke MGT (Option 2):** large build, ongoing training/serving cost, and
  redundant with the existing stack; justified only by unverified speed claims.

## Cost / Latency / Quality Tradeoff

Multi-provider routing lets the owner pick the cost/latency/quality point per
request (e.g. a cheap FAL tier vs. a premium model). A single bespoke model would
fix that tradeoff and add serving cost — `spend_money` is owner-gated regardless.

## Validation Plan

Provider plugins are exercised by `uv run pytest tests/plugins -k 'image or video'`
and are inert unless enabled via the `plugins.enabled` allowlist.

## Approval Required

None for this decision — it is "keep current architecture." Adopting a *hosted*
MGT later would touch `spend_money` (owner-gated) and would get its own decision.

## Final Decision

Adopt Option 1. Record the MGT proposal as **DISCARD** in
[`../MUSE_TECHNOLOGY_DISPOSITION.md`](../MUSE_TECHNOLOGY_DISPOSITION.md).

## Confidence

High.

## Open Risks

If a hosted MGT later shows a verified, decisive advantage, revisit as a new
provider plugin (Option 3) — not a core rewrite.

## Rollback Plan

No code changed by this decision; it documents the existing architecture. Reverting
means deleting this record.
