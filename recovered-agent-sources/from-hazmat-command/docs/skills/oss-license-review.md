# Skill — oss-license-review

## Purpose

Review the OSS license posture of the repository's 873+
dependencies. Identify copyleft surfaces, license compatibility
issues, and required attributions.

## Triggers

- New dependency added.
- Major-version dependency upgrade.
- Quarterly review.
- Customer / RFP asks for an OSS inventory.

## Required Inputs

- `package.json` + `package-lock.json`.
- Output of `npm ls --all` (when fast enough; otherwise
  `npm ls --depth=1`).
- License field of each top-level dependency.

## Research Required

- Compatibility matrix between AGPL / GPL / LGPL / MPL / EPL /
  Apache 2.0 / MIT / ISC / BSD / Unlicense.
- The repo's proprietary status (HazMat Command source is
  proprietary; the 22-placard SVG set is Hazmat Command
  copyright per the v1.0.0 release notes; underlying 49 CFR
  regulation is public domain).

## Step-by-Step Method

1. Run `npm ls --all --json` (or `--depth=2` for speed) and
   parse licenses.
2. Flag every dependency whose license is:
   - GPL/AGPL (incompatible with proprietary distribution
     except via specific carve-outs)
   - Custom / non-OSI-approved
   - Missing or "UNKNOWN"
3. For permissive licenses (MIT, ISC, BSD, Apache 2.0),
   compile the attribution / NOTICE file requirement.
4. Cross-check against the existing `vercel.json` /
   distribution model — Vercel-served code does not "convey"
   under GPL terms in the same way as binary distribution; but
   AGPL has stronger reach. Flag any AGPL transitive dep.
5. Recommend remediation: replace, vendor under a permissive
   alternative, or carve out for the dependency.

## Deliverable Format

OSS License Review Memo + an updated attribution / NOTICE file
draft when permissive deps are present.

## Quality Checklist

- [ ] Every top-level dep license recorded
- [ ] AGPL / GPL / unknown flagged
- [ ] Attribution file drafted for permissive deps
- [ ] No copyleft contamination of proprietary code

## Escalation Triggers

- AGPL transitive dep on a code path bundled into the
  customer-facing front end → halt; Engineering Factory
  + Legal.

## Related Agents

- IP & Open Source Agent (Legal Office)
- Supply Chain Security Agent (Assurance Office)
- Release Engineering Agent (Engineering Factory)

## Related Artifacts

- `package.json`
- `governance/14-supply-chain-and-agent-security.md`
