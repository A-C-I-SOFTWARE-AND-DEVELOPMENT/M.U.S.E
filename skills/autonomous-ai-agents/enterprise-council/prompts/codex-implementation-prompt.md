# Codex Implementation Prompt (Codex Task Packet form)

Copy-paste into Codex when an execution blueprint hands it a
bounded task. This is the **Task Packet** contract — Codex operates
at L3 max, T3+T4 only, never on constitutional surfaces, never on
owner-only walls.

Fill in every section. Empty sections invalidate the packet and the
`claude-codex-orchestrator` will reject the envelope on return.

---

## Codex Task Packet — v1

### 1. Packet ID
`codex-<goal-slug>-<ISO-date>-<seq>` e.g. `codex-rls-tenant-test-2026-05-24-01`

### 2. Originating blueprint
`docs/aos/runs/<run-slug>/06-execution-blueprint.md` § _<section>_

### 3. Risk class
RC0 | RC1 | RC2 | **RC3** (RC3 packets require Assurance review on return)

### 4. Goal (one paragraph)
_<plain-English description of what this packet asks Codex to do>_

### 5. Acceptance criteria (binary, testable)
- [ ] _<criterion 1>_
- [ ] _<criterion 2>_

### 6. Allow-list (paths Codex MAY read/write)
```
src/lib/example.js
src/lib/example.test.js
tests/integration/example.test.js
```
Glob patterns broader than the change require a one-sentence
justification.

### 7. Forbidden-list (paths Codex MUST NOT touch)
```
AGENTS.md
CLAUDE.md
.claude/**
docs/governance/**
docs/agents/**
.github/workflows/**       # unless the blueprint explicitly chartered CI changes
package.json               # unless dependency change is the packet's purpose
package-lock.json          # unless tied to dep change above
```
Plus the repo's listed RC3 surfaces (authz, audit ledger, OCR
provenance, payments, RLS, regulator-facing builders) unless this
packet was explicitly chartered for one.

### 8. Test commands (exact)
```bash
npm run lint
npm run typecheck
npm test -- --runInBand
npm run build
# Repo-specific gates if declared:
npm run governance:check
npm run agentos:check
```

### 9. Branch
Feature branch only. Pattern: `codex/<packet-id>`. Never `main` /
`master`. Open PR as **draft**.

### 10. Owner-only walls (Codex MUST NOT call)
- `gh pr merge` / merge_pull_request / enable_pr_auto_merge
- `git push --force` / push to `main` or `master`
- `vercel --prod`
- `npm publish`
- Base44 Publish (any path that triggers it)
- Play/App Store submission
- DNS / CNAME changes
- Any OAuth flow / account creation / ad spend / social post

### 11. Rollback plan
_<one paragraph: how the change is undone if it misbehaves>_

### 12. Return envelope (Codex must produce this on completion)
```json
{
  "packet_id": "...",
  "branch": "codex/...",
  "draft_pr_url": "...",
  "files_changed": ["path:line-count", "..."],
  "test_commands_run": [
    {"cmd": "...", "exit_code": 0, "stdout_tail": "...", "stderr_tail": "..."}
  ],
  "acceptance_criteria": [
    {"criterion": "...", "met": true, "evidence": "file:line or command output"}
  ],
  "owner_actions_required": ["..."],
  "rollback": "...",
  "deviations_from_packet": ["..."]  // empty if none
}
```

### 13. Acknowledgement (Codex signs before starting)
> I have read this packet. I will not touch any path in §7. I will
> not call any action in §10. I will run the exact commands in §8.
> I will produce the envelope in §12. If I cannot meet §5, I will
> return a partial envelope explaining why, not invent success.
