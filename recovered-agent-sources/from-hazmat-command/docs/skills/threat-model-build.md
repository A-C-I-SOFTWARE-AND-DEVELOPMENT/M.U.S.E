# Skill — threat-model-build

## Purpose

Extend `docs/security/threat-model.md` with a STRIDE analysis of
a new feature or attack surface, integrated with the existing
R3-N/R3-O model.

## Triggers

- A new RC3 attack surface (new API route, new auth surface, new
  data path, new vendor integration).
- A change to an existing RC3 surface that materially shifts the
  threat picture.

## Required Inputs

- The feature / surface under analysis.
- Existing `docs/security/threat-model.md`.
- Existing `docs/iso27001/risk-register.md` (cross-reference).

## Research Required

- STRIDE methodology (Spoofing, Tampering, Repudiation,
  Information disclosure, Denial of service, Elevation of
  privilege).
- OWASP ASVS L1/L2 chapter relevant to the surface (V2 Auth,
  V4 Access Control, V13 API, etc.).
- NIST 800-53 family relevant to the surface (AC, AU, SC, SI).
- The repo's existing mitigations: single authz middleware,
  hash-chained audit, RLS migrations (authored), CSP, rate
  limiting, request-id propagation, PII scrubbing.

## Step-by-Step Method

1. Identify the trust boundaries the feature creates or moves.
2. For each STRIDE category, enumerate threats specific to this
   surface (not generic).
3. For each threat, identify:
   - existing mitigation (cite code + test)
   - residual risk
   - recommended additional mitigation (if any)
4. Cross-reference `docs/iso27001/risk-register.md`; add or
   update a risk row if material.
5. Append to `docs/security/threat-model.md` as a new section.
6. If the new surface introduces a new external dependency,
   update `governance/14-supply-chain-and-agent-security.md`.

## Deliverable Format

A new section in `docs/security/threat-model.md` with the STRIDE
table per surface.

## Quality Checklist

- [ ] All 6 STRIDE categories considered
- [ ] Threats are concrete to this surface
- [ ] Mitigations cite code + test
- [ ] Residual risk explicit
- [ ] ISO 27001 risk register cross-reference

## Escalation Triggers

- A high-residual-risk threat with no mitigation path → halt
  feature ship; Risk Controller.

## Related Agents

- Threat Modeling Agent (Assurance Office)
- Principal Security Architect (Assurance Office)

## Related Artifacts

- `docs/templates/threat-model-template.md`
- `docs/security/threat-model.md`
- `docs/iso27001/risk-register.md`
