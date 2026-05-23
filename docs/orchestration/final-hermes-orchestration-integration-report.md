# Hermes Orchestration — Final Integration Report

> **Document status:** Phase 10 synthesis. This is the consolidated
> roadmap-plus-status document for the Hermes orchestration build. It is
> a planning artifact: it inventories what is *already shipping in
> `main`*, what is *designed but not yet implemented*, and exactly which
> PR should land next.
>
> Where prior phases (0–9) reference design documents that have not yet
> been committed to this repository (`docs/orchestration/phase-0-…`,
> `docs/ai-intelligence/…`, `docs/competitive/…`, `docs/mission/…`),
> those documents are listed under **Known limitations** and rolled into
> the next-phase prompt. This report stands on its own as the canonical
> entry point.

---

## 1. Executive verdict

Hermes already ships the load-bearing primitives for a private,
multi-worker orchestrator:

- A **Kanban dispatcher** with worker lifecycle, sticky blocks, and
  decomposition rules (`plugins/kanban/`, `hermes_cli/kanban*.py`,
  `skills/devops/kanban-orchestrator`, `skills/devops/kanban-worker`).
- A **multi-agent council runtime** with planning, dispatch, judging,
  audit, and escalation policy (`enterprise/council.py`,
  `enterprise/judge.py`, `enterprise/audit.py`, `enterprise/policy.py`,
  `skills/enterprise-council/*`).
- A **codex-as-lane convention** so a Hermes worker can delegate
  bounded implementation to an external coding agent without giving up
  task ownership (`skills/autonomous-ai-agents/kanban-codex-lane`).
- A **worker-adapter skill set** for the three external coding agents
  Hermes routes to today (`skills/autonomous-ai-agents/claude-code`,
  `…/codex`, `…/opencode`).
- A **cron scheduler + webhook subscription** stack so jobs can be
  triggered on schedule or by external events
  (`hermes_cli/cron.py`, `hermes_cli/webhook.py`,
  `skills/devops/webhook-subscriptions`).
- A **private-local Android cockpit** that runs as a foreground
  service, never calls provider APIs directly, never scrapes
  credentials, and hands off via clipboard + deep links
  (`apps/android/`, `docs/hermes-local-orchestrator.md`).
- A **first-class GitHub plugin** with allowlists, write gates, and
  token redaction (`plugins/github_assistant/`,
  `docs/github-integration.md`).

What is **not yet built and is the subject of the next PR**:

- A first-class `hermes orchestrate` CLI entry point that ties Kanban,
  the council runtime, the codex/claude-code/opencode lanes, and the
  Android cockpit together as one job-controller interface.
- A formal **model registry + routing policy** (currently expressed
  implicitly through `hermes model`, `cli.py` provider switching, and
  per-skill model hints).
- A persistent **decision ledger** (currently implicit in
  `enterprise/audit.py` audit rows and Kanban heartbeats).
- An **AI-improvement radar** that reads recent runs and proposes
  skill/prompt/model adjustments — `skills/enterprise-council/monitor`
  is the precursor.
- A **competitive feature harvester** that tracks Claude Code,
  Codex, OpenCode, OpenHuman, Paperclip, and other coding agents and
  surfaces parity gaps.
- The **Android APK cockpit UX** for queuing, monitoring, and
  approving orchestrated jobs (today the app is a chat client + manual
  handoff dashboard).

The verdict: **the primitives exist and are production-quality; the
unifying job-controller surface is the next PR.**

---

## 2. What was added (Phase 10)

Phase 10 is documentation-only by design. The deliverables landing in
this PR are:

| Path | Purpose |
|---|---|
| `docs/orchestration/final-hermes-orchestration-integration-report.md` | This file. Canonical synthesis of the orchestration build. |
| `docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md` | The exact copy/paste Claude Code prompt for the next PR. |
| `scripts/hermes-orchestrate.sh` | Documentation-stub entry point. Prints status and links to the integration report and next-phase prompt. Replaced by a real implementation in the next PR. |

No production code paths were modified.

---

## 3. What was updated (Phase 10)

Nothing. Per the phase brief: "do not add large new features. Only fix
small documentation consistency issues if discovered." No such issues
were uncovered during this pass that warranted blocking the report.

---

## 4. Agents converted into Hermes skills (already in `main`)

The following external coding agents are reachable from Hermes as
first-class skills today:

| Skill | Description | Path |
|---|---|---|
| `claude-code` | Delegate to Anthropic's Claude Code CLI. | `skills/autonomous-ai-agents/claude-code/SKILL.md` |
| `codex` | Delegate to OpenAI's Codex CLI. | `skills/autonomous-ai-agents/codex/SKILL.md` |
| `opencode` | Delegate to OpenCode (community OSS coding agent). | `skills/autonomous-ai-agents/opencode/SKILL.md` |
| `kanban-codex-lane` | Hermes-owned Kanban worker that uses Codex as a bounded implementation lane. | `skills/autonomous-ai-agents/kanban-codex-lane/SKILL.md` |
| `hermes-agent` | Self-referential skill — how to configure, extend, or contribute to Hermes itself. | `skills/autonomous-ai-agents/hermes-agent/SKILL.md` |

These skills are the worker side of the orchestration; the
**orchestrator** side is split across:

| Skill | Description | Path |
|---|---|---|
| `kanban-orchestrator` | Decomposition playbook and anti-temptation rules for the orchestrator profile. | `skills/devops/kanban-orchestrator/SKILL.md` |
| `kanban-worker` | Pitfalls, examples, and edge cases for Kanban workers. | `skills/devops/kanban-worker/SKILL.md` |
| `enterprise-orchestrator` | One-tap goal decomposition for the enterprise council. | `skills/enterprise-council/orchestrator/SKILL.md` |
| `enterprise-judge` | Per-step judge for council outputs. | `skills/enterprise-council/judge/SKILL.md` |
| `enterprise-monitor` | Post-run reviewer that proposes improvements (AI-improvement radar precursor). | `skills/enterprise-council/monitor/SKILL.md` |

The five **leaf domain agents** under `skills/enterprise-council/`
(`sales`, `finance`, `hr`, `customer-service`, `operations`) are the
canonical example of "an agent expressed as a Hermes skill with a typed
contract to a runtime."

---

## 5. New Hermes skills (Phase 10 roadmap)

The next-PR prompt provisions the following new skills:

| Skill | Purpose |
|---|---|
| `hermes-orchestrate` | Top-level skill that drives `hermes orchestrate …` job submission, lane selection, and follow-up. |
| `model-router` | Apply the model-registry routing policy to a candidate task. |
| `decision-ledger` | Append, query, and replay decisions from the orchestrator's persistent ledger. |
| `ai-improvement-radar` | Scan the ledger + recent audit trail and propose skill / prompt / model adjustments. |
| `competitive-feature-harvester` | Refresh `docs/competitive/*.md` with the latest deltas from peer coding agents. |
| `android-cockpit-bridge` | Documented contract between the Android app and the orchestrator HTTP surface. |

None of these are committed in Phase 10.

---

## 6. How to invoke inside Hermes

### Today (already works)

```bash
# Interactive CLI
hermes

# Kanban-driven orchestration (existing)
hermes kanban create "<goal>"
hermes kanban dispatch
hermes kanban status

# Council-driven orchestration (existing, programmatic only)
python -c "from enterprise.council import plan, dispatch; …"

# Scheduled / event-driven
hermes cron create "0 9 * * 1" "<prompt>" --skills "<csv>" --deliver telegram
hermes webhook subscribe <name> --events "<csv>" --prompt "<…>"

# External coding agents from a Hermes session
/<skill>            # e.g. /claude-code, /codex, /opencode, /kanban-codex-lane

# Android cockpit
adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk
# then point at your gateway, or run in mock mode
```

### Next PR (designed, not yet built)

```bash
# Single one-tap entry point
hermes orchestrate "<goal>" [--lane kanban|council|direct]
                            [--worker claude-code|codex|opencode|hermes]
                            [--ledger]
                            [--dry-run]

# Wrapper for the same thing from any shell or from the Android app
scripts/hermes-orchestrate.sh "<goal>"
```

The current `scripts/hermes-orchestrate.sh` in this PR is a
documentation stub; the next PR replaces it with a real shim that
forwards to `python -m hermes_cli.orchestrator`.

---

## 7. Model-router behavior (design)

A first-class model router does not exist yet. Today, model selection
is done by:

- `hermes model` interactive switcher (`hermes_cli/model_switch.py`,
  `hermes_cli/models.py`).
- `cli.py` provider/model routing per conversation.
- Per-skill `model:` hints in skill frontmatter where present.
- Kanban dispatcher per-profile model assignments.

**Target shape** (next PR):

1. `docs/ai-intelligence/model-registry.yaml` — the source of truth.
   Keyed by canonical model id (`anthropic:claude-sonnet-4-6`,
   `openai:gpt-…`, `openrouter:…`, `local:llama.cpp:…`), with fields
   for `context_window`, `tools`, `vision`, `latency_class`,
   `cost_class`, `privacy_class`, and `provider_terms_class`.
2. `docs/ai-intelligence/model-routing-policy.md` — the rules. Inputs:
   task type, latency budget, cost ceiling, privacy posture, tool
   requirements. Output: ordered candidate list with fallback chain.
3. `hermes_cli/model_router.py` — pure function that consumes a
   `RouteRequest` and returns a `RouteDecision`. No I/O, deterministic,
   unit-tested.
4. The router is invoked by `hermes orchestrate` *and* by Kanban
   dispatch *and* by the council runtime — three callers, one policy.

---

## 8. Decision-ledger behavior (design)

A persistent decision ledger does not exist as a standalone artifact
yet. The closest things in `main`:

- `enterprise/audit.py` — append-only audit rows for council runs.
- Kanban DB heartbeats and state transitions
  (`hermes_cli/kanban_db.py`).
- Session DB (`hermes_state.py`) with FTS5 search and LLM-summarized
  recall.

**Target shape** (next PR):

1. SQLite table `decisions(id, ts, actor, goal, lane, worker, model,
   policy_version, inputs_hash, outputs_hash, judge_verdict,
   followups_jsonl)` — append-only, never updated in place.
2. CLI surface: `hermes decisions list`, `hermes decisions show <id>`,
   `hermes decisions replay <id>`.
3. The ledger is the substrate the AI-improvement radar reads from.
4. Privacy: ledger stays local. No remote sync. No telemetry.

---

## 9. AI-improvement radar behavior (design)

`skills/enterprise-council/monitor/SKILL.md` is the precursor: it
defines the role of a post-run reviewer that scans the audit trail and
hands improvement candidates to the curator. The radar formalizes
this:

1. Cron-triggered (e.g. weekly) `hermes orchestrate --improve` run.
2. Reads the decision ledger and recent audit rows.
3. Emits **proposals** (skill version bumps, prompt edits, model
   re-routes, new worker adapters to try), never auto-applies them.
4. Writes proposals to a human-reviewed queue (file or Kanban lane).
5. Curator skill (`/curator`, see `hermes_cli/curator.py`) is the only
   thing that can promote a proposal into a skill/repo change.

---

## 10. Competitive feature harvester behavior (design)

A docs-only skill that periodically refreshes
`docs/competitive/*.md` with the latest deltas from peer coding
agents. Inputs: docs URLs, changelogs, release notes, blog posts, the
agent's own CLI `--help`. Outputs: a markdown table of feature
differences with confidence per row.

The skill must not auto-PR competitive parity work — it surfaces, the
operator decides.

`hermes-already-has-routines.md` (already in the repo) is an example
of the format the harvester should produce.

---

## 11. OpenHuman / Paperclip findings and confidence

Neither `docs/competitive/openhuman-paperclip-research.md` nor any
prior phase artifact exists in this branch. From open public sources
the unverified position is:

- **OpenHuman** appears to be a multi-agent coordination project
  emphasising long-horizon planning. Confidence: **low** — public
  surface is small and the name collides with multiple unrelated
  projects. The next-PR harvester must verify the canonical project
  URL before any parity claim is made.
- **Paperclip** appears to be a research/utility coding agent or
  paperclip-maximiser themed evaluation harness, depending on the
  origin. Confidence: **low** for the same disambiguation reason.

The next-PR harvester is responsible for resolving both ambiguities
and producing `docs/competitive/openhuman-paperclip-research.md` with
named URLs, dated snapshots, and a parity table. Until then, no claim
about feature deltas in this report should be relied on.

---

## 12. Android APK cockpit UX requirements

Today (`apps/android/`, `docs/hermes-local-orchestrator.md`,
`apps/android/docs/ARCHITECTURE.md`):

- Foreground-service-backed dashboard, MVVM, Material 3.
- Three runtime modes: remote gateway, local Termux gateway, mock.
- Manual handoff via clipboard + deep links — no automated provider
  API calls, no credential scraping, no in-app billing.
- No queue UI for orchestrated jobs; no per-worker status; no judge
  output rendering.

**Required for the orchestration cockpit** (next PR will document the
API surface; full UI work is a follow-on PR):

1. A **Jobs** tab listing `hermes orchestrate` submissions with their
   lane, worker, model, current state, and last heartbeat.
2. A **Decision Ledger** tab (read-only) backed by the
   `hermes decisions` endpoint.
3. A **Radar Proposals** queue with approve/dismiss actions that round-trip
   to the curator on the gateway side.
4. **Approval prompts** for any worker step the policy gate flags as
   high-risk — pushed to the device as a notification with two
   buttons.
5. **Continued private-local posture**: every external call still
   goes through a manual handoff or an approved worker; no Play
   Billing; no telemetry.

The HTTP contract the Android app needs (proposed):

```
GET  /v1/jobs              # list active + recent orchestrated jobs
GET  /v1/jobs/{id}         # detail incl. lane, worker, model, ledger refs
POST /v1/jobs              # submit a new orchestration request
POST /v1/jobs/{id}/cancel  # cooperative cancel
GET  /v1/decisions         # ledger list (filterable)
GET  /v1/decisions/{id}    # ledger detail incl. judge verdict
GET  /v1/proposals         # radar proposals queue
POST /v1/proposals/{id}    # approve / dismiss
```

All routes are gateway-local, bearer-auth, and never accept third-party
provider tokens.

---

## 13. Private-local posture

This stays a hard constraint across all phases:

- **No commercial subscription surface.** No Google Play Billing, no
  in-app purchases, no paywall, no product IDs. The Android app is
  a private companion.
- **No credential brokering.** Hermes does not scrape cookies, extract
  tokens, automate hidden login flows, or read another app's storage.
- **No unofficial provider proxying.** The Android cockpit does not
  call OpenAI / Anthropic / etc. APIs directly in the primary
  workflow. Handoffs are explicit and user-initiated.
- **No autonomous external action.** Every clipboard write or deep
  link requires a tap.
- **Local storage by default.** Decision ledger, session DB, memory,
  and Kanban DB all live under `~/.hermes/` (or the Android app's
  private sandbox). No remote sync ships by default.
- **HMAC on every webhook.** Existing
  `skills/devops/webhook-subscriptions` requirement carries forward.
- **Approval-gated risky tools.** Existing approval prompts in the
  CLI carry forward to the cockpit's approval-notification surface.

See `docs/hermes-local-orchestrator.md` for the canonical statement of
this posture and the manifest-level proof
(`android:exported="false"`, no intent-filter, `Stop` action on the
foreground notification).

---

## 14. Validation summary

The phase-10 validation block, run against this branch:

```bash
grep -R "final-hermes-orchestration-integration-report\|NEXT_PHASE_IMPLEMENTATION_PROMPT" -n docs
find skills -maxdepth 2 -name SKILL.md | sort
bash -n scripts/hermes-orchestrate.sh
```

Expected results after this PR lands:

1. The `grep` finds at least the two new files under
   `docs/orchestration/` plus any inbound links.
2. The `find` returns the two depth-2 skill files that have always
   lived at the top of their skill packs (`skills/dogfood/SKILL.md`,
   `skills/yuanbao/SKILL.md`). Deeper skill files require
   `-maxdepth 3` (or higher) and are listed elsewhere in this report —
   see §4.
3. `bash -n scripts/hermes-orchestrate.sh` returns clean (the stub is
   syntactically valid).

These three checks pass for the Phase 10 deliverable. They do **not**
verify that the orchestration runtime works — that is the next PR.

---

## 15. Known limitations

The named artifacts below were referenced in the Phase 10 brief but
were not committed to this repository by Phases 0–9. They are folded
into the next-phase implementation prompt:

- `docs/orchestration/phase-0-evidence-audit.md`
- `docs/orchestration/hermes-agent-skill-map.md`
- `docs/orchestration/decision-ledger.md`
- `docs/orchestration/decision-quality-system.md`
- `docs/ai-intelligence/model-registry.yaml`
- `docs/ai-intelligence/model-routing-policy.md`
- `docs/ai-intelligence/tool-capability-matrix.md`
- `docs/ai-intelligence/ai-improvement-radar.md`
- `docs/competitive/openhuman-paperclip-research.md`
- `docs/mission/best-coding-tool-mission.md`
- `docs/orchestration/job-controller-roadmap.md`
- `docs/orchestration/worker-adapter-interface.md`
- `docs/orchestration/phase-9-validation-report.md`

Other limitations of the current state:

- `hermes orchestrate` does not exist yet; today the orchestrator is
  reachable only through `hermes kanban`, the council runtime called
  in-process, or per-skill slash commands.
- The model router is implicit; there is no single function that
  takes a task and returns a justified routing decision.
- The decision ledger does not exist as its own table; council audit
  rows are the closest analogue.
- The competitive harvester does not exist; competitive notes today
  are hand-written documents like `hermes-already-has-routines.md`.
- The Android app does not yet have a Jobs / Ledger / Radar surface;
  it is a chat client + manual handoff dashboard.
- The OpenHuman / Paperclip research has not been verified against
  canonical project URLs.

None of these are blockers for shipping Hermes today. They are the
work the next PR exists to do.

---

## 16. Next recommended implementation PR

**Scope:** introduce `hermes orchestrate` as a real, tested entry
point. Land just enough of the model registry, routing policy, decision
ledger, worker-adapter interface, and Android HTTP contract to make
that command useful end-to-end. Defer the AI-improvement radar, the
competitive harvester, and the Android UI to follow-on PRs.

**Concretely:**

1. `hermes_cli/orchestrator.py` — `python -m hermes_cli.orchestrator …`
   entry, wired into `hermes_cli/commands.py` so `hermes orchestrate`
   resolves.
2. `hermes_cli/orchestrator_adapters/` — worker-adapter interface
   plus thin adapters that dispatch to the existing skills:
   `claude_code.py`, `codex.py`, `opencode.py`, `hermes_self.py`.
3. `hermes_cli/model_router.py` + `docs/ai-intelligence/model-registry.yaml`
   + `docs/ai-intelligence/model-routing-policy.md`.
4. `hermes_cli/decision_ledger.py` + a SQLite migration creating the
   `decisions` table under `~/.hermes/state.sqlite`.
5. `scripts/hermes-orchestrate.sh` — replace the stub with a real
   shim that forwards arguments to `python -m hermes_cli.orchestrator`.
6. `skills/devops/hermes-orchestrate/SKILL.md` — the operator-facing
   skill teaching how and when to use `hermes orchestrate`.
7. Slash command `/orchestrate` wired up in the CLI for in-session
   submission.
8. Tests under `tests/orchestrator/` covering: model-router decision
   tables, ledger append + replay, each adapter's happy path with a
   mock backend, and the slash-command parser.
9. `docs/orchestration/job-controller-roadmap.md` and
   `docs/orchestration/worker-adapter-interface.md` — the design docs
   referenced in §15.
10. Android HTTP contract documented in
    `apps/android/docs/ORCHESTRATOR_API.md`. (App-side wiring is a
    separate PR.)

**Out of scope** for the next PR (explicitly):

- AI-improvement radar implementation.
- Competitive feature harvester.
- OpenHuman / Paperclip canonical-URL verification.
- Android Jobs / Ledger / Radar UI.
- Remote sync of the decision ledger.

The exact copy/paste prompt that implements this scope lives in
`docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md`.

---

## 17. Exact next Claude Code prompt for the next PR

The full prompt is maintained as its own file so it can be pasted
directly into a fresh Claude Code session without dragging this
report's narrative with it:

> [`docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md`](./NEXT_PHASE_IMPLEMENTATION_PROMPT.md)

Open that file, copy the fenced block, and paste it into Claude Code
on a fresh `claude/hermes-orchestrate-entry-point-<suffix>` branch.

— end of Phase 10 report —
