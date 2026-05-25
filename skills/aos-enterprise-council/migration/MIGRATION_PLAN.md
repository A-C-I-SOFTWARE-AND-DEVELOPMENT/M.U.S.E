# Migration Plan

Phase 1: Freeze the recovered registry.
- Treat existing complete registry files as historical reference.
- Do not dispatch directly from recovered entries.

Phase 2: Establish verified operating registry.
- Use `operating-registry/registry.json` as the daily source of truth.
- Cap active Slack council at 6.
- Promote only high-value recurring specialists.

Phase 3: Reclassify entries.
- Runnable decision agents -> `runnable-agents/`.
- Narrow procedures -> `skills/`.
- Execution lanes -> `workers/`.
- Tone overlays -> `personas/`.
- Business viewpoints -> `product-roles/`.
- Recovered source material -> `archive/recovered-sources/` pointers.

Phase 4: Verify schema and descriptions.
- Run `python skills/aos-enterprise-council/scripts/verify_registry.py`.
- Fix any SKILL.md description longer than 60 characters or not ending in a period.

Phase 5: Gradual promotion.
- Promote recovered entries only when they have current ownership, required inputs, outputs, verification, and gates.

Owner gates: Yes, with authorization.
