# Next-Phase Implementation Prompt

The fenced block below is the **exact copy/paste prompt** for the next
Claude Code session. It is self-contained: it does not require the
reader to have read the Phase 10 integration report first.

Branch convention: `claude/hermes-orchestrate-entry-point-<suffix>`.

---

```text id="next-phase-orchestrator-entry-point"
You are Claude Code working inside the Hermes repo.

GOAL: land the first real `hermes orchestrate` entry point. The Phase 10
report (`docs/orchestration/final-hermes-orchestration-integration-report.md`)
explains the surrounding design. This PR is the minimum implementation
that makes that design usable end-to-end. Stay inside the listed scope.
Do not also build the AI-improvement radar, the competitive harvester,
or the Android UI — those are explicitly follow-on PRs.

Repository ground rules:
- Develop on a fresh branch `claude/hermes-orchestrate-entry-point-<suffix>`.
- Land everything in one PR (draft).
- Preserve the private-local posture
  (see `docs/hermes-local-orchestrator.md`):
  no remote sync, no telemetry, no Play Billing, no credential
  brokering, no autonomous external action.
- Reuse existing primitives where they already exist
  (`enterprise/council.py`, `plugins/kanban/`, `hermes_cli/kanban*.py`,
  `hermes_cli/cron.py`, `hermes_cli/webhook.py`, the
  `skills/autonomous-ai-agents/*` worker skills). Do not duplicate
  them.

Deliverables (create or update):

1. `hermes_cli/orchestrator.py`
   - `python -m hermes_cli.orchestrator` entry point.
   - Subcommands: `submit`, `status`, `cancel`, `decisions`.
   - `submit` accepts: a free-text goal, `--lane {kanban,council,direct}`,
     `--worker {claude-code,codex,opencode,hermes}`,
     `--model <id>`, `--ledger/--no-ledger`, `--dry-run`,
     `--workspace <path>`.
   - Sensible defaults: lane=auto (pick kanban for multi-step,
     direct for single-step), worker chosen by the model router,
     ledger on.
   - Pure orchestration: no LLM calls inside this module. Defer to
     adapters.

2. `hermes_cli/orchestrator_adapters/`
   - `__init__.py` exporting an `Adapter` protocol with
     `name`, `supports(task) -> bool`, `submit(task) -> RunHandle`,
     `status(handle) -> RunState`, `cancel(handle)`.
   - One thin adapter per existing skill:
     `claude_code.py`, `codex.py`, `opencode.py`, `hermes_self.py`.
   - Each adapter is a shell-out (or in-process call for
     `hermes_self`) — keep them small; the heavy logic stays in the
     skills.

3. `hermes_cli/model_router.py`
   - Pure function `route(request: RouteRequest) -> RouteDecision`.
   - Reads `docs/ai-intelligence/model-registry.yaml`.
   - Applies `docs/ai-intelligence/model-routing-policy.md` rules.
   - Returns an ordered candidate list with fallback chain and a
     short justification string.

4. `docs/ai-intelligence/model-registry.yaml`
   - YAML source of truth keyed by canonical model id
     (`anthropic:claude-sonnet-4-6`, `anthropic:claude-opus-4-7`,
     `openai:gpt-…`, `openrouter:…`, `local:llama.cpp:…`).
   - Per-model fields: `context_window`, `tools` (bool),
     `vision` (bool), `latency_class` (fast|standard|slow),
     `cost_class` (free|low|standard|premium),
     `privacy_class` (local|provider|byok),
     `provider_terms_class` (subscription|api|both).

5. `docs/ai-intelligence/model-routing-policy.md`
   - The human-readable rules the router applies.
   - At minimum: privacy-class filter, tool/vision capability filter,
     latency/cost ordering, fallback chain.

6. `docs/ai-intelligence/tool-capability-matrix.md`
   - Which Hermes tools each worker adapter exposes by default,
     and which ones require explicit operator approval.

7. `hermes_cli/decision_ledger.py`
   - SQLite-backed append-only ledger.
   - Schema:
     `decisions(id TEXT PRIMARY KEY, ts INTEGER NOT NULL,
                actor TEXT, goal TEXT, lane TEXT, worker TEXT,
                model TEXT, policy_version TEXT,
                inputs_hash TEXT, outputs_hash TEXT,
                judge_verdict TEXT, followups_jsonl TEXT)`.
   - Migration lives next to the existing `hermes_state.py` schema
     bootstrapping.
   - API: `append(decision)`, `list(filters)`, `show(id)`,
     `replay(id) -> RouteDecision` (re-computes what *would* be
     decided now, without re-running).

8. `scripts/hermes-orchestrate.sh`
   - Replace the documentation stub with a real shim:
     `exec python -m hermes_cli.orchestrator "$@"`.
   - Must still pass `bash -n`.

9. `skills/devops/hermes-orchestrate/SKILL.md`
   - Operator-facing skill: when to use `hermes orchestrate`,
     how to read decision-ledger output, how to pick a lane and a
     worker, how to dry-run.
   - Frontmatter follows the same shape as
     `skills/devops/kanban-orchestrator/SKILL.md`.

10. Slash command `/orchestrate` in `hermes_cli/commands.py` and the
    relevant slash-command registry so in-session submission works
    from the CLI and the messaging gateway.

11. Tests under `tests/orchestrator/`:
    - `test_model_router.py` — decision-table tests against the
      committed registry + policy.
    - `test_decision_ledger.py` — append/list/show/replay round-trip;
      append-only invariant.
    - `test_adapter_protocol.py` — every adapter satisfies the
      `Adapter` protocol; happy-path submit with a mocked backend.
    - `test_orchestrator_cli.py` — `--dry-run` returns the planned
      lane/worker/model without side effects.

12. Design docs:
    - `docs/orchestration/job-controller-roadmap.md` — how
      `hermes orchestrate` plugs into Kanban dispatch and the council
      runtime; what is in v1 vs v2.
    - `docs/orchestration/worker-adapter-interface.md` — the
      `Adapter` protocol contract, error semantics, cancellation,
      and how to add a new adapter.

13. `apps/android/docs/ORCHESTRATOR_API.md`
    - Document (do not implement) the HTTP surface the Android
      cockpit will consume:
      `GET /v1/jobs`, `GET /v1/jobs/{id}`, `POST /v1/jobs`,
      `POST /v1/jobs/{id}/cancel`, `GET /v1/decisions`,
      `GET /v1/decisions/{id}`.
    - Note that proposals (`/v1/proposals`) belong to the
      AI-improvement radar PR and are out of scope here.

Out of scope (do not implement in this PR):
- AI-improvement radar (`docs/ai-intelligence/ai-improvement-radar.md`
  is intentionally not on the deliverables list — leave for the next
  PR after this one).
- Competitive feature harvester
  (`docs/competitive/openhuman-paperclip-research.md`, etc.).
- Best-coding-tool mission doc (`docs/mission/best-coding-tool-mission.md`).
- Android Jobs / Ledger UI implementation (Kotlin side).
- Remote sync of the decision ledger.

Validation before opening the PR:

    bash -n scripts/hermes-orchestrate.sh
    python -m hermes_cli.orchestrator --help
    python -m hermes_cli.orchestrator submit "demo goal" --dry-run
    pytest tests/orchestrator -q
    grep -R "hermes orchestrate" -n docs hermes_cli scripts | head

PR description must list:
- the new CLI entry,
- the registry + policy + ledger landed,
- which adapters are wired,
- which skills got a frontmatter bump,
- explicit out-of-scope items above.

Keep the private-local posture intact. No new telemetry, no remote
sync, no provider tokens in the ledger.
```

---

## Why this prompt is shaped the way it is

- **Self-contained.** A reader who has never seen the Phase 10 report
  can still execute it. The first sentence inside the prompt points at
  the report for context, but every deliverable is restated.
- **Scope-explicit.** The "out of scope" list keeps the next PR from
  growing into the same all-at-once design the previous phases tried
  to do.
- **Tests-first deliverables.** `tests/orchestrator/` is item 11
  rather than an afterthought, because the model router and ledger are
  exactly the kind of pure-function code that benefits most from
  decision-table tests.
- **No new posture surface.** The private-local guarantees in
  `docs/hermes-local-orchestrator.md` are referenced as immutable
  constraints, not as bullet points to "consider."
