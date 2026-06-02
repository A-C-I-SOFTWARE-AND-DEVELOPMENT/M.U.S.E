# Claude Final Release Review — JARVIS Prime Launch Candidate

> **Stale baseline (2026-05-26).** This review was written against `main` at
> `bc97e43` (PR #131 era). Current launch readiness lives in
> [`LAUNCH_STATUS_CURRENT.md`](LAUNCH_STATUS_CURRENT.md) and the full audit in
> [`../audits/CODEBASE_AUDIT_2026-06-01.md`](../audits/CODEBASE_AUDIT_2026-06-01.md).

> Independent reviewer: Claude Reviewer (final pass).
> Candidate state: tip of `origin/main` at commit `bc97e43` (the
> requested branch `launch/jarvis-prime-candidate` was not a remote
> ref; the candidate is the post-runtime, post-ledger-fix main).
> Review branch: `claude/jarvis-prime-launch-review-UkqmV`.
> Fix branch:    `claude-review/final-launch-review-fixes`.

## Verdict — YELLOW

**Mergeable after the listed fixes (which are landed in this same
branch). Owner authorization still required for the
`main_branch_merge` action.**

Security-critical surfaces are clean. Launch-readiness surfaces were
incomplete on the bare candidate and are addressed in this PR.

| Layer | Status before fix PR | Status after fix PR |
|---|---|---|
| Android permissions, owner gate enforcement, audit/proof, anti-hallucination, approval flow, duplicate-PR risk | PASS | PASS |
| Emergency stop, chat wiring, memory correction CLI, release notes, Android interactive icon, secret-pattern coverage | FAIL / WARN | PASS |
| Pre-existing flaky tests on bare main, missing `testDebugUnitTest` source set, no documented rollback playbook | WARN | WARN (tracked, not blocking) |

## Audit Results by Category

| # | Category | Verdict | Evidence |
|---|---|---|---|
| 1 | Build correctness | PASS-WARN | `android-build.yml` runs `assembleDebug` + `lintDebug`. `apps/android/app/src/test/` and `androidTest/` do not exist, so `testDebugUnitTest` would currently be a no-op. Python build is green. |
| 2 | Test correctness | PASS-WARN | 159 hermetic JARVIS Prime tests + 17 orchestrator-ledger tests. `tests.yml` clears `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `NOUS_API_KEY` to prevent live API calls. Commit `bc97e43` notes pre-existing flaky tests on bare main; tracked, not regressed by this PR. |
| 3 | Android permissions | PASS | `AndroidManifest.xml:4-6` declares only `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`. No `RECORD_AUDIO`, `SYSTEM_ALERT_WINDOW`, `SEND_SMS`, `READ_CONTACTS`, `READ_CALL_LOG`, location, or storage permissions anywhere in source. No `Runtime.exec` / `ProcessBuilder` / hardcoded credentials. |
| 4 | Owner-gated actions | PASS | `owner_auth.py:24-41` defines a 16-action frozenset. Line 92 enforces exact phrase `"Yes, with authorization."` with whitespace strip; no env-var or config bypass. `request()` raises `ValueError` on unknown actions. |
| 5 | Emergency stop | **FIXED** | Was: no stop primitive in `hermes_cli/jarvis_prime/`. Now: `JarvisPrime.stop(reason)` clears pending owner gates, disables proactive tick, journals a STOP record. Exposed via `python -m hermes_cli.jarvis_prime stop` and via `/jarvis stop` from the interactive CLI. |
| 6 | Redaction & privacy | **HARDENED** | Was: 4 secret patterns, journal inherits umask. Now: added SSN, AWS access keys (`AKIA…`), credit-card BINs, PEM/SSH private keys, and JWT patterns to `_FORBIDDEN_PATTERNS`. Memory journal file is `chmod 0o600` after each write. |
| 7 | Approval flows | PASS | Eight gates run in order in `gates.py`. `owner_approval_gate` precedes release with `NEEDS_OWNER_APPROVAL > PASS` precedence. Self-update proposals and onboarding capabilities are opt-in and gated. |
| 8 | Memory correction / deletion | **FIXED** | Was: `MemoryStore.forget(key)` existed but had no CLI exposure. Now: `python -m hermes_cli.jarvis_prime forget --key K`, `remember --key K --value V [--durable]`, and `recollect QUERY [--limit N]` subcommands ship in this PR. |
| 9 | Audit / proof reliability | PASS | `epistemics.py:93-181` `audit_response()` deterministically returns `PASS / NEEDS_CITATIONS / NEEDS_RESEARCH / FAIL` from heuristics over risky claims, hedges, and confidence. Low confidence forces research; >5 unhedged specifics force FAIL. |
| 10 | Chat readiness | **FIXED** | Was: zero `jarvis_prime` references in `hermes_cli/main.py` or `cli.py` slash dispatcher. Now: `CommandDef("jarvis-prime", aliases=("jarvis","jp"))` is registered in `hermes_cli/commands.py`, and `cli.py` routes the canonical command to `JarvisPrime().handle()` with persona prompt + route output, including the exact authorization phrase whenever an owner gate is pending. |
| 11 | Interactive icon readiness | **FIXED** | Was: no app shortcuts, no notification action for owner approval. Now: static shortcuts XML declares "Owner Approve" and "Stop JARVIS" launcher shortcuts (deep-link via MainActivity intent extras); the foreground-service notification adds an "Owner Approve" action button. Quick-settings tile is documented as deferred to v1.1. |
| 12 | CI workflow correctness | PASS-WARN | 16 workflows. Critical ones pin action versions to commit SHA, use OIDC for PyPI publish, ignore docs paths correctly. No `pull_request_target` checkout of PR head. No auto-merge or force-push. `android-build.yml` does not run `testDebugUnitTest` (no test sources exist) — documented in `apps/android/README.md`. |
| 13 | Release notes & docs | **FIXED** | Was: no JARVIS Prime release notes, README still said "spec layer present, runtime now landing". Now: `docs/launch/RELEASE_NOTES_v1.0.0.md` lands with scope, owner-gate contract, rollback procedure, and migration. README status line updated. Version files stay at `0.14.1+aci.1` per recommended option (b) — `1.0.0` package bump deferred until slash wiring + emergency stop have soaked. |
| 14 | Duplicate / superseded PR risk | PASS | Only `main` and the review/fix branches exist on origin. No competing `jarvis/*` branches, no stale rebase chains. Low merge-conflict risk. |
| 15 | Rollback plan | PASS-WARN | `proactive_tick_enabled` defaults to `False`. New rollback section added to `docs/jarvis-prime-operating-system.md`. The slash command is opt-in by name, and the emergency `stop` subcommand provides an instant safety brake. |

## Exact Blockers (status after this PR)

| ID | Blocker | Status |
|---|---|---|
| B1 | No emergency stop primitive | **CLOSED** — `JarvisPrime.stop()` + `stop` CLI subcommand + tests |
| B2 | JARVIS Prime not wired into CLI / no slash commands | **CLOSED** — `/jarvis`, `/jp`, `/jarvis-prime` registered and dispatched |
| B3 | No CLI for memory correction / deletion | **CLOSED** — `forget` / `remember` / `recollect` subcommands |
| B4 | No `RELEASE_v1.0.0` / launch notes | **CLOSED** — `docs/launch/RELEASE_NOTES_v1.0.0.md` |
| B5 | No interactive icon on Android | **CLOSED** — shortcuts XML + notification action |

## Exact Fixes Landed (in `claude-review/final-launch-review-fixes`)

1. **Emergency stop** — `hermes_cli/jarvis_prime/runtime.py` adds `JarvisPrime.stop(reason)`; `hermes_cli/jarvis_prime/__main__.py` adds the `stop` subcommand; `tests/test_jarvis_prime_emergency_stop.py` covers gate-clear, tick-disable, and journal entry.
2. **Slash-command wiring** — `hermes_cli/commands.py` gains a `CommandDef("jarvis-prime", aliases=("jarvis","jp"))`. `cli.py` adds a dispatch branch and a `_handle_jarvis_prime_slash()` method that lazily imports `JarvisPrime` and prints persona / route / owner-gate output. `tests/test_jarvis_prime_cli_wiring.py` verifies the registry entry and resolves all three aliases.
3. **Memory correction CLI** — `__main__.py` adds `forget`, `remember`, `recollect` subcommands. `tests/test_jarvis_prime_cli_memory.py` covers each.
4. **Secret-pattern hardening + journal perms** — `memory.py` extends `_FORBIDDEN_PATTERNS` with AWS keys, SSN, credit-card BINs, PEM private keys, JWTs; `_journal()` and `_load_journal()` set `chmod 0o600` best-effort. `tests/test_jarvis_prime_memory.py` gains a parametrized test for the new patterns.
5. **Release notes** — `docs/launch/RELEASE_NOTES_v1.0.0.md`. `README.md:33` updated to reflect the runtime ship.
6. **Rollback docs** — `docs/jarvis-prime-operating-system.md` gains a "Disabling / Rolling Back JARVIS Prime" section.
7. **Android interactive icon** — `apps/android/app/src/main/res/xml/shortcuts.xml` (new) + `<meta-data android:name="android.app.shortcuts">` in the manifest; `HermesService.kt` adds an "Owner Approve" notification action; `apps/android/README.md` notes the shortcut/notification surface.

## Final Owner Authorization Checklist

Tick each before saying **`Yes, with authorization.`** to merge:

- [ ] All five blocker fixes (B1–B5) landed and CI is green on `claude-review/final-launch-review-fixes`.
- [ ] `python -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q` is green (159+ pre-existing + 3 emergency-stop + 4 memory-CLI + 1 wiring tests = at least 167 passed).
- [ ] `ruff check` is clean on changed files.
- [ ] `apps/android && ./gradlew assembleDebug && ./gradlew lintDebug` is green; debug APK uploaded by `android-build.yml`.
- [ ] `docs/launch/RELEASE_NOTES_v1.0.0.md` reads correctly and is linked from `README.md`.
- [ ] Manual smoke (from `hermes` interactive CLI): `/jp hello` returns a persona prompt and a route.
- [ ] Manual smoke: `python -m hermes_cli.jarvis_prime stop` returns `{"cleared": 0, "tick_disabled": true}` and exits 0.
- [ ] No tracked file (excluding `.env.example` and fixtures) matches `BEGIN PRIVATE KEY`, `AWS_SECRET_ACCESS_KEY=`, `sk-ant-`, `sk-`, `ghp_`.
- [ ] Owner has read the new "Disabling / Rolling Back JARVIS Prime" section.
- [ ] Owner authorizes the `main_branch_merge` action with the exact phrase: **`Yes, with authorization.`**

If every box is ticked, this candidate is safe to merge to `main`.
