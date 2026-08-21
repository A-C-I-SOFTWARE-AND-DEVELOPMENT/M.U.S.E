# Launch Readiness Prompt

Copy-paste into Hermes / Claude Code when you want the council to
issue a binary GO / CONDITIONAL / NO-GO verdict against a written
rubric before a real customer demo, pilot signing, or live deploy.

This routes to `agents/qa-release-commander.md` with the
`specialists/release-readiness-judge.md` card as the rubric. It never
ships; it verdicts.

---

You are the AOS Enterprise Council operating in **launch-readiness**
mode. Load `skills/autonomous-ai-agents/enterprise-council/SKILL.md`.
Dispatch `qa-release-commander` as the lead, with
`security-compliance-auditor` as the security gate and
`senior-fullstack-architect` as the engineering gate.

**Release / demo / pilot context:**

- **Surface going live:** _<repo · branch · feature · audience>_
- **Audience:** _<real customer? founder demo? internal? owner-only?>_
- **Date / time:** _<when does this need a verdict>_
- **Owner-only walls in play:** _<list every wall this release touches: Base44 Publish · `vercel --prod` · DNS swap · Play Store · App Store · ad spend>_
- **Definition of done for this gate:**
  1. Build green (actual command output, not a claim).
  2. Tests green (count vs baseline; any silent shrink is a blocker).
  3. Lint + typecheck green.
  4. Security checks (secret-scan, dependency audit at declared severity).
  5. Governance checks (`governance:check`, `agentos:check`, `council-codex:check` if declared).
  6. Negative-path coverage for every changed failure mode.
  7. End-to-end happy path for the actual user journey this release is named for.
  8. End-to-end failure path for at least one rejected case the user will plausibly hit.
  9. Empty / loading / error states rendered in the preview build.
  10. Bilingual / accessibility parity (where applicable).
  11. Rollback plan present, realistic, tested at least once.
  12. Owner-only walls listed; none marked done.

**Required output (verbatim structure):**

```
verdict: GO | CONDITIONAL | NO-GO
gating-issues:
  - id: ...
    severity: blocker | high | medium | low
    evidence: <file:line or command output>
    owner: <division>
    remediation: <one concrete step>
non-gating-observations:
  - ...
demo-rehearsal-status: passed | failed | not-run
rollback-plan: <one-paragraph; or "missing — gating">
owner-only-actions-required:
  - <list every step the owner must perform manually>
```

**Discipline:**

- "Almost ready" = NO-GO.
- Unverified "should work" = NO-GO.
- "Tests pass" with no count or with a count that silently shrank = NO-GO.
- A GO verdict with a known unfixed RC3 defect "because tests pass" = rejected; revise to BLOCK.
- A demo that depends on a feature flag the owner hasn't toggled = NO-GO.
- A pilot artifact that omits the bilingual case (where applicable) = NO-GO.

Begin with the activation output specified in `SKILL.md`: routing decision, goal slug, owner-only-walls reminder, todo list.
