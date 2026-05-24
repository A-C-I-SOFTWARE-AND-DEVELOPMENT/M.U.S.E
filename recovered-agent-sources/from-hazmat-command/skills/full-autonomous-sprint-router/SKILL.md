---
name: full-autonomous-sprint-router
description: Use at the start of a multi-domain or ambiguous request to classify the work, route to the right workflow and subagents, and avoid overbuilding. Inspects the request, names the risk class, picks the workflow, names the builder / reviewer / verifier, and proposes a scoped todo list before any code is written.
disable-model-invocation: true
---

# full-autonomous-sprint-router

## When to use

Owner gives an open-ended or multi-domain request ("ship the
pilot-ready Stage X", "make the trust portal procurement-grade",
"resolve the Base44 cutover decision"). Run this skill BEFORE
writing code.

## Method

1. **Restate the request.** One paragraph. Confirm the owner's
   stated outcome.
2. **Classify the work.**
   - Risk class per
     `docs/governance/03-change-risk-matrix.md`.
   - Workflow per `docs/governance/04-workflow-router.md`.
   - Domains touched (engineering, security, compliance, commercial,
     legal, mobile, release, docs).
3. **Pick the team.**
   - Builder: usually `engineering-architecture-factory`,
     `research-evidence-bureau`, `commercial-strategy-growth-office`,
     or `legal-policy-contracts-trust-office`.
   - Independent reviewer: `principal-code-reviewer` (code) and/or
     `assurance-security-compliance-office` (RC3).
   - Third verifier (RC3): `research-evidence-bureau` for cited
     standards, `knowledge-operations-self-improvement` for doc
     integrity.
4. **Owner walls check.** Does the request hint at an action that
   sits behind an owner-only wall (publish / merge / push to
   main / DNS / store submission / ad spend / OAuth / social)?
   If yes, name the wall and split the autonomous work from the
   owner-only action.
5. **Scoped todo list.** No more than 8 items. Each item maps to
   a subagent and a skill.
6. **Skip overbuild.** Reject anything not strictly required by
   the request. Add a "deliberately out of scope" section.
7. **Hand off** to `chief-orchestrator` to execute the routing
   decision.

## Output

```
REQUEST: <one paragraph>
RISK CLASS: RCx
WORKFLOW: docs/workflows/<file>.md
DOMAINS: ...
BUILDER: <agent>
INDEPENDENT REVIEWER: <agent>
VERIFIER (RC3): <agent>
OWNER WALLS: <walls touched + owner action>
TODO (≤ 8):
1. ...
DELIBERATELY OUT OF SCOPE:
- ...
```

## Anti-patterns

- Routing an RC3 surface to the builder alone with no reviewer.
- Routing legal work to engineering.
- Routing a "demo prep" request without involving
  `product-pilot-experience-studio` and `pilot-readiness-judge`.
- Letting the todo list grow past 8 items.
