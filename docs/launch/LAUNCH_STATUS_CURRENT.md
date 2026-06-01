# Launch Status — CURRENT

**Date:** 2026-06-01
**Base commit:** `084c132` (`main` tip)
**Supersedes:** [`LAUNCH_STATUS.md`](./LAUNCH_STATUS.md),
[`LAUNCH_READINESS_CHECKLIST.md`](./LAUNCH_READINESS_CHECKLIST.md),
[`LAUNCH_BRANCH_MATRIX.md`](./LAUNCH_BRANCH_MATRIX.md) (all dated 2026-05-26,
written against the now-211-commits-stale `bc97e43` / PR #131 baseline).
**Full audit:** [`../audits/CODEBASE_AUDIT_2026-06-01.md`](../audits/CODEBASE_AUDIT_2026-06-01.md).

## Verdict

**🟢 GREEN on everything runnable in-repo; 🟡 YELLOW pending CI-only Android
build; permission-posture risk (B6) reviewed and ACCEPTED by owner (ship-as-is,
2026-06-01).**

The prior "🔴 RED — 52%" verdict is obsolete: the integration it tracked
(worker engine, orchestrator replay, cockpit↔ledger bridge, Android rebrand,
chat screen, interactive icon) has all landed on `main`, and
lint/tests/lockfile are green. A later feature ("Sentient JARVIS avatar", #170)
expanded the permission surface (accessibility service, system overlay,
query-all-packages, always-on microphone) beyond the original safety model;
the owner reviewed this (audit §5 B6) and chose to ship as-is, accepting the
Play-policy/privacy risk. Recommended-but-not-gating follow-ups: runtime
consent, Play declarations, privacy disclosure.

## Evidence captured this audit (local, CI-equivalent)

| # | Check | Command | Status |
|---|---|---|---|
| C1 | Blocking lint | `ruff check .` | 🟢 All checks passed |
| C2 | Windows footguns | `python scripts/check-windows-footguns.py --all` | 🟢 638 files clean |
| C3 | Lockfile integrity | `uv lock --check` | 🟢 218 packages resolved |
| C4 | Launch-critical tests | `pytest` (owner_auth + gates + workpacket + jarvis_prime) | 🟢 234 passed |
| C5 | Full Python suite | `pip install -e ".[all,dev]" && pytest -m "not integration"` | 🟡 see "Full suite" below |
| C6 | Owner-gate audit hatch | `AUTHORIZATION_PHRASE` + `OwnerAuth` present in `owner_auth.py` | 🟢 present |

### Full suite (C5)

<!-- FULL_SUITE_RESULT -->
_Run in progress — result appended on completion._

## Pending (CI-only — cannot run in this container)

| # | Check | Owner | Status |
|---|---|---|---|
| P1 | `android-build.yml` → `assembleDebug` | CI | 🟡 needs CI run on launch branch |
| P2 | `android-build.yml` → `testDebugUnitTest` | CI | 🟡 needs CI run |
| P3 | `android-build.yml` → `lint` | CI | 🟡 needs CI run |
| P4 | Permissions vs `bc97e43` baseline | owner | 🟡 **6 added & ACCEPTED** (`RECORD_AUDIO`, `QUERY_ALL_PACKAGES`, `SYSTEM_ALERT_WINDOW`, `BLUETOOTH_CONNECT`, 2× foreground-service) via "Sentient avatar" (#170). Owner accepted ship-as-is 2026-06-01. See audit **B6**. |
| P5 | `launch-gate.yml` aggregate green | CI | 🟡 rolls up P1–P4 + Python checks |
| P6 | `tests/agent/lsp/test_client_e2e.py` | — | 🟢 **6 passed** under `uv run` — the "baseline failures" were a stray-pytest env artifact (missing `pytest-asyncio`), not a code bug |

## Residual non-blockers

- `ui/screens/placeholder/PlaceholderScreen.kt` is defined but **unreferenced**
  (no live route binds it) — safe to remove in cleanup.
- Android test depth below the roadmap target (ViewModel ≥80% + per-screen
  Compose smoke + instrumented E2E + a label-gated emulator CI job).
- Minor product TODOs (ClawHub publish, Google Chat Card v2 buttons, Feishu
  @-lookup, Gemini multimodal part, one bridge transport) — see the audit §4.

## Owner-gated steps remaining (performed only on owner authorization)

- Merge the launch branch to `main` (`main_branch_merge`).
- Any deploy / package publish / app-store submission.

The gate code (`OWNER_GATED_ACTIONS`, `AUTHORIZATION_PHRASE`, `OwnerAuth`,
emergency-stop) is **not** modified.
