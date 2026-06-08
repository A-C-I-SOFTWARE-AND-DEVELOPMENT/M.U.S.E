# Launch Review — 2026-06-01

**Date:** 2026-06-01
**Base commit:** `084c132` (`main` tip)
**Full audit:** [`../audits/CODEBASE_AUDIT_2026-06-01.md`](../audits/CODEBASE_AUDIT_2026-06-01.md)
**Live readiness rollup:** [`LAUNCH_STATUS_CURRENT.md`](LAUNCH_STATUS_CURRENT.md)

An honest, short snapshot of where the launch stands as of this date. It
supersedes the PR #131 / `bc97e43`-era review docs in this folder (those are
banner-marked stale). It does not re-litigate history.

## Verdict

**Green on everything runnable in-repo. The only remaining launch verification
is CI-only (Android build + the `launch-gate` aggregate). The permission-posture
item (B6) is owner-accepted ship-as-is.**

## What is green (verified locally this audit)

| Check | Command | Result |
|---|---|---|
| Blocking lint | `ruff check .` | All checks passed |
| Windows footguns | `python scripts/check-windows-footguns.py --all` | 638 files clean |
| Lockfile integrity | `uv lock --check` | 218 packages resolved |
| Launch-critical tests | `pytest` (owner_auth + gates + workpacket + jarvis_prime) | 234 passed |
| Owner-gate audit hatch | `AUTHORIZATION_PHRASE` + `OwnerAuth` present | present |

The runtime, gateway, worker engine, orchestrator, MUSE package, and
the Android cockpit (incl. the now-landed **chat screen** and **interactive
icon**) are real and substantially complete. See the audit §3 for the full map.

## Permission posture (B6) — owner-accepted

The "Sentient MUSE avatar" feature (#170) expanded the Android permission
surface beyond the original safety model: accessibility service, system
overlay, `QUERY_ALL_PACKAGES`, and always-on microphone. These back real
shipped features and are a Play Store policy risk. **The owner reviewed this on
2026-06-01 and elected to ship as-is, accepting the Play-policy / privacy
risk** (the recommendation against it is logged). The permission risk-register
has been reconciled to the shipped reality. Recommended-but-not-gating
follow-ups before public store submission: runtime consent per capability, Play
Console declarations, and a privacy-policy disclosure. Full detail: audit §5
**B6**.

## Remaining launch verification (CI-only)

These cannot run in the audit container (no Android SDK) and must be confirmed
on a fresh CI run on the launch branch:

- `android-build.yml` → `assembleDebug`, `testDebugUnitTest`, `lint`.
- Permissions vs the `bc97e43` baseline: **6 added & owner-accepted** (see B6).
- `launch-gate.yml` aggregate green (rolls up the Android jobs + Python checks).

The historical "LSP e2e failures" were a stray-`pytest` env artifact (missing
`pytest-asyncio`); under `uv run --extra all --extra dev pytest` all 6 pass.
See audit §5 **B3**.

## Owner-gated steps still pending (owner authorization only)

- Merge the launch branch to `main` (`main_branch_merge`).
- Any deploy / package publish / app-store submission.

The gate code (`OWNER_GATED_ACTIONS`, `AUTHORIZATION_PHRASE`, `OwnerAuth`,
emergency-stop) is not modified.
