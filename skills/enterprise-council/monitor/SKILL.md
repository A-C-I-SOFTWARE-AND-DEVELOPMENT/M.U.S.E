---
name: enterprise-monitor
description: "Post-run reviewer: scans the audit trail, proposes improvements, hands them to the curator."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [enterprise, monitor, learning, audit, curator]
    related_skills: [enterprise-orchestrator, enterprise-judge]
---

# Monitor

After every council run, the Orchestrator calls
`enterprise.monitor.review_session(session_id)`. That function reads
the audit JSONL, buckets failures by kind, and writes one proposal per
kind into `~/.hermes/enterprise/drafts/`.

Your role as the Monitor SKILL is to:

1. **Read the proposals just written.** They are JSON files named
   `prop-XXXXXXXX.json` with the shape defined in
   `enterprise.monitor.ImprovementProposal`.
2. **Decide what to do with each.** Three options:
   * **Promote to curator drafts.** Use the existing
     `agent/curator.py` flow — write a curator-style draft pointing
     at the target_agent's SKILL.md so a human or the next session
     can pick it up.
   * **Apply directly.** Only for very narrow, low-risk changes:
     adding a known-good (domain, action) row to
     `enterprise.policy._BASE_RULES`, or appending a frontmatter tag
     to a SKILL.md. Anything that changes prompt wording, ACL
     entries, or risk classifications goes through the curator.
   * **Defer.** If you can't categorise the failure, leave the
     proposal in `drafts/` and surface the count to the user.
3. **After K=3 confirming sessions** (i.e. the same kind of failure
   appears three runs in a row for the same target_agent), trigger
   curator auto-promotion. The curator's policy is in
   `agent/curator.py`; the Monitor only counts and signals.

## What "improvement" can look like

| kind | typical target | typical change |
|---|---|---|
| `prompt_regression` | a leaf SKILL.md | Tighten the "Structured output" section; add the missing key to the example. |
| `planning_regression` | `enterprise.policy._BASE_RULES` | Add or re-classify an (domain, action) row. |
| `model_disagreement` | a leaf SKILL.md | Lower temperature, or add a deterministic comparator the Judge can ignore. |

## What you must NOT do

* Do not modify a SKILL.md while a session is still running.
* Do not delete or rewrite an existing rule without leaving the
  previous value in the proposal's `extra.previous_value`.
* Do not promote a proposal whose `evidence_event_count == 1` unless
  it carries the `@user-confirmed` extra flag.
