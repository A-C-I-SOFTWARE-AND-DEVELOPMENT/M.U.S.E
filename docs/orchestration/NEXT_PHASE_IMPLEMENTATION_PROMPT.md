# Next-Phase Implementation Prompt

The fenced block below is the **exact copy/paste prompt** for the next
Claude Code session. It is self-contained: the reader does not need
the Phase 10 integration report first.

Branch convention: `claude/hermes-router-ledger-radar-wire-<suffix>`.

---

```text id="next-phase-router-ledger-radar-wire"
You are Claude Code working inside the muse repo.

GOAL: make the existing `muse orchestrate` / `/model-router explain`
/ `/decision-ledger show` / `/ai-radar update` surface honest by
wiring the runtime to the documents it already ships alongside. Stay
inside the listed scope. Do not also build end-to-end worker
execution, the competitive harvester automation, or the Android UI —
those are explicitly follow-on PRs.

Repository ground rules:
- Develop on a fresh branch
  `claude/hermes-router-ledger-radar-wire-<suffix>`.
- Land everything in one PR (draft).
- Preserve the private-local posture
  (see `docs/orchestration/private-local-mode.md` and
  `docs/hermes-local-orchestrator.md`): no remote sync, no telemetry,
  no Play Billing, no credential brokering, no autonomous external
  action.
- Reuse the primitives already in `main`. Do not duplicate them.
  Pre-existing pieces this PR builds on:
  - `hermes_cli/orchestrator.py` — job submit/list/resume/publish,
    today's keyword-table `model_router_explain`, today's JSON
    `_append_ledger` / `get_ledger`, today's placeholder
    `ai_radar_update`.
  - `hermes_cli/orchestrator_api.py` — local HTTP/WS control plane.
  - `hermes_cli/workers/` — adapter base class + 5 concrete adapters.
  - `hermes_cli/commands.py` — slash-command registry.
  - `docs/ai-intelligence/model-registry.yaml` — 8-worker catalog with
    strengths, fallbacks, quality/speed/cost tiers.
  - `docs/ai-intelligence/model-routing-policy.md` — deterministic
    routing rules and the 13 task-type taxonomy.
  - `docs/ai-intelligence/tool-capability-matrix.md` — 14 capability
    columns per worker.
  - `docs/orchestration/decision-ledger.md` — canonical markdown
    template + storage layout.
  - `docs/orchestration/decision-quality-system.md` — when a ledger is
    required and how skills validate it.
  - `skills/model-router/SKILL.md`,
    `skills/decision-quality-gate/SKILL.md`,
    `skills/ai-improvement-radar/SKILL.md`.

Deliverables (create or update):

1. `hermes_cli/model_router.py`
   - New module. Pure function
     `route(request: RouteRequest) -> RouteDecision`.
   - `RouteRequest`: `task: str`, `task_type: str` (one of the 13
     types in `model-routing-policy.md`), `evidence: list[str]`,
     `workspace: WorkspaceContext`, `available_workers: frozenset[str]`,
     `user_preferences: Mapping[str, Any]`.
   - `RouteDecision`: `primary: str`, `fallbacks: tuple[str, ...]`,
     `rationale: str`, `policy_version: str`, `matched_rules: tuple[str, ...]`.
   - Reads `docs/ai-intelligence/model-registry.yaml` once, caches per
     process.
   - Applies, in order: privacy filter (`task_type ==
     redaction_safe_draft` → only `redaction_safe = yes` workers from
     the capability matrix), capability filter (every disqualifying
     `no` cell drops the worker), preference filter
     (`user_preferences['model_router.preferred_workers']`,
     `prefer_local`, `cost_ceiling`, `quality_floor`), then the
     ordering rules from `model-routing-policy.md`.
   - Deterministic. No network. No LLM calls. No I/O outside the YAML
     read.

2. `hermes_cli/decision_ledger.py`
   - New module. SQLite-backed append-only ledger.
   - Schema (creates table on first call, idempotent):
     ```
     CREATE TABLE IF NOT EXISTS decisions (
       id              TEXT PRIMARY KEY,
       ts              INTEGER NOT NULL,
       actor           TEXT NOT NULL,
       goal            TEXT NOT NULL,
       lane            TEXT,
       worker          TEXT,
       model           TEXT,
       policy_version  TEXT,
       inputs_hash     TEXT,
       outputs_hash    TEXT,
       judge_verdict   TEXT,
       followups_jsonl TEXT
     );
     CREATE INDEX IF NOT EXISTS decisions_ts ON decisions(ts);
     ```
   - DB file lives at `~/.hermes/state.sqlite` (re-use the existing
     `hermes_state.py` bootstrap if practical; otherwise create a
     sibling connection — do NOT clone its schema).
   - API: `append(decision) -> id`, `list(filters) -> list[Decision]`,
     `show(id) -> Decision | None`,
     `replay(id) -> RouteDecision` (re-runs
     `hermes_cli.model_router.route` against the stored inputs;
     never re-invokes a worker).
   - **Append-only invariant.** No `UPDATE`. No `DELETE`. Tests must
     pin this.
   - Migration: on first call, if
     `~/.hermes/orchestrator/decision_ledger.json` exists, copy each
     entry into the new table (preserve the file as a read-only
     legacy export — do not delete it).

3. `hermes_cli/orchestrator.py` — small surgical edits only
   - `model_router_explain(prompt)` delegates to
     `hermes_cli.model_router.route`. Keep the old keyword-table
     behavior reachable behind a `legacy_keyword_table=True` kwarg so
     existing callers / tests are not broken in a single PR.
   - `_append_ledger(job_id, entry)` writes through
     `hermes_cli.decision_ledger.append` in addition to the legacy
     JSON file. The JSON file stays the read source until a follow-on
     PR flips it.
   - `ai_radar_update()` invokes the `/ai-improvement-radar` skill via
     the existing skill-dispatch path rather than stamping the
     placeholder JSON. If the skill is not loaded, fall back to the
     existing placeholder and surface a clear instructional message.

4. `apps/android/docs/ORCHESTRATOR_API.md`
   - Document (do not implement) the HTTP surface the Android cockpit
     will consume:
     `GET /v1/jobs`, `GET /v1/jobs/{id}`, `POST /v1/jobs`,
     `POST /v1/jobs/{id}/cancel`, `GET /v1/decisions`,
     `GET /v1/decisions/{id}`.
   - Reference `hermes_cli/orchestrator_api.py` and
     `docs/orchestration/local-api-backend.md` as the source of truth
     for the wire format.
   - Note that `/v1/proposals` (radar proposals) is intentionally
     deferred to the radar PR.

5. Tests under `tests/orchestrator/`
   - `test_model_router.py` — decision-table tests against the
     committed registry + policy. At minimum: one test per task type
     in `model-routing-policy.md`, plus capability-filter and
     preference-filter tests.
   - `test_decision_ledger.py` — append/list/show/replay round-trip,
     append-only invariant (an UPDATE attempt raises), legacy-JSON
     migration round-trip, and a `replay(id)` test that proves the
     reconstructed `RouteDecision` matches a freshly-routed one.
   - `test_orchestrator_router_integration.py` —
     `model_router_explain` returns the new shape; the legacy keyword
     output is reachable behind the kwarg; the slash-command parser
     handles both.

6. PR description must list:
   - the new `hermes_cli/model_router.py` and
     `hermes_cli/decision_ledger.py`,
   - the surgical edits to `hermes_cli/orchestrator.py`,
   - the new Android API contract doc,
   - the legacy compatibility surface that is preserved,
   - explicit out-of-scope items below.

Out of scope (do not implement in this PR):
- End-to-end worker execution beyond "queued" / "scaffolded".
  `--trusted-local` execution is a separate PR.
- AI-improvement radar implementation beyond invoking the existing
  skill.
- Competitive feature harvester automation
  (`skills/competitive-feature-harvester/` stays operator-triggered).
- Android Jobs / Decision Ledger / Radar Proposals UI (Kotlin side).
- Remote sync of the decision ledger. The ledger stays local.
- Schema changes to the kanban or session DB.

Validation before opening the PR:

    bash -n scripts/hermes-orchestrate.sh
    python -m py_compile hermes_cli/model_router.py \
                        hermes_cli/decision_ledger.py \
                        hermes_cli/orchestrator.py
    pytest tests/orchestrator -q
    grep -n "model_router_explain\|model_router.route" hermes_cli docs | head
    grep -n "decision_ledger\.append\|decisions(" hermes_cli docs | head

Keep the private-local posture intact. No new telemetry, no remote
sync, no provider tokens in the ledger. No autonomous external
action — the orchestrator continues to stop at "queued" /
"scaffolded" unless the operator explicitly opts in (and that opt-in
is the next PR's job, not this one's).
```

---

## Why this prompt is shaped the way it is

- **Self-contained.** A reader who has never seen the Phase 10 report
  can still execute it. Every artefact it references lives at a stable
  path on `main` and is named explicitly inside the prompt.
- **Scope-explicit.** The "out of scope" list keeps the next PR from
  growing into the same all-at-once design earlier phases tried.
- **Wire, don't invent.** The 8-worker registry, the 13 task-type
  taxonomy, the 14-column capability matrix, the canonical ledger
  template, and the radar skill all already exist. The PR's job is to
  connect the runtime to them, not to redesign them.
- **Append-only and migration-safe.** The new ledger preserves the
  legacy JSON file; the new router preserves the legacy keyword-table
  output behind a kwarg. No flag day.
- **No posture surface drift.** The private-local guarantees in
  `docs/orchestration/private-local-mode.md` and
  `docs/hermes-local-orchestrator.md` are referenced as immutable
  constraints, not as bullet points to "consider."
