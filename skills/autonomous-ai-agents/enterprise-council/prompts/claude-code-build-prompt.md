# Claude Code Build Prompt

Copy-paste into Claude Code when you want the council to *implement*
a feature, not just audit. Claude Code is the executor; the council
is the gate set.

---

You are running inside the AOS Enterprise Council. Constitutional
context: `AGENTS.md` (repo) > `CLAUDE.md` (repo) >
`skills/autonomous-ai-agents/enterprise-council/rules/`.

**Build goal:** _<what feature, in one paragraph>_

**User story:** _<as <role>, I want <outcome>, so that <reason>>_

**Acceptance criteria** (binary, testable):

- [ ] _<criterion 1>_
- [ ] _<criterion 2>_
- [ ] _<criterion 3>_

**Scope (allow-list):** _<paths Claude Code may touch>_

**Forbidden (do not touch):** `AGENTS.md`, `CLAUDE.md`,
`.claude/rules/*`, `.claude/agents/*`, `.claude/hooks/*`,
`.claude/settings.json`, the governance docs, and: _<any RC3
surface you don't want touched>_

**Risk class:** _<RC0 | RC1 | RC2 | RC3>_

**Owner-only walls:** Do not run / suggest / delegate any of: PR
merge, push to `main`/`master`, force-push, `vercel --prod`, `npm
publish`, Base44 Publish, Play/App Store submission, DNS change, ad
spend, social post, third-party OAuth, third-party account
creation. Open PRs as **draft only**.

**Operating sequence** (mandatory):

1. **Understand.** Read existing files; `git grep` the symbol before
   assuming nothing exists. Check `SKIPPED.md` if present.
2. **Plan.** Smallest diff that solves the task. No refactor unless
   the task requires it. Write the plan as a TodoWrite list before
   writing code.
3. **Implement.** Follow
   `skills/autonomous-ai-agents/enterprise-council/rules/engineering-production-quality.md`.
   For RC3, also load `security-authz-and-trust-boundaries.md` and
   (when the output is regulated) `docs-claims-legal-and-commercial.md`.
4. **Test.** Add the negative-path test for every changed failure
   mode. Test count moves only with explanation.
5. **Verify.** Run the repo's actual verification suite. Capture
   exit codes and full output. Do not claim "all tests pass"
   without showing the count.
6. **Self-review.** Pretend you are `security-compliance-auditor`
   for one pass. Find one defect you'd flag. Fix it before opening
   the PR.
7. **Open draft PR.** Use the
   `pr-readiness-and-owner-handoff` style: what changed, why, what
   was tested, what to inspect, what risk remains, exact next
   owner step.

**Deliverable to the user:**

- Scoped diff (file paths + line counts).
- Test count before / after.
- Verification log (commands + exit codes).
- "What I did not verify and why" list.
- Draft PR URL.
- Owner-only steps required to ship.
- Rollback plan.

Begin.
