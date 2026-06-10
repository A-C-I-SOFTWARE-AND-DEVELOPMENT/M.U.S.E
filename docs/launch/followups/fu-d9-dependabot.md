# FU-D9: Resolve Dependabot alerts — 1 critical, 3 moderate (Wave D G9)

- **Status:** in-review
- **Risk class:** additive (dependency security bumps; no default code-path changes)
- **Branch:** `claude/fu-d9-dependabot` · **Base:** `main` @ `e283d39ea`
- **PR:** #<n> (draft)
- **Owner-gate required to merge?** no — strictly additive security bumps; auto-merge on green CI per contract §6 (orchestrator's call)

## Intent (one paragraph)

GitHub reports 4 Dependabot alerts on `main` (1 critical, 3 moderate). No
direct Dependabot API access from this grain, so alerts were re-derived
locally: `npm audit` across all 8 npm lockfiles, `pip-audit` over a full
`uv export` (all extras + all groups), and OSV.dev batch queries over every
crate in `apps/desktop/src-tauri/Cargo.lock`, every npm package in every
lockfile, and the Android Gradle version catalog (Maven). Exactly 4
GitHub-reviewed advisories match — 1 critical + 3 moderate — and 3 are fixed
here; the 4th lives in `Cargo.lock`, which is owned by another in-flight
grain, so it is deferred to the orchestrator.

### Alert inventory

| # | Package | Version | Advisory | Severity | Manifest | Disposition |
|---|---------|---------|----------|----------|----------|-------------|
| 1 | `shell-quote` | 1.8.3 | GHSA-w7jw-789q-3m8p (CVE-2026-9277) — `quote()` does not escape newlines in object `.op` values | **critical** | `website/package-lock.json` (via `launch-editor`, which allows `^1.8.3`) | **Fixed** → 1.8.4 (in-range lockfile bump) |
| 2 | `uuid` | 8.3.2 | GHSA-w5hq-g745-h8pq (CVE-2026-41907) — missing buffer bounds check in v3/v5/v6 when `buf` provided | moderate | `website/package-lock.json` (via `sockjs`, which pins `^8.3.2`) | **Fixed** → 11.1.1 via *scoped* npm override (`sockjs > uuid`). **Flagged:** the patch only exists at 11.1.1+ (no 8.x backport), so this is a transitive major jump; scoped to `sockjs` only so mermaid's `uuid@14.0.0` is untouched. `sockjs` only calls top-level `uuid.v4()`, which is unchanged across 8→11. |
| 3 | `pynacl` | 1.5.0 | GHSA-mrfv-m5wm-5w6w (CVE-2025-69277) — bundled libsodium incomplete disallowed-inputs list | moderate | `uv.lock` (via `discord.py[voice]==2.7.1` in the `messaging` extra) | **Fixed** → 1.6.2 via `[tool.uv] override-dependencies`. **Flagged:** every discord.py release (≤ 2.7.1, latest) pins `PyNaCl<1.6`, so the patched 1.6.2 is unreachable without overriding that upper bound. Voice-path tests pass (see Validation). Remove the override once discord.py relaxes the cap. |
| 4 | `glib` (crate) | 0.18.5 | GHSA-wrw7-89jp-8q8g (RUSTSEC-2024-0429) — unsoundness in `VariantStrIter` `Iterator`/`DoubleEndedIterator` impls | moderate | `apps/desktop/src-tauri/Cargo.lock` | **DEFERRED to orchestrator** — `Cargo.lock` is owned by another in-flight grain (contract §3/§7). Fix is `glib >= 0.20`, which is coupled to the gtk-rs/tauri dependency stack in that grain's scope. |

Negative results (cross-check): all other npm lockfiles, the root
`package-lock.json`, the Gradle version catalog (`apps/android/gradle/libs.versions.toml`),
and GitHub Actions pins show **zero** GitHub-reviewed advisories. The other
Cargo.lock OSV hits (gtk-rs GTK3 bindings, `proc-macro-error`, `unic-*`) are
RUSTSEC *unmaintained* notices without GHSA review — Dependabot does not
alert on those. Tally = 1 critical + 3 moderate, matching GitHub exactly.

## Owned files (the ONLY files this task may write)

- `website/package.json` (scoped `overrides` entry only)
- `website/package-lock.json`
- `pyproject.toml` (`[tool.uv] override-dependencies` only)
- `uv.lock`
- `docs/launch/followups/fu-d9-dependabot.md` (this snapshot)

> `apps/desktop/src-tauri/Cargo.lock` is explicitly **not** owned and was not
> touched (alert #4 deferred).

## Plan (bounded steps)

1. Enumerate manifests; reproduce alerts via npm audit + pip-audit + OSV batch. ✅
2. Bump `shell-quote` 1.8.3 → 1.8.4 (in-range). ✅
3. Scoped override `sockjs > uuid` → `^11.1.1`; regenerate lockfile. ✅
4. `[tool.uv] override-dependencies = ["pynacl>=1.6.2"]`; `uv lock` (pynacl-only delta). ✅
5. Defer `glib` (Cargo.lock) to orchestrator. ✅
6. Validate, snapshot, draft PR. ✅

## Validation

- **npm audit (website), before:** `21 vulnerabilities (20 moderate, 1 critical)` → **after:** `found 0 vulnerabilities`
- **pip-audit (uv export, --all-extras --all-groups), before:** `Found 1 known vulnerability in 1 package — pynacl 1.5.0 CVE-2025-69277 fix 1.6.2` → **after:** `No known vulnerabilities found`
- `cd website && npm ci && npm run build` → pass (exit 0)
- `uv sync && uv run ruff check` → `All checks passed!`
- `uv run --extra dev ty check` → 7747 diagnostics — identical count to base (`git stash` A/B), no new diagnostics
- `uv run --extra dev --extra messaging pytest tests/gateway/test_discord_opus.py tests/gateway/test_discord_connect.py tests/gateway/test_discord_imports.py -q` → `20 passed` (exercises the discord.py voice/PyNaCl-adjacent paths)
- `python3 scripts/scan_secrets.py --base origin/main` → exit 0 (`ok: no high-confidence secrets`)
- Lockfile deltas are scoped: `uv.lock` diff touches only the `[manifest]` overrides block + the `pynacl` package entry; `website/package-lock.json` diff touches only `shell-quote`, `uuid`, and the override metadata.

## Residual / follow-on

- **Alert #4 (`glib` 0.18.5, moderate) is NOT fixed here** — deferred to the
  orchestrator because `apps/desktop/src-tauri/Cargo.lock` is owned by
  another in-flight grain. Fix requires glib ≥ 0.20 (gtk-rs stack bump),
  which should ride with that grain or a sequenced follow-up.
- The `pynacl>=1.6.2` uv override masks discord.py's `<1.6` cap repo-wide;
  remove it when discord.py publishes a release without the cap.
- The `sockjs > uuid ^11.1.1` npm override should be dropped if/when
  sockjs (or webpack-dev-server upstream) moves off uuid 8.x.
