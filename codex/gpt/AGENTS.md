# Codex/GPT Agent Registry Instructions

This directory is the permanent GPT/Codex-facing registry surface for MUSE agents.

When operating here:

1. Treat `permanent-agent-registry.json` as the manifest.
2. Treat `permanent_agent_registry.py` as the machine-readable loader.
3. Treat the AOS Enterprise Council registry markdown files as canonical source of truth:
   - `skills/aos-enterprise-council/registry/AOS_AGENT_REGISTRY_COMPLETE.md`
   - `skills/aos-enterprise-council/registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md`
4. Do not invent agent names. If a requested agent is missing, add it to the canonical registry first.
5. Preserve GPT/Codex separation:
   - GPT owns intake, strategy, critique, synthesis, and owner handoff.
   - Codex owns implementation review, bounded fixes, refactors, code audits, test/debug work, and PR handoff packets.
6. Preserve MUSE gates before calling work done: Planning, Build, Review, Test, Security, Release, Owner Approval, Rollback.
7. Owner-gated actions stay gated. This registry does not authorize deploys, public posts, credential/OAuth changes, spending, publishing, app-store submission, DNS changes, or main-branch merges.

Verification command:

```bash
python -m codex.gpt.permanent_agent_registry --summary
```
