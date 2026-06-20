# Compile SYNAPSE in CI on your Legion (self-hosted runner)

No GitHub-hosted runner ships Unreal Engine, and the cloud authoring container
has no UE/GPU. To make the UE compile + `Synapse.Geometry` tests run
**automatically in CI on your own machine**, register the Legion as a
**self-hosted runner**. Then [`.github/workflows/synapse-ue-build.yml`](../../../.github/workflows/synapse-ue-build.yml)
builds `apps/synapse-ue/Synapse.uproject` and the PR gets a green UE check —
closing the OWNER-BLOCKER with no manual step.

> Prefer a one-off? You don't need any of this — just double-click
> `apps\synapse-ue\tools\build-legion.bat` (see `build-on-legion.md`). The
> runner is only for *automatic* CI compiles.

## ⚠️ Security first (M.U.S.E is a public repo)

Self-hosted runners on **public** repos are dangerous by default: a pull request
from a fork could run arbitrary code on your Legion. Before registering a runner,
lock down PR runs:

- **Settings → Actions → General → Fork pull request workflows** → set
  **"Require approval for all external contributors"** (or all outside
  collaborators). Now fork PRs can't run on your machine without your click.
- Keep the runner box treated as untrusted-input-facing: run it in a dedicated
  Windows user account, not your daily admin login.

This workflow only triggers on `apps/synapse-ue/**` changes, `main`/`claude/**`
pushes, and manual dispatch — but the approval gate above is still required.

## Prerequisites (the Legion)

- Unreal Engine **5.6** at `C:\Program Files\Epic Games\UE_5.6` (override via the
  `UE_ROOT` env on the runner if elsewhere).
- Visual Studio 2022 with *"Game development with C++"*.
- Git + Git LFS.

## Register the runner (~5 min, one-time)

1. Repo **Settings → Actions → Runners → New self-hosted runner → Windows (x64)**.
2. Follow the shown commands on the Legion (PowerShell): download, then
   `config.cmd` with the **token GitHub shows you**. When prompted for labels,
   add: `UE5_6` (the `self-hosted` and `Windows` labels are added automatically).
   The workflow targets `[self-hosted, Windows, UE5_6]`.
3. Run it as a service so it's always available:
   ```
   .\svc.cmd install
   .\svc.cmd start
   ```
   (or `run.cmd` to run interactively while you watch the first build).

## Verify

- Re-run the check from the PR (or **Actions → "SYNAPSE UE build (self-hosted)"
  → Run workflow** on `claude/kind-pascal-kry8mh`), or push any change under
  `apps/synapse-ue/**`.
- The job compiles (`Build.bat SynapseEditor Win64 Development`) then runs
  `Automation RunTests Synapse.Geometry`, uploading the report artifact.
- **Green = OWNER-BLOCKER cleared.** Tell me (or flip PR #537 out of draft) and it
  can merge.

## Notes

- This is the **monorepo bridge**. When the standalone SYNAPSE repo is split out
  (master plan §5), the equivalent `apps/synapse-ue/.github/workflows/build-win64.yml`
  goes live at that repo's root and this root workflow can be removed.
- The runner needs ~100 GB free for the UE build cache; first compile is slow,
  later ones are incremental.
- No binary assets are added to the repo by this workflow.
