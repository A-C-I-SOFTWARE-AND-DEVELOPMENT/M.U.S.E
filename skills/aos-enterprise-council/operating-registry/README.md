# AOS Operating Registry

This directory is the verified operating registry. It is intentionally smaller than the recovered registry and is the only registry used for daily Slack council work.

Historical source material remains in `../registry/` and `../source-snapshots/`. Do not dispatch directly from historical material until an entry is promoted into `registry.json` and passes `skills/aos-enterprise-council/scripts/verify_registry.py`.

Registry sections:
- `active_council`: always-available daily Slack council, max 6.
- `domain_specialists`: on-demand specialists with use boundaries and verification.
- `super_specialist_skills`: narrow procedures promoted as skills.
- `worker_templates`: execution lanes that cannot make decisions.
- `separated_collections`: canonical folder map.
