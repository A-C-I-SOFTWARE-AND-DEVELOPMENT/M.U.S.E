---
name: quality-council
description: "Run the scoring + merge engine over parallel worker outputs, produce a scorecard, council review, conflict report, and a plain-English summary, and decide whether to ship or escalate."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [scoring, merge, council, quality, validation, orchestration, audit]
    related_skills:
      - decision-quality-gate
      - local-quality-gate
      - aos-council-director
      - enterprise-council
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# Quality Council

The Quality Council is what Hermes runs *after* a parallel orchestration
job finishes. Several workers (Claude, GPT, OpenRouter, NovitaAI, a
local llama.cpp, …) have each tried to solve the same task in their
own sandbox. Each one dropped a fixed set of artifacts on disk. The
Council reads them, scores them across **sixteen** categories, decides
which one — if any — should ship, and writes a human-readable plan.

This skill is the playbook for invoking that pipeline correctly and
for *interpreting* what it produces. It does not implement the
pipeline; that lives in
[`hermes_cli/scoring.py`](../../hermes_cli/scoring.py) and
[`hermes_cli/merge_engine.py`](../../hermes_cli/merge_engine.py).

## When to invoke this skill

- After a parallel orchestration run completes
  (`/orchestrate <goal>` with N>1 workers).
- When a user asks "which worker should I pick?" / "why was this
  rejected?" / "show me the scorecard".
- Before any apply step in an orchestrated job — the Council's
  `final-plan.md` decides whether the diff is ready or needs eyes.
- When debugging a stuck or contentious orchestration run — the
  Council's outputs are the audit trail.

## Inputs the Council expects

Each worker writes a directory under `workers/<worker_id>/` with five
files. The Council does **not** crash if any are missing — it
downgrades the worker instead — but the more present, the better the
scoring.

| File | Purpose |
|---|---|
| `output.md` | Human-readable narrative — what the worker did and why. |
| `patch.diff` | Unified diff against the repo root. |
| `changed-files.txt` | Newline-separated list of relative paths. |
| `validation-output.txt` | Captured stdout/stderr of the validation run (tests / linters / etc.). The legacy filename `test-output.txt` is also accepted. |
| `status.json` | Structured metadata: `success`, `profile`, `elapsed_seconds`, `tokens`, optional `self_scores`. |

Optional, passed in by the orchestrator alongside the worker
directories:

- **Decision ledger** (`Sequence[Mapping[str, Any]]`) — prior decisions
  recorded by the orchestrator. The Council uses it to surface a note
  when the same worker has been rejected before for the same reason.
- **User profile** (`Mapping[str, Any]`) — the project owner's
  preferences, normally loaded from `~/.hermes/profile.json`. A
  `category_preferences` map inside it can bias any category on a
  per-worker basis.

## The sixteen scoring categories

| Category | What it measures |
|---|---|
| `correctness` | Did validation pass? Did the worker declare success? Is the patch non-empty? |
| `completeness` | Are all required artifacts present? Did the worker write meaningful prose? |
| `maintainability` | Diff size — small focused diffs score higher than sprawling ones. |
| `testability` | Were tests added? Did they pass? Is the change high-risk? |
| `architecture_fit` | Self-score, with a fallback heuristic on diff breadth and risk surface. |
| `repo_fit` | Does `patch.diff` actually look like a `diff --git` patch? Are claimed files reflected? |
| `security` | Combines validation outcome, high-risk path touches, and diff size. |
| `secrets_safety` | Scans the diff additions for recognisable secret patterns. A hit gives 0.0. |
| `mobile_fit` | Does the change support / not break Android, Termux, iOS, React Native paths? |
| `voice_fit` | Does the change support / not break voice / TTS / STT / audio paths? |
| `remote_execution_fit` | Penalises TTY-only, localhost-only, or hard-coded user-path patterns. |
| `developer_experience` | Output narrative depth + whether docs/help/error messages were touched. |
| `ui_ux` | Self-score, fallback to depth of `output.md`. |
| `speed` | Self-score, fallback to a curve over `elapsed_seconds`. |
| `cost_efficiency` | Self-score, fallback to a curve over `tokens`. |
| `jeremiah_fit` | Project-owner alignment. Defaults to a blend of `secrets_safety`, `security`, `remote_execution_fit`. Overridable via `user_profile.category_preferences.jeremiah_fit`. |

Every category is bounded to `[0.0, 1.0]`. A missing category resolves
to `0.5` (soft-neutral) rather than `0.0`, so a worker that omitted a
self-score is not punished as if it had failed it.

## The merge policy

The Council applies four gates in order before picking a winner:

1. **High-risk + no tests = rejected.** Any worker that touched a path
   matching `auth`, `secret`, `crypto`, `billing`, `payment`,
   `migration`, `schema`, `policy`, `permission`, or `gateway` and
   did not add tests is rejected outright — even if its weighted
   score is highest.
2. **Leaked secrets = rejected.** Any worker whose diff additions
   contain a recognisable secret (AWS key id, GitHub token, OpenAI
   key, PEM private key, etc.) is rejected outright. `secrets_safety`
   collapses to 0.0 and the worker drops below `SECRETS_SAFETY_FLOOR`.
3. **Score floor = rejected.** Workers whose `weighted_total` is
   below `SCORE_FLOOR` (0.45) are rejected with a recorded reason.
4. **Rank survivors.** The remaining workers are ranked by
   `weighted_total`, then by `correctness`, then by smaller diff
   size, then by worker id (for determinism). The top entry wins.

The merge engine **never splices patches together.** If you want
pieces from two workers, lift them by hand — blindly combining
diffs from independent agents is how you get a Frankenstein patch
that compiles but is wrong.

## The six output artifacts

The Council writes everything into a single `merge/` directory next
to the workers:

| File | Audience | What's in it |
|---|---|---|
| `scorecard.json` | Machines | Schema `hermes.merge.scorecard.v2`. Every worker's full breakdown, plus rejections and conflicts. |
| `council-review.md` | Reviewers | Selected worker, score table across every category, rejected workers with reasons, runners-up worth lifting from, conflicts, validation gates. |
| `conflict-report.md` | Reviewers | Per-file conflict details, or an explicit "no conflicts detected". |
| `final-plan.md` | The applier | What to apply, whether manual review is required, step-by-step apply instructions. |
| `final-patch.diff` | `git apply` | The winning worker's diff verbatim. Empty if no winner. |
| `plain-english-summary.md` | The project owner (on their phone) | One-page jargon-free summary: what happened, what's next, what still needs checking. |

## How to invoke the pipeline

From Python:

```python
from pathlib import Path
from hermes_cli.merge_engine import run_merge

result = run_merge(
    workers_dir=Path("./run-123/workers"),
    out_dir=Path("./run-123/merge"),
    user_profile=load_user_profile(),       # optional
    decision_ledger=load_ledger("run-123"), # optional
)

if result.manual_review_required:
    raise SystemExit(
        "merge needs a human; see ./run-123/merge/final-plan.md"
    )
# Otherwise the orchestrator can:
#   git apply --3way ./run-123/merge/final-patch.diff
```

From the CLI (once wired up by the orchestrator):

```bash
muse orchestrate merge ./run-123
# → writes ./run-123/merge/{scorecard.json,council-review.md,...}
```

## How to read the output as a reviewer

Open the artifacts in this order:

1. **`plain-english-summary.md`** first — 30 seconds, tells you whether
   anything is even worth your time.
2. **`final-plan.md`** — the apply plan and any validation gates the
   Council flagged.
3. **`council-review.md`** if you want the score table or want to see
   what the runners-up tried.
4. **`conflict-report.md`** if `final-plan.md` mentioned conflicts.
5. **`scorecard.json`** if you're building tooling on top of this.

If the plan says `MANUAL REVIEW REQUIRED`, do not let any automation
apply the patch. The gate exists because the Council found something
it could not resolve alone.

## What the Council will NOT do

- It will **never** blindly stitch patches from multiple workers.
- It will **never** apply a high-risk diff without tests.
- It will **never** apply a diff that looks like it contains a secret.
- It will **never** auto-merge when there's a conflict between
  surviving candidates.
- It will **never** execute the patch — that is the orchestrator's
  job, after the human-or-policy review gate.

## Cross-references

- [`docs/orchestration/scoring-merge-quality-council.md`](../../docs/orchestration/scoring-merge-quality-council.md)
  — the full reference for this stack.
- [`hermes_cli/scoring.py`](../../hermes_cli/scoring.py) — scoring
  implementation.
- [`hermes_cli/merge_engine.py`](../../hermes_cli/merge_engine.py) —
  merge policy implementation.
- [`templates/orchestration/scorecard.json`](../../templates/orchestration/scorecard.json)
  — schema template.
- [`templates/orchestration/council-review.md`](../../templates/orchestration/council-review.md)
  — review template.
- [`skills/decision-quality-gate/SKILL.md`](../decision-quality-gate/SKILL.md)
  — the pre-action gate that pairs with this post-action gate.
