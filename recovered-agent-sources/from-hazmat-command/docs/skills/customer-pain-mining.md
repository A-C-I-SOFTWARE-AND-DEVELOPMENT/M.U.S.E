# Skill — customer-pain-mining

## Purpose

Synthesize practitioner pain — safety_manager, dispatcher,
driver, solo_driver, carrier_admin — into actionable findings the
Engineering Factory, Product Studio, Commercial Office, and Legal
Office can use.

## Triggers

- A pilot post-mortem.
- A new product feature in design.
- A persona-specific positioning question.
- A regulator enforcement action affecting the customer's
  workflow.

## Required Inputs

- The persona(s) to mine.
- The pain area (e.g. "endorsement-expiry surprise,"
  "shipping-paper field errors during inspection," "DVIR
  submission friction on mobile").

## Research Required

- Public driver / carrier forum discussions (friction signal
  only; not authoritative).
- Public DOT-PHMSA enforcement summaries.
- HazMat industry trade publications.
- HazMat Command's own pilot feedback (when present).
- Internal: 5-role audit (`AUDIT.md` once refreshed), smoke test
  log (`SMOKE_TEST.md`).

## Step-by-Step Method

1. Restate the pain area concretely tied to one of the 5 roles.
2. Gather 5–10 quote-level pain points with citations.
3. Cluster the pain points into 3–5 themes.
4. For each theme: list (a) what HazMat Command does today,
   (b) what's missing, (c) candidate product move.
5. Surface the top 3 themes with the largest gap between current
   capability and customer expectation.

## Deliverable Format

A Pain Synthesis memo under `docs/research/<YYYY-MM-DD>-pain-
<area>.md`. Sections: Persona, Pain Area, Quote-level Evidence,
Themes, Gaps, Recommended Moves.

## Quality Checklist

- [ ] Every quote cited (source + date)
- [ ] Themes are distinct, not overlapping
- [ ] Gaps are tied to specific HazMat Command surfaces
- [ ] No assertion presented as fact when it comes from a
  single forum thread

## Escalation Triggers

- A pain theme that implies a current compliance gap →
  immediately route to Compliance Engine Engineer + Compliance
  Evidence Agent.

## Related Agents

- Practitioner Friction Agent (Research Bureau, division 02)
- Field Feedback Analyst (Pilot Ops, division 08)

## Related Artifacts

- `docs/templates/research-dossier-template.md` (for deeper
  follow-on dossiers)
