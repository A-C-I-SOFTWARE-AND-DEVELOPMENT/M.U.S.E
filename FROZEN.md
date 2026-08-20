# M.U.S.E is frozen

**Frozen:** 2026-08-20
**Tag:** `muse/frozen-2026-08-20`
**Branch at freeze:** `claude/work-packet-repair`
**Archive branch:** `muse/archive`

This repository is a **preserved future project**. It is no longer the place where work
happens. Active development moved to the consolidated Hermes repo at
`C:\Users\Echer\hermes-agent-latest`.

## Do not commit here

A `pre-commit` hook in `.git/hooks/` blocks commits. If you find yourself editing files in
this tree, you are in the wrong repository.

## Why it was frozen

M.U.S.E was a fork of `NousResearch/hermes-agent`. By 2026-08-20 it had drifted to the
point where the drift itself was the problem:

- It lacked Bot Mode and **1,203 other upstream paths**.
- It carried unrepaired damage from merge `d938501dd3` (2026-08-10) — 756 conflicts
  resolved in ten minutes by a sync bot, inconsistently in both directions. **13 files lost
  ~794 upstream symbols.** Three of them (`hermes_cli/banner.py`, `uninstall.py`,
  `slack_cli.py`) were left as the pre-merge MUSE blob with the upstream file discarded
  entirely.
- ~38% of its edits to shared files were pure branding churn that conflicted on every
  upstream sync and bought nothing.

The decision was to start from pristine upstream and port the fork's capabilities in,
de-branded, rather than keep merging upstream into a damaged tree.

## What this archive contains

The complete fork at its final state, including material that was never tracked in git:

| Archive | What |
|---|---|
| `C:\Users\Echer\Archive\M.U.S.E-frozen-2026-08-20` | Byte-exact filesystem mirror, including gitignored paths and `checkpoints/needle2.pkl` (87 MB, deliberately kept out of git) |
| `C:\Users\Echer\Archive\M.U.S.E.git` | Bare git mirror — the fetch source for the consolidation port, so the live tree is never touched |

The freeze commit itself captured 107 previously-uncommitted files (+15,259 lines),
including a live source module (`hermes_cli/jarvis_prime/run_store.py`), the entire
untracked `foundry/` + `docs/foundry/` + `tests/foundry/` trees, and the
`skills/creative/{game-studio,guide-first}` and `skills/mlops/local-role-loras` packs.

## Key commits

| Commit | Meaning |
|---|---|
| `e2fd462ebe` | True fork point from upstream (2026-05-19) |
| `bb78a5bf1c` | Pre-merge MUSE tip — **the correct source for the true MUSE delta** |
| `d938501dd3` | The damaging merge (2026-08-10) |
| `a98aee47ce` | Upstream v0.20.0 tip; merge parent #2 |
| `d797a925d3` | Fork tip before freeze |

To recover what MUSE actually authored on any shared file, diff
`e2fd462ebe..bb78a5bf1c` — **not** against the merge base, which is contaminated by the
bad merge and its repairs.

## Port status

What was carried into Hermes and what was deliberately left behind is tracked in
`docs/consolidation/PORT-LEDGER.md` in the consolidated repo.

Deliberately **not** ported: the Vercel/commercial deployment stack (`vercel.json`,
`vercel_app.py`, repo-root `api/`, `web/musehq`, `deploy/`,
`docker-compose.hosted.yml`) — MUSE product surface rather than agent capability. It
remains here, intact, if the MUSE product is ever revived.

The MUSE branding, persona, and identity live on only in this archive. The consolidated
repo presents as Hermes.
