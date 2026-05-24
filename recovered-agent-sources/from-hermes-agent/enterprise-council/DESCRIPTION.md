---
description: Autonomous multi-agent enterprise system — Orchestrator + Finance/HR/CustomerService/Operations/Sales leaves + Judge + Monitor, with secure-by-construction credential retrieval and a self-improvement loop.
---

# Enterprise Council

Eight agents working together to take a single one-tap goal end-to-end:

  * **orchestrator/** — decomposes the goal, classifies risk, dispatches
    domain leaves, runs the judge, escalates HIGH-risk steps to the user.
  * **finance/**, **hr/**, **customer-service/**, **operations/**,
    **sales/** — domain leaves with named sub-skills and adapter-backed
    tool calls. Always fetch credentials via `fetch_secret(...)` at the
    moment of use; never store, log, or echo the returned value.
  * **judge/** — validates every leaf's structured result against a
    schema, the policy taxonomy, and an optional second-opinion pass.
  * **monitor/** — reads the post-run audit trail and writes
    improvement proposals into Hermes' drafts lane.

Shared docs live in `shared/` (policy and audit conventions). The
runtime is `/home/user/hermes-agent/enterprise/` — Python shim that
the SKILL.md prompts reference.
