# First PR Plan

Title: Refactor AOS council into verified Hermes operating registry

Scope:
- Shorten the AOS skill description to Hermes-compatible format.
- Add verified operating registry and schema.
- Add active council, specialists, skills, workers, personas, product-role, and archive boundaries.
- Add Slack team usage rules.
- Add registry verification script.
- Set owner gates to yes with authorization.

Files expected:
- `skills/aos-enterprise-council/SKILL.md`
- `skills/aos-enterprise-council/operating-registry/registry.json`
- `skills/aos-enterprise-council/operating-registry/schema.json`
- `skills/aos-enterprise-council/operating-registry/README.md`
- `skills/aos-enterprise-council/scripts/verify_registry.py`
- `skills/aos-enterprise-council/runnable-agents/active-council.md`
- `skills/aos-enterprise-council/specialists/README.md`
- `skills/aos-enterprise-council/skills/README.md`
- `skills/aos-enterprise-council/workers/README.md`
- `skills/aos-enterprise-council/personas/README.md`
- `skills/aos-enterprise-council/product-roles/README.md`
- `skills/aos-enterprise-council/archive/recovered-sources/README.md`
- `skills/aos-enterprise-council/slack/SLACK_TEAM_USAGE_RULES.md`
- `skills/aos-enterprise-council/migration/MIGRATION_PLAN.md`
- `skills/aos-enterprise-council/migration/FIRST_PR_PLAN.md`

Validation:
- `python skills/aos-enterprise-council/scripts/verify_registry.py`
- `git diff --check`
- Review that no new always-active agents were added.
- Review that full recovered registry remains available under `registry/`.

Rollback:
- Remove new operating-registry and classification folders.
- Restore prior `SKILL.md` if routing needs to revert.
