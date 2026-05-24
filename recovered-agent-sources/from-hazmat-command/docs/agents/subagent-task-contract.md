# Subagent Task Contract

**Status:** Installed 2026-05-17

Any subagent dispatched by an AEO agent must be briefed with the
fields below. The contract exists because subagents do not inherit
the parent session's full context — they need everything in writing
to operate safely under the authority and tool-trust ceilings
defined in `docs/governance/02-agent-authority-matrix.md` and
`docs/governance/07-tool-trust-zones-and-agent-permissions.md`.

## Required fields

| Field | Description | Example |
|---|---|---|
| **Task ID** | Unique slug for the subagent run, used in artifacts and retrospectives | `2026-05-17-aeo-install-explore-1` |
| **Parent Agent** | Division + role of the agent dispatching the subagent | `Executive Command & Orchestration / Chief Orchestrator` |
| **Objective** | One-sentence definition of done | "Read the 9 governance files and produce a structured summary of source-of-truth law" |
| **Context** | What the subagent needs to know that is not in its built-in tools — repo paths, current branch, recent commits, prior research, what was tried | "Branch `claude/install-autonomous-org-lBBUy`. Coverage CI gate at `tests/inventory/skipped-coverage.test.js` must not be broken. Round personas R1-D…R5-V exist." |
| **In Scope** | Specific files / commands / artifacts the subagent may touch | "Read AGENTS.md, PUBLISH.md, SKIPPED.md, HANDOFF.md, AUDIT.md, PLAY_STORE.md" |
| **Out of Scope** | Specific things the subagent must NOT do | "Do not modify any file. Do not run npm install. Do not call vendor APIs." |
| **Required Sources** | Primary sources the subagent must cite if producing research | "49 CFR Subchapter C; NIST SSDF; OWASP ASVS L1/L2; vendor docs by URL" |
| **Approved Tools** | Tool list with trust zone | "Read (T1), Glob (T1), Grep (T1), Bash for read-only `git`/`ls`/`wc` (T4 read-only)" |
| **Prohibited Tools** | Tool list explicitly disallowed | "Edit, Write, NotebookEdit, mcp__github__merge_pull_request, mcp__github__enable_pr_auto_merge, gh pr merge, npm install, curl to external URLs" |
| **Deliverable Format** | What the subagent returns | "Markdown report ≤ 800 words with headers and bullet lists; cite file paths with line numbers" |
| **Quality Bar** | What "good" looks like | "Every claim cites a file path or a primary source; contradictions surfaced; recommendations under 100 words at the end" |
| **Stop Conditions** | When the subagent halts early | "Stop if Read returns >2000 lines for any single file; stop if any file path is missing; stop and ask via `AskUserQuestion` if scope is ambiguous" |
| **Handoff Target** | Where the subagent's output is consumed | "Returned to Chief Orchestrator; integrated into the plan file at `/root/.claude/plans/<plan>.md`" |
| **Confidence Rating** | The subagent reports High / Medium / Low confidence on its conclusion + one sentence why | "Medium — sources cite Stage 5 work in forward-tense; current state may have moved" |
| **Known Unknowns** | What the subagent could not determine and why | "Could not confirm DNS state on hazmatcommandcore.org without owner-level access" |

## Starter tool mapping (HazMat Command-specific)

The trust zones below are the **default** for each tool in this
repo. A subagent may not exceed its parent's ceiling regardless of
this default.

| Tool | Default zone | Typical role with access | Notes |
|---|---|---|---|
| `Read`, `Glob`, `Grep` | T1 | All divisions | Internal repo read |
| `Bash`: `git status`, `git diff`, `git log`, `git show`, `git branch --show-current`, `git grep`, `ls`, `find`, `wc`, `cat` (for short files only — prefer `Read`) | T1 / T4 read | All divisions | Read-only; safe |
| `Bash`: `npm run lint`, `typecheck`, `test`, `build`, `i18n:check`, `governance:check`, `test:e2e` | T4 | Engineering Factory, Assurance Office, Executive Orchestrator | Reproducible build/test runs |
| `Bash`: `npm install`, `npm ci`, `npm install --save*` | T4 | Engineering Factory (under RC3 with maker-checker for dependency changes) | Adds/changes runtime surface; goes through `governance/14` |
| `Edit`, `Write`, `NotebookEdit` on `docs/`, `marketing/` drafts, `.claude/` | T2 | Research Bureau (drafts only), Product Studio, Commercial Office, Legal Office, Pilot Ops, Knowledge Ops | Internal draft writes |
| `Edit`, `Write` on `src/`, `api/`, `base44/`, `scripts/`, `tests/`, `supabase/migrations/`, `vercel.json`, `package.json`, `.github/workflows/`, `eslint.config.js`, `vitest.config.js`, `playwright.config.js`, `tailwind.config.js`, `jsconfig.json`, `capacitor.config.json` | T3 | Engineering Factory, Assurance Office, Executive Orchestrator (for governance hooks) | Subject to RC3 maker-checker for RC3 surfaces in `governance/03` |
| `Bash`: `git add`, `git commit`, `git push -u origin claude/<permitted-branch>` | T4 | Engineering Factory, Assurance Office, Executive Orchestrator | Only the session's permitted branch |
| `Bash`: `git push origin main`, `git push --force*`, `git reset --hard`, `git rebase -i`, `gh pr merge`, `npm publish`, `vercel --prod`, `vercel link`, any cap distribute / Play Store CLI | T6 (Prohibited) | Owner only | Never agent |
| `mcp__github__create_pull_request` (draft only), `mcp__github__update_pull_request`, `mcp__github__list_pull_requests`, `mcp__github__pull_request_read`, `mcp__github__add_issue_comment`, `mcp__github__add_reply_to_pull_request_comment`, `mcp__github__pull_request_review_write` (comment-only) | T4 | Engineering Factory, Assurance Office, Executive Orchestrator | Always draft when creating; never merge |
| `mcp__github__merge_pull_request`, `mcp__github__enable_pr_auto_merge`, `mcp__github__disable_pr_auto_merge`, `mcp__github__create_repository`, `mcp__github__delete_file` (on `main`), `mcp__github__push_files` (to `main`) | T6 (Prohibited) | Owner only | Hard owner-only walls |
| `WebFetch`, `WebSearch` | T0 (read) → T1 if cite-checked | Research Bureau (with cite check), Knowledge Operations | T0 because content is external; cite-checking against primary sources elevates to T1 |
| Vitest (`npm test`), Playwright (`npm run test:e2e`) | T4 | Engineering Factory, Assurance Office | Includes negative / cross-tenant / fuzz suites |
| semgrep (CI), gitleaks (CI) | T4 (read) | Assurance Office | CI-only this sprint; agents read results |
| Sentry SDK (`@sentry/browser`) | T1 (read), T5 if writing to a live project | Engineering Factory | T5 = not granted this sprint; SDK is in no-op stub mode until `VITE_SENTRY_DSN` lands |
| WorkOS SDK / Square SDK / Supabase SDK / Tesseract OCR | T1 (read code), T5 if hitting a real account | Engineering Factory | T5 = not granted this sprint; all integrations exercised against stubs / fixtures per `SKIPPED.md` |
| Base44 SDK (`@base44/sdk`) | T1 (read), T6 for Publish | Engineering Factory | Base44 Builder Publish is owner-only (Gate 1 of PUBLISH.md) |
| Capacitor CLI (`npx cap`) | T4 (sync, copy), T6 (build signed AAB / open Play Console) | Engineering Factory (sync/copy) / Owner only (signed builds) | See `PLAY_STORE.md` |
| Vercel CLI | T1 (preview URL lookup) / T6 (`vercel --prod`, env management) | Owner only for T6 | DNS / env / prod promotion are owner-only |
| IONOS / Cloudflare DNS panels | T6 | Owner only | See AGENTS.md "Vercel + DNS gotcha" |

Any tool not in this list defaults to **T0** until the parent agent
or the governance docs grant a higher zone explicitly.

## Worked example — research subagent dispatch

```
Task ID: 2026-05-17-aeo-install-explore-1
Parent Agent: Executive Command & Orchestration / Chief Orchestrator
Objective: Read and structurally summarize the 9 root governance
  files so the AEO install plan is grounded in current repo law.
Context: Branch claude/install-autonomous-org-lBBUy. We are about
  to install AGENTS.md additions, PUBLISH.md G0-G4 extension, and a
  SKIPPED.md schema retrofit. We must not destabilize the existing
  CI gate at tests/inventory/skipped-coverage.test.js.
In Scope:
  - Read AGENTS.md, PUBLISH.md, SKIPPED.md, HANDOFF.md, AUDIT.md,
    PLAY_STORE.md, README.md, CODEOWNERS, SMOKE_TEST.md, CLOUD_SYNC.md
Out of Scope:
  - No file modifications
  - No vendor API calls
  - No npm install
Required Sources: only the in-repo files listed
Approved Tools: Read (T1), Glob (T1), Grep (T1), Bash for read-only
  git/ls/wc (T4 read-only)
Prohibited Tools: Edit, Write, NotebookEdit, all mcp__github__*
  write tools, gh pr merge, npm install, curl, any web fetch
Deliverable Format: Markdown report with these sections —
  per-file summary, unified source-of-truth hierarchy, rules that
  cannot be violated, gaps / missing concepts, stale-doc risks
Quality Bar: Every claim cites a file + line if specific; no
  invented capabilities; flag every doc-freshness risk you see
Stop Conditions: Halt if any required file is missing; halt if a
  Read returns content suggesting credentials or PII
Handoff Target: Chief Orchestrator; consumed into the plan at
  /root/.claude/plans/<plan>.md
Confidence Rating: High / Medium / Low + one sentence why
Known Unknowns: List anything you could not determine and why
```

This was the actual contract used to dispatch the Phase 1 governance
deep-read subagent during this install. The structure made the
subagent's output directly slottable into the plan.

## Anti-patterns

- Dispatching a subagent without an explicit **Out of Scope** list.
  The agent will assume its full toolbox is available and may
  exceed the parent's ceiling.
- Omitting **Stop Conditions** — long-running subagents drift.
- Letting a subagent write its own Quality Bar — the parent owns
  what "good" means for this task.
- Using a subagent for a job that can be done with a single targeted
  Read / Grep. The contract exists to keep subagents bounded; if the
  job has no internal branching, do it inline.
- Forgetting to log the subagent's deliverable into the artifact
  registry (`docs/governance/08`). Subagent output is artifact data
  too.
