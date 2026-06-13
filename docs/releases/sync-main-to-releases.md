# Sync `main` to all release channels

`main` is the source of truth, but releases are **tag-driven GitHub Releases**,
not branches. Three rolling channels track the latest source:

| Channel | What it is | Refreshed by |
|---|---|---|
| `M.U.S.E` | the rolling **source** tag + release | re-pointed to `main` HEAD (no build) |
| `android-latest` | the rolling **Android APK** download | the Android release workflow, in rolling mode |
| `muse-desktop-latest` | the rolling **desktop** installers (macOS/Win/Linux) | the desktop release workflow, in rolling mode |

Before this engine existed, the per-app release workflows only refreshed their
rolling channel when a `main` push **touched that app's own paths**
(`apps/android/**` / `apps/desktop/**`). So a change to docs, the core agent,
or anything else never reached the releases. This closes that gap.

## The engine: `sync-main-to-releases.yml`

[`.github/workflows/sync-main-to-releases.yml`](../../.github/workflows/sync-main-to-releases.yml)
is the workhorse — it holds the `contents: write` / `actions: write` token and
the runners. It runs on:

- **push to `main`** — only the cheap source-tag re-point runs (no APK/desktop
  rebuild on every commit).
- **schedule, hourly (`0 * * * *`)** — the unattended **auto-sync**: refreshes
  all three channels.
- **manual dispatch** — Actions → "Sync main to releases" → Run workflow, with
  a `targets` input (`all` | `android` | `desktop` | `source`).

For the app channels it dispatches the existing
[`android-release.yml`](../../.github/workflows/android-release.yml) and
[`muse-desktop-release.yml`](../../.github/workflows/muse-desktop-release.yml)
with `channel=rolling`, which refreshes the rolling download from the current
`main` (instead of cutting a new permanent versioned release — that stays the
one-button `workflow_dispatch` with no input).

## The button: `muse sync`

```
muse sync                      # refresh all three channels from main
muse sync --targets android    # just android-latest
muse sync --targets source     # just the M.U.S.E source tag
muse sync --dry-run            # print what would be dispatched; no side effects
```

`muse sync` is a thin trigger: it resolves the GitHub `origin` and runs
`gh workflow run sync-main-to-releases.yml --ref main -f targets=<…>`. It holds
**no** release credentials — the workflow does the publish. If `gh` is missing
or unauthenticated it prints the exact command (and the Actions URL) to run by
hand instead of failing, keeping the local-first, secret-free posture.

## Owner gate

Refreshing a release **publishes** (outward-facing). The automation only takes
effect once it is on `main` (merging is owner-gated) or when `muse sync` is run
against the live repo. The hourly cron and `muse sync` then keep the three
channels tracking `main` without re-typing tags.
