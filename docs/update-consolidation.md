# `update` — consolidating upstream + your branch into main

On a **fork**, `hermes update` (and telling Jarvis to "update", "sync my
fork", or "merge upstream") does more than pull the latest release: it
**consolidates** the original code and your in-flight work into your fork's
`main` in one reviewed step.

It brings together:

- **the original** — `upstream/main` (the official
  `NousResearch/hermes-agent` repo your fork tracks), and
- **your branch** — whatever branch is currently checked out,

resolving any conflicts and showing you a review **before** anything lands
on `main`.

## How it works

1. Ensures the `upstream` remote exists (prompts to add it if missing), then
   fetches `upstream` and `origin`.
2. Builds a throwaway integration branch (`hermes/update-integration`) from
   your fork's `origin/main`.
3. Merges `upstream/main`, then your current branch, into the integration
   branch.
4. **Conflict handling** — for each conflicted file:
   - If a model is configured (see below), Jarvis auto-resolves the conflict
     and the result is validated to contain no leftover conflict markers.
   - Otherwise — or if a resolution can't be made cleanly — it **safe-stops**:
     the merge is aborted, `main` is left untouched, and the conflicted files
     are listed for you to resolve manually. It never guesses silently.
5. Runs the critical-files syntax guard over the integrated tree.
6. Prints a **review** (diffstat + the files it auto-resolved) and asks for
   confirmation.
7. Only on approval does it fast-forward `main` to the reviewed result and
   delete the integration branch. Your original branch is restored on every
   other path.

Merging into `main` is governed by the LaunchGate policy (see
`docs/launch/AUTOMATED_MERGE_POLICY.md`), so the gate here is a
review-and-confirm prompt — not the `"Yes, with authorization."` owner
phrase. Use `--yes` to skip the prompt in automation.

## Enabling model-assisted conflict resolution

Auto-resolution reuses the stdlib model bridge, configured by environment
(any OpenAI-compatible endpoint — OpenAI, OpenRouter, NIM, local llama.cpp):

```bash
export SELF_AUDIT_MODEL_BASE_URL="https://api.openai.com/v1"
export SELF_AUDIT_MODEL_NAME="gpt-4o-mini"   # or anthropic/claude-…
export SELF_AUDIT_MODEL_KEY="sk-…"           # omit for keyless local servers
```

Without these set, conflicts trigger the safe-stop path described above.

## Flags and scope

- `hermes update --no-consolidate` — forks only: skip consolidation and use
  the legacy behavior (fast-forward `main` from `origin`).
- `hermes update --yes` — assume yes for the review prompt (and other
  interactive prompts).
- **Non-fork installs** (a direct clone of the official repo) are unchanged:
  there is no separate "your main vs upstream", so consolidation is skipped
  automatically.

## Implementation

- Core logic: `hermes_cli/branch_consolidation.py`
  (`consolidate_into_main`).
- Wired into the update flow at `_cmd_update_impl` in `hermes_cli/main.py`.
- Natural-language trigger: the `UPDATE` intent in
  `hermes_cli/jarvis_prime/natural_language_coder.py`.
- Tests: `tests/hermes_cli/test_branch_consolidation.py`.
