# muse — Remaining Work Plan
**Companion to `docs/AUDIT_REPORT.md` (2026-06-11).** Everything below is *not yet done*. Phases are ordered by dependency; each has a machine-checkable exit so "done" is a verdict, not a feeling. The Fable 5 build loop (`FABLE5_GOD_PROMPT.md` at repo root) is designed to execute this plan top-to-bottom, draining `improvement_queue.jsonl` between phases.

---

## Phase 0 — Land this drop (your machine, ~20 min)
1. Replace your working tree with this zip's contents (or diff-apply; changed files are listed at the bottom).
2. `pip install -e '.[axiom]'` — on Termux this skips z3 automatically (aarch64 marker) and the kernel runs in proven degraded mode.
3. Run the acceptance trio and keep the transcripts:
   - `cd axiom && python -m pytest tests/ && python smoke.py`
   - `python -m hermes_cli.jarvis_prime.axiom_bridge status` → `available: true`
   - `python -m pytest tests/test_jarvis_prime_gates.py tests/test_decision_ledger.py -q`
- **Exit:** 66 kernel tests green on *your* device, bridge `available: true`, regression files green.

## Phase 1 — Deepen the AXIOM hardwire (the orchestrator becomes risk-adaptive)
The bridge exists; now make the orchestration plane *consume* it.
1. **Risk-classified jobs:** in `hermes_cli/job_controller.py` + `hermes_cli/orchestrator_models.py`, call `get_bridge().classify_change(...)` when a Job is planned (loc/files estimated from the task graph; effects from declared tool surfaces) and run exactly the returned gate profile — LOW stops burning all eight gates on one-line changes; HIGH always includes OwnerApproval.
2. **Release gate requires the chain:** in `gates.py` release evaluator, FAIL when `get_bridge().audit()["chain_valid"]` is not True (skip when bridge inert). One conditional; makes "ship" mean "history verifies."
3. **Strict-evidence default at MED+:** orchestrator passes `strict_evidence=True` for MED/HIGH so self-attested packets can't pass.
4. **CI hermeticity:** export `MUSE_AXIOM_GATES=0` in unit-test workflows (or set `HERMES_HOME` to a temp dir) so gate-chaining never touches a runner's home.
- **Exit:** a deliberately mis-scoped HIGH job is blocked at OwnerApproval; a tampered ledger byte flips Release to FAIL; full `tests/` run stays green.

## Phase 2 — Flywheel everywhere (no action wasted, by construction)
1. Call `flywheel.record("owner.prompt", …)` at the gateway/TUI message entry; `("agent.action", …, outcome=…)` in the agent loop's tool-result handler; `("skill.used", …)` in the skill invoker; `("model.routed", …)` in model routing.
2. Add `muse flywheel` (or `/flywheel`) surfacing `digest()` + `pending()`; fold the digest into the existing daily owner brief.
3. Cron: nightly `digest()` + `audit()`; weekly auto-file the top pending improvements into `.plans/`.
- **Exit:** after one normal day of use, `digest()` shows all four event kinds, and a forced failure appears in `pending()` within the same session.

## Phase 3 — UE5 live smoke (needs a machine with the editor)
1. Install free UE5; enable **Remote Control API** + **Python Editor Script Plugin** (tick *Enable Remote Execution*); open any project.
2. `python -m hermes_cli.jarvis_prime.research_fabric.ue5 ping` → true; `…ue5 discover` → node id; `…ue5 console "stat fps"`; `…ue5 py "import unreal; unreal.log('muse')"`.
3. One real offscreen render: tiny Level Sequence → `MUSE_UE5_ALLOW_SPAWN=1` + `launch_offscreen_render(...)` → frames on disk; confirm the `ue5.render` event in `axiom_bridge tail`.
4. Then build the creative layer on top: a `ue5-render` skill (prompt-packet → sequence/script → gated render) and a Builder-mode recipe.
- **Exit:** all four live commands succeed; render artifact exists; every action visible in the ledger.

## Phase 4 — Surfacing (Android cockpit + docs truth)
1. Cockpit: an **Axiom panel** — `audit()` status chip (chain_valid ✔/✘), event tail, pending-improvements count; one new gateway route reading the bridge.
2. Docs: add `docs/axiom-integration.md` (bridge API, env vars, degraded mode, effect vocabulary) and a README row; fix the two rename artifacts **including CLAUDE.md:12 once you approve touching it**.
3. Decide sync-workflow semantics (full mirror vs filtered) now that it parses; adjust rsync excludes accordingly.
- **Exit:** cockpit shows live chain status; `grep -rn '"muse", "muse"'` returns nothing; sync runs green once on GitHub.

## Phase 5 — Hardening ladder (steady-state quality)
1. Triage the 40 TODO/FIXMEs into `improvement_queue.jsonl` (one command; the loop drains them).
2. Add `tests/test_axiom_bridge.py`, `tests/test_flywheel.py`, `tests/test_ue5_module.py` formalizing this session's live proofs (the proof scripts in the audit report are the test bodies).
3. Quarterly: re-run the full audit sweep set (compileall, collect-only, YAML/JSON parse, secrets) — codify as `scripts/self-audit.sh` + a `jarvis-self-audit-live` step.
- **Exit:** three new test files green in CI; self-audit script exits 0.

## Backlog (valuable, not urgent)
- MCP: expose the AXIOM MCP server (`axiom/axiom/interface/mcp_server.py`) in `.mcp.json` so Claude Code can attest units directly.
- Forge: route model-candidate selection through `axiom.forge.Tournament` so routing scorecards become Glicko-rated, ledger-backed.
- GraphRAG: index ledger events as graph nodes (decisions ↔ code ↔ evidence in one queryable graph).
- Re-upload `AXIOM_MASTER_PLAN.md` (arrived 0 bytes twice) if you want it archived in-repo.

---

### Files changed in this drop
**New:** `hermes_cli/jarvis_prime/axiom_bridge.py`, `hermes_cli/jarvis_prime/flywheel.py`, `hermes_cli/jarvis_prime/research_fabric/ue5.py`, `docs/AUDIT_REPORT.md`, `docs/REMAINING_WORK_PLAN.md`, `FABLE5_GOD_PROMPT.md`.
**Modified:** `hermes_cli/jarvis_prime/gates.py` (chain hook), `hermes_cli/decision_ledger.py` (chain hook), `hermes_cli/jarvis_prime/research_fabric/ue5_bridge.py` (→ compat shim), `axiom/axiom/core/contracts.py` (z3 optional), `axiom/axiom/core/verifier.py` + `axiom/axiom/interface/mcp_server.py` (honest check label), `.github/workflows/sync-aci-to-base44.yml` (YAML fix), `pyproject.toml` (axiom extra).
