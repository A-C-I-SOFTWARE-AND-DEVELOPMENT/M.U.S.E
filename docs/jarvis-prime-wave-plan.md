# JARVIS Prime Build Plan — Waves

This document is the wave-based build plan for JARVIS Prime. It exists
to keep the team (Claude Code, Codex, owner) from stepping on each
other while several parallel feature lanes are open.

Canonical repo: **`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`** (see
[`CANONICAL_REPO.md`](../CANONICAL_REPO.md)).

## Wave 0 — Foundation lock (this wave)

Branch: `feature/jarvis-foundation-lock`
(or the assigned `claude/jarvis-foundation-lock-*` branch for the
current Claude Code session).

Scope:

- Declare the canonical repo (`CANONICAL_REPO.md`).
- Document the wave plan (this file).
- Ship the standard `WorkPacket` dataclass at
  `hermes_cli/jarvis_prime/work_packet.py`, exported from
  `hermes_cli.jarvis_prime`.
- Add baseline tests for the WorkPacket.
- No new runtime behavior, no new CLI surface, no new dispatch
  logic.

Done definition: the foundation pieces above are merged into the
integration branch, tests pass, and the WorkPacket is importable.
**No claim of "done" without verification evidence.**

## Wave 1 — Parallel feature lanes

Each lane gets its own branch off `main` (or off the integration
branch, depending on coordination). Lanes that touch shared runtime
files must coordinate explicitly — see "Shared runtime files" below.

| Lane | Suggested branch | Touches |
|---|---|---|
| Semantic immune layer | `feature/jarvis-immune-layer` | `epistemics.py`, new module |
| Runtime enforcement | `feature/jarvis-runtime-enforcement` | `runtime.py`, `gates.py` |
| CLI expansion | `feature/jarvis-cli-expansion` | `__main__.py`, new subcommands |
| Memory / self-improvement persistence | `feature/jarvis-memory-persistence` | `memory.py`, `self_update.py` |
| Mobile / focused mode | `feature/jarvis-mobile-focused` | `modes.py`, `persona.py` |
| Test suite expansion | `feature/jarvis-test-suite` | `tests/` |

Lanes may proceed in parallel **only** if they touch disjoint files
or coordinate on shared edits ahead of time. When in doubt, ask the
owner — a 30-second coordination message beats a merge conflict.

## Wave 2 — Integration

Branch: `integration/jarvis-prime-runtime`

All Wave-1 feature branches merge into the integration branch first.
The integration branch is where conflicts are resolved, the test
suite is run end-to-end, and the verification gates are exercised
against a realistic WorkPacket.

## Wave 3 — Codex independent review

Codex reviews the integration branch on its own branch (e.g.
`review/codex-jarvis-runtime`). Findings are returned as PR review
comments or as bounded fix branches that target the integration
branch.

Claude Code does not edit the integration branch while Codex review
is in flight.

## Wave 4 — Owner-approved main merge

The owner reviews the integration branch and either:

- Requests changes (back to Wave 1 / 2 / 3 as appropriate), or
- Approves the merge with the exact phrase
  `Yes, with authorization.`, at which point the integration branch
  is fast-forwarded into `main`.

## Rules (apply across every wave)

1. **Do not edit `main` directly.** Always work on a feature branch.
2. **Each feature lane gets its own branch.** No "and a few other
   things" smuggled into a focused branch.
3. **Shared runtime files require extra caution.** A change to
   `runtime.py`, `__init__.py`, `gates.py`, `modes.py`, or
   `owner_auth.py` should be called out in the PR description with
   an explicit reason.
4. **Claude Code and Codex must not edit the same branch at the same
   time.** Sequence them.
5. **All feature branches merge into the integration branch first.**
   Never directly into `main`.
6. **Main merge requires owner approval** via the exact
   authorization phrase.
7. **No "done" claim without verification evidence.** Show the
   commands you ran, the output, and the verdict.

## Out of scope for Wave 0

The following are explicitly **not** in Wave 0 and must wait for
their assigned Wave-1 lane:

- Semantic immune layer logic.
- Runtime enforcement changes (gate execution policy, hard blocks).
- CLI expansion (new subcommands beyond the existing five).
- Proposal persistence (writing the `ProposalBook` to disk).
- Mobile live mode (live voice loop, push-to-talk).
- Real Claude / Codex dispatch (today it is data, not action).
- GitHub publishing automation.
- Deployment automation.

If a Wave-0 PR drifts into any of these, the PR is out of scope and
should be split before merge.

## Related docs

- [`CANONICAL_REPO.md`](../CANONICAL_REPO.md)
- [`docs/jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
- [`docs/jarvis-verification-gates.md`](jarvis-verification-gates.md)
- [`skills/jarvis-prime/SKILL.md`](../skills/jarvis-prime/SKILL.md)
