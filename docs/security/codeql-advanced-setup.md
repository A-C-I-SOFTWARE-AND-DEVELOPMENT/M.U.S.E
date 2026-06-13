# CodeQL: advanced setup (activation guide)

The repository ships an **advanced** CodeQL configuration at
[`.github/codeql/codeql-config.yml`](../../.github/codeql/codeql-config.yml) —
it excludes the sha-pinned `autoresearch/vendor` tree (`paths-ignore`) and a
known false-positive query (`py/clear-text-logging-sensitive-data`).

That config is **only honored by an advanced workflow**, not by CodeQL *default
setup*. Historically the repo had default setup enabled, so the config was
ignored — which produced two symptoms:

- the **"CodeQL" check failing in ~2 seconds** (the default-setup aggregate), and
- **un-suppressed vendor alerts** (the `paths-ignore` never applied).

The advanced workflow [`.github/workflows/codeql.yml`](../../.github/workflows/codeql.yml)
fixes both by consuming the config. It is **dormant until activated**: every job
is gated on `vars.CODEQL_ADVANCED == 'true'`, so until the variable is set the
jobs render as *skipped* (neutral) and add no failing check.

## Activation (two owner-only steps)

CodeQL default setup and advanced setup **cannot run at the same time** — the
advanced `init` step errors while default setup is enabled. So activate in this
order:

1. **Switch to advanced setup.** Repo → **Settings → Code security → Code
   scanning → CodeQL analysis → Set up / Configure → switch from _Default_ to
   _Advanced_** (this disables default setup). GitHub will offer to commit a
   starter workflow — decline it; `codeql.yml` already exists.
2. **Enable the workflow.** Repo → **Settings → Secrets and variables → Actions
   → Variables → New repository variable**: `CODEQL_ADVANCED` = `true`.

After both, the next push to `main` (or the weekly schedule, a PR, or a manual
**Actions → CodeQL → Run workflow**) runs the first-party language legs
(`python`, `javascript-typescript`, `actions`) with the committed config applied
— the 2-second failure disappears and the two vendor alerts clear on the next
scan.

## Deactivation / rollback

Set `CODEQL_ADVANCED` to anything other than `true` (or delete the variable) to
make the jobs skip again. To return to default setup, re-enable it in the Code
scanning settings (it cannot coexist with this workflow once both are active).

## Language scope

The matrix targets the first-party languages analyzable without a build:
`python`, `javascript-typescript`, `actions`. Dropped on purpose: `csharp` /
`ruby` / `rust` / `c-cpp` (default-setup false detections, no first-party code),
and `java-kotlin` — CodeQL can't analyze the Android Gradle/Kotlin app
(`apps/android`) in `build-mode: none` (it reports a configuration error needing
a full Android build); that app is already covered by `android-build.yml` (lint
+ unit tests + APK build). Re-add `java-kotlin` only with a working autobuild +
Android SDK setup.
