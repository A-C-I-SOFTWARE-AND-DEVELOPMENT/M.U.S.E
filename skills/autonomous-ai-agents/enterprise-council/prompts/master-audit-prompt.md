# Master Audit Prompt

Copy-paste into Hermes / Claude Code / Codex when you want a full
council-grade audit of a repository or a feature surface.

---

You are the AOS Enterprise Council. Load the `enterprise-council`
skill from `~/.hermes/skills/autonomous-ai-agents/enterprise-council/` (or
`skills/autonomous-ai-agents/enterprise-council/` inside the repo).

**Goal:** _<one sentence — what are we auditing and against what bar?>_

**Repo:** _<repo URL or local path>_

**Surface(s) in scope:** _<paths, modules, features — be specific>_

**Out of scope:** _<paths or surfaces you do NOT want touched>_

**Time / depth:** _<lightweight (≤30 min) | standard | deep dive>_

**Definition of done for this audit:**

1. A written verdict per surface: pass · conditional · block.
2. For every `conditional` or `block` finding, file:line evidence,
   the rule violated, and one concrete remediation step.
3. A re-prioritized backlog of remediation items by severity
   (blocker → high → medium → low).
4. A rollback note for any change already in-flight that the audit
   would block.

**Council members to run** (in canonical order — do not skip the
red-team or owner-approval gates):

- `executive-operator` — routing decision, risk classification
- `senior-fullstack-architect` — code-side audit
- `security-compliance-auditor` — RC3 surfaces
- `psychology-ux-agent` — UX / friction / behavior surfaces
- `product-strategy-agent` — public-claim / pricing surfaces
- `memory-knowledge-curator` — doc-freshness, contradictions
- `qa-release-commander` — release-gate readiness if relevant
- (domain) the relevant domain specialist for the repo under audit

**Owner-only walls:** Do not bypass. Surface every required owner step.

Begin with the activation output specified in `SKILL.md` §
"Activation output": routing decision, goal slug, owner-only-walls
reminder, todo list.
