---
name: codex-return-envelope-verify
description: Use after a Codex Task Packet execution returns. Parses the return envelope, asserts schema validity, asserts allow-list adherence, asserts forbidden-list adherence, re-runs the claimed test commands locally, cross-checks against the owner-only-wall RULES table, and rejects any envelope claiming an action the PreToolUse hook would block. Verifier must be a different session than the packet dispatcher.
---

# codex-return-envelope-verify

## When to use

Immediately after a Codex packet executes and returns its envelope.
Before any code review begins. Codex envelopes are not trusted —
they must be verified before `principal-code-reviewer` is invoked.

## Inputs

- The packet at `07-codex-task-package.md` (allow-list,
  forbidden-list, owner-only walls, required tests, expected
  envelope shape).
- The return envelope (either pasted into the run folder or
  attached to the dispatch result).
- Repo state at the branch the envelope claims to have written to.

## Method

1. **Schema check.** Confirm every required field in the
   `Expected return envelope` section of the packet is present:
   `envelope_version`, `packet_id`, `status`, `diff.files_touched`,
   `tests_added_or_changed`, `results.{lint,typecheck,test,build,council_codex_check,agentos_check,governance_check}`,
   `self_assessment`, `escalation`.
2. **Packet ID match.** Envelope's `packet_id` matches the
   packet's filename slug. Mismatch rejects the envelope.
3. **Allow-list adherence.** For every entry in
   `diff.files_touched`, confirm the path matches at least one
   allow-list glob in the packet. Any path that does not match is
   a rejection.
4. **Forbidden-list adherence.** For every entry in
   `diff.files_touched`, confirm the path does NOT match any
   forbidden-list glob. Constitutional surfaces are always
   forbidden. Any match is a rejection.
5. **Owner-only-wall cross-check.** Cross-reference any commands
   the envelope reports running against the RULES table in
   `.claude/hooks/block-owner-only-actions.mjs`. Any owner-only
   command claimed (even with a "skipped" status) is a rejection
   and an escalation.
6. **Test re-run.** Re-execute the test commands the envelope
   claims passed (`npm run lint`, `npm run typecheck`, `npm test`,
   `npm run build`, `npm run governance:check`,
   `npm run agentos:check`, `npm run council-codex:check`). The
   re-run results must match the envelope's claim. Any mismatch
   is a rejection.
7. **Negative-test presence.** For each named test in the
   packet's "Required tests" → "New negative-path tests" list,
   confirm the test file exists and the test name asserts what
   the packet specified.
8. **No new stub without SKIPPED entry.** Grep the diff for new
   `TODO(stub:<name>)` markers; confirm each has a matching
   `SKIPPED.md` entry. New stubs without an entry fail
   `tests/inventory/skipped-coverage.test.js`.
9. **Verdict.** Either:
   - `pass` — hand the diff to `principal-code-reviewer`. For RC3
     additionally to `assurance-security-compliance-office`.
   - `reject-redispatch` — packet shape was sound but envelope
     violated the contract; re-dispatch with a tighter packet.
   - `reject-escalate` — envelope claims an owner-only action or
     touches a constitutional surface; escalate to the owner.

## Output

A verdict block appended to `10-test-results.md` in the run folder,
plus (on pass) a hand-off to `principal-code-reviewer`.

```text
ENVELOPE: <run-folder>/07-codex-task-package.md
PACKET_ID: <slug>
SCHEMA: ok | missing-fields: <list>
ALLOW-LIST: ok | violations: <paths>
FORBIDDEN-LIST: ok | violations: <paths>
OWNER-ONLY WALL ATTEMPTS: none | <command>
TEST RE-RUN: matches | diverges (<which command>)
NEGATIVE TESTS: present | missing (<which>)
NEW STUBS: ok | unpaired (<TODO names>)
VERDICT: pass | reject-redispatch | reject-escalate
NEXT STEP: <one sentence>
```

## Anti-patterns

- Accepting the envelope's claim without re-running tests.
- Skipping the forbidden-list check on the grounds that "the
  packet was fine."
- Approving a verdict when the same session dispatched the
  packet (no maker-checker).
- Re-running a different test command than the one the envelope
  claims (cheating the comparison).
- Treating an owner-only-wall attempt as a warning instead of a
  rejection.
- A "pass" verdict on RC3 without handing to
  `assurance-security-compliance-office`.
