---
name: github-publisher
description: "Turns approved Hermes changes into branches, pull requests, and releases. Reads the decision ledger, refuses to ship anything not gated by decision-quality-gate, and never bypasses auth or signing."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    status: stub
    tags: [github, publisher, release, pr, orchestration, ship]
    related_skills:
      - hermes-orchestration-pipeline
      - decision-quality-gate
      - self-improvement-loop
      - aos-full-agent-team
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# GitHub Publisher (stub)

The ship-it end of the Hermes orchestration pipeline. After
`decision-quality-gate` has approved a change set, this skill is
responsible for turning the resulting job folder into a branch, a pull
request, and (when configured) a release — without leaving the
Hermes cockpit.

> **Status: Phase 1 placeholder.** This stub exists so the
> `github-publisher` references already in `AGENTS.md`, `README.md`,
> and the Phase 8 integration docs resolve to a real file. The
> behaviour below is the *intended* contract, to be implemented by
> the next Phase 1 pass.

## Intended invocation

```text
/github-publisher <branch>
```

Inputs (resolved from the active job folder):

- A diff or commit set produced by the builder lane.
- A decision ledger entry with `outcome: approved`.
- The target repo / branch policy from project settings.

Output:

- A pushed branch on the remote the user has authorised.
- A draft pull request linking back to the decision ledger entry.
- Optional release artefact when the project's release policy applies.

## Safety posture

- Never bypasses pre-commit hooks (`--no-verify` is refused).
- Never force-pushes to `main` / `master`.
- Refuses to publish anything without a matching `decision-quality-gate`
  approval in `ledger.jsonl`.
- Honours the local-first stance: nothing leaves the user's machine
  except git pushes to the user's own remote.

## Companion docs

- `AGENTS.md` — Orchestration pipeline skills (canonical contract).
- `docs/orchestration/decision-ledger.md` — ledger lifecycle.
- `docs/orchestration/hermes-orchestration-pipeline.md` — pipeline driver.
- `plugins/github/` — the existing native GitHub plugin this skill builds on.
