# JARVIS Prime — Current State Audit

**Date:** 2026-05-25  
**Auditor:** Jarvis Prime (senior build lead session)  
**Branch:** main  
**Repo:** A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent  
**Status:** READ-ONLY — no runtime code changed

---

## Executive Summary

Jarvis Prime is a real, working product. It is not a stub. The CLI runs, the gateway runs, skills are wired, and the AOS council registry verifies clean. However, Jarvis Prime exists primarily as an **identity layer** over the Hermes Agent runtime — there is no `hermes_cli/jarvis_prime/` Python module, no `CANONICAL_REPO.md`, and no `test_jarvis_prime_*.py` test files. These are the three highest-priority gaps.

The risk is not that Jarvis Prime doesn't work. The risk is that the distinction between "what is Jarvis Prime natively" and "what is inherited Hermes behavior" is entirely undocumented in code. A new wave of build work could either (a) duplicate Hermes capabilities inside a new Jarvis module, or (b) leave Jarvis Prime permanently dependent on Hermes internals without clear extension points.

This audit draws the line.

---

## 1. What Exists Today

### 1.1 CLI Entry Points — WORKING

**pyproject.toml `[project.scripts]`:**

```
jarvis-prime = "hermes_cli.main:main"
jarvis        = "hermes_cli.main:main"
hermes        = "hermes_cli.main:main"
hermes-agent  = "run_agent:main"
jarvis-agent  = "run_agent:main"
hermes-acp    = "acp_adapter.entry:main"
jarvis-acp    = "acp_adapter.entry:main"
```

All three user-facing names (`jarvis-prime`, `jarvis`, `hermes`) map to the **same** `hermes_cli.main:main` function. There is no separate Jarvis Prime dispatcher.

**Verification result:**
```
python -m hermes_cli.main --help  → PASS (full subcommand tree shown)
python -m hermes_cli.jarvis_prime --help  → FAIL (module does not exist)
python -m hermes_cli.jarvis_prime classify "review this build"  → FAIL (module does not exist)
```

### 1.2 CLI Subcommand Surface — WORKING

`hermes_cli/main.py` exposes 42 subcommands:

```
chat, model, fallback, gateway, proxy, lsp, setup, postinstall,
whatsapp, slack, send, login, logout, auth, status, cron, webhook,
kanban, hooks, doctor, dump, debug, backup, checkpoints, import,
config, pairing, skills, bundles, plugins, curator, memory, tools,
computer-use, mcp, sessions, insights, claw, version, update,
uninstall, acp, profile, completion, dashboard, logs
```

None of these are Jarvis Prime–specific subcommands. They are all Hermes runtime commands.

### 1.3 Package Identity — WIRED

`pyproject.toml`:
- `name = "jarvis-prime"`
- `version = "0.14.0"`
- `description = "JARVIS Prime, a local-first personal AI operating partner forked from Hermes Agent"`

The package is branded as Jarvis Prime. The runtime is 100% Hermes CLI code.

### 1.4 Skills Layer — EXISTS

| Skill | Path | Status |
|-------|------|--------|
| `jarvis-prime` | `skills/jarvis-prime/SKILL.md` | ✅ WIRED — activation manifest with 6 operating modes |
| `jarvis-code-operator` | `skills/jarvis-code-operator/SKILL.md` | ✅ WIRED — coding workflow controller |
| `mobile-voice-development` | `skills/mobile-voice-development/SKILL.md` | ✅ WIRED — mobile capture skill |
| `aos-enterprise-council` | `skills/aos-enterprise-council/` | ✅ WIRED — full council structure + registry |
| `autonomous-ai-agents` | `skills/autonomous-ai-agents/` | EXISTS |
| `github` | `skills/github/` | EXISTS |
| `hermes-orchestration-pipeline` | `skills/hermes-orchestration-pipeline/` | EXISTS |

### 1.5 AOS Enterprise Council Registry — VERIFIED PASSING

```
skills/aos-enterprise-council/operating-registry/registry.json
```

- Version: 3.0.0
- Active council: 6 members (council-director, evidence-architect, delivery-scope-controller, product-experience-architect, assurance-risk-director, contrarian-reviewer)
- Domain specialists: 8
- Registry verifier: `python skills/aos-enterprise-council/scripts/verify_registry.py` → **PASS**

Historical registry (reference only, NOT operating):
- `registry/AOS_AGENT_REGISTRY_COMPLETE.md` — 233 agents
- `registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md` — 108 sub-agents
- Total recovered: 341 named roles (not all runnable)

### 1.6 Documentation Layer — EXISTS

| File | Status |
|------|--------|
| `docs/jarvis-prime-operating-system.md` | ✅ COMPLETE — identity, modes, hierarchy, principles, owner gates |
| `docs/jarvis-verification-gates.md` | ✅ COMPLETE — 8 gates defined |
| `docs/aos-jarvis-agent-routing.md` | ✅ COMPLETE — routing plan, council/specialist/worker/persona distinctions |
| `docs/jarvis-code-operator-workflow.md` | ✅ COMPLETE — builder mode workflow |
| `docs/mobile-voice-development-workflow.md` | ✅ EXISTS |
| `docs/slack-mobile-command-policy.md` | ✅ EXISTS |
| `docs/memory-and-personality-policy.md` | ✅ EXISTS |

### 1.7 Gateway & Messaging — WORKING INFRASTRUCTURE

- `hermes_cli/gateway.py` (231 KB) — multi-platform process management (systemd, launchd, Windows Scheduled Task)
- `hermes_cli/gateway_windows.py` (43 KB) — Windows schtasks.exe integration
- `hermes_cli/slack_cli.py` — Slack manifest generator with full OAuth scopes
- `hermes_cli/pairing.py` — DM pairing system for multi-user access control
- `gateway/` directory — full messaging runtime (Discord, Telegram, Slack, WhatsApp, Signal, Email, Matrix, Home Assistant)

### 1.8 Owner Gate System — DOCUMENTED, PARTIALLY WIRED

**Documented gate phrase:** `"Yes, with authorization."`

Owner gates are enforced in:
- `skills/jarvis-prime/SKILL.md` ✅
- `skills/jarvis-code-operator/SKILL.md` ✅
- `skills/mobile-voice-development/SKILL.md` ✅
- `skills/aos-enterprise-council/operating-registry/registry.json` ✅ (`"owner_gate_phrase"` field)
- `docs/jarvis-verification-gates.md` ✅ (Owner Approval Gate section)

Owner gates in code:
- `hermes_cli/terminal_tool.py` — `set_approval_callback()`, `_get_approval_callback()` ✅
- `run_agent.py` — `_set_approval_callback`, `_set_sudo_password_callback` imports ✅

**Gap:** No programmatic enforcement of Jarvis Prime–specific owner gates. The gates exist at the skill/doc layer. Code-level enforcement depends on Hermes terminal_tool approval callbacks, not a Jarvis-owned gate module.

### 1.9 Mobile / Termux Support — DOCUMENTED, WIRED VIA HERMES

- `constraints-termux.txt` — Termux dependency constraints ✅
- `pyproject.toml` — `termux` and `termux-all` extras ✅
- `skills/mobile-voice-development/SKILL.md` — mobile capture workflow ✅
- Termux command: `cd /data/data/com.termux/files/home/hermes-agent && hermes "JARVIS capture: <idea>"` ✅

No Jarvis Prime–specific Android APK, no Termux-native launch script, no mobile-specific config file distinct from Hermes.

---

## 2. What Is Working

| Component | Working? | Verified How |
|-----------|----------|--------------|
| CLI (`jarvis-prime` binary) | ✅ | Resolves to `hermes_cli.main:main`; help output confirmed |
| AOS registry verifier | ✅ | `verify_registry.py` passes |
| Gateway infrastructure | ✅ | Code present; 231 KB gateway.py + platform runners |
| Slack manifest generator | ✅ | Code present |
| Skills activation system | ✅ | SKILL.md manifests present and correctly structured |
| Package install | ✅ | `.venv` with Python 3.14.4; `jarvis_prime.egg-info` installed |
| Owner gate callbacks (code) | ✅ | `terminal_tool.py` approval callbacks present |
| Memory system | ✅ | `hermes_cli/memory_setup.py`, `curator.py`; plugin system in `plugins/` |
| AOS council (doc layer) | ✅ | 6-member council + 8 specialists, verified registry |

---

## 3. What Is Only Documented, Not Wired

| Gap | Location of Docs | Wired in Code? |
|-----|-----------------|----------------|
| `hermes_cli/jarvis_prime/` Python module | Implied by audit spec | ❌ DOES NOT EXIST |
| `python -m hermes_cli.jarvis_prime classify` | Implied by audit spec | ❌ DOES NOT EXIST |
| `CANONICAL_REPO.md` | Implied by audit spec | ❌ DOES NOT EXIST |
| `test_jarvis_prime_*.py` test suite | Implied by audit spec | ❌ DOES NOT EXIST |
| Jarvis Prime–specific CLI subcommands | None documented | ❌ No `jarvis-prime capture`, `jarvis-prime classify` subcommands in main.py |
| AOS council invocation from CLI | `aos-jarvis-agent-routing.md` | ❌ No CLI hook to activate council programmatically |
| Mobile voice mode auto-detection | `mobile-voice-development/SKILL.md` | ❌ No runtime phone/voice surface detection |
| Logistics specialist | `jarvis-prime-operating-system.md` | ❌ No specialist file in `specialists/` |
| Career Strategy specialist | `jarvis-prime-operating-system.md` | ❌ No specialist file in `specialists/` |
| `skills/` subdirectory in aos-enterprise-council | README says "not yet populated" | ❌ Empty |
| `personas/` subdirectory | README says "not yet populated" | ❌ Empty |
| `product-roles/` subdirectory | README says "not yet populated" | ❌ Empty |

---

## 4. What Is Duplicated or Stale

| Duplication | Risk | Recommendation |
|------------|------|----------------|
| 233 top-level + 108 sub-agents in historical registry vs. 6-member operating council | MEDIUM — confusion about which agents are runnable | Historical registry is properly labeled "reference only" in docs. Keep as-is. |
| `AOS_AGENT_REGISTRY_COMPLETE.md` exists in both root and `skills/aos-enterprise-council/registry/` | LOW — redundant copies | Root copy is the historical import artifact; council copy is the working reference. Both should stay; root copy should have a header pointing to the council version. |
| `docs/aos-jarvis-agent-routing.md` defines 9-member daily council vs. `operating-registry/registry.json` defines 6-member council | MEDIUM — routing plan is stale | `aos-jarvis-agent-routing.md` lists 9 members (includes `claude-code-builder`, `codex-reviewer`, `memory-evidence-curator`). The operating registry has 6. Routing plan needs updating to match registry. |
| `jarvis-prime`, `jarvis`, `hermes` all point to same main function | LOW — intentional aliasing | Documented. No action needed unless Jarvis Prime needs its own dispatcher. |
| `hermes-agent` and `jarvis-agent` both point to `run_agent:main` | LOW — intentional aliasing | Same as above. |
| Three overlapping skills for the same coordination layer (jarvis-prime, jarvis-code-operator, mobile-voice-development) | LOW — each has distinct scope | Well-scoped. Keep all three. They are not duplicates; they are layered responsibilities. |

---

## 5. What Should Be Extended Instead of Replaced

| Component | Extend With | Do Not Replace |
|-----------|------------|----------------|
| `hermes_cli/main.py` | Add `jarvis_prime` subcommand dispatcher that routes `capture`, `classify`, `council` | Do not rewrite the full argument parser |
| `skills/aos-enterprise-council/operating-registry/registry.json` | Add Logistics Specialist + Career Strategy Specialist entries | Do not create a second registry file |
| `skills/jarvis-prime/SKILL.md` | Add `classify` routing table to routing model section | Do not replace SKILL.md; extend it |
| `docs/jarvis-prime-operating-system.md` | Reference this audit + gap map | Do not replace; add links |
| `gateway/` directory | Add Jarvis Prime–specific Slack slash commands | Do not fork the gateway |
| `tests/` directory | Add `tests/test_jarvis_prime_*.py` suite | Do not restructure existing test directories |

---

## 6. Highest-Risk Gaps

| Rank | Gap | Risk | Blast Radius |
|------|-----|------|-------------|
| 1 | No `hermes_cli/jarvis_prime/` module | Build work could create a competing second CLI layer OR leave Jarvis Prime permanently non-extensible at the Python level | HIGH |
| 2 | No `test_jarvis_prime_*.py` tests | Any new Jarvis Prime behavior ships unverified | HIGH |
| 3 | No `CANONICAL_REPO.md` | No single authoritative document defining source of truth; wave builds can conflict | MEDIUM |
| 4 | `aos-jarvis-agent-routing.md` lists 9-member council but registry has 6 | Agent routing decisions made from stale plan | MEDIUM |
| 5 | No programmatic owner gate for Jarvis Prime actions | Gates exist at skill layer only; no code-level block on destructive actions initiated through the Jarvis surface | MEDIUM |
| 6 | Logistics and Career Strategy specialists referenced in `jarvis-prime-operating-system.md` but not defined anywhere | Activating them produces undefined behavior | LOW-MEDIUM |
| 7 | `skills/` and `personas/` subdirs in aos-enterprise-council empty | Council missing super-specialist procedure layer | LOW |

---

## 7. Load-Bearing Files

These files must not be deleted, renamed, or restructured without an owner-gated plan:

| File | Why Load-Bearing |
|------|-----------------|
| `hermes_cli/main.py` | Sole CLI dispatcher; all entry points resolve here |
| `hermes_cli/__init__.py` | Version string (0.14.0), UTF-8 enforcement |
| `pyproject.toml` | Package name (jarvis-prime), all entry points, dependency pins |
| `uv.lock` | Reproducible installs; supply-chain defense |
| `hermes_state.py` | Session history, memory, tool definitions |
| `hermes_constants.py` | Model catalog, provider endpoints, skills paths |
| `hermes_bootstrap.py` | UTF-8 fix before any imports; critical on Windows |
| `run_agent.py` | Tool-calling loop; `jarvis-agent` entry point |
| `gateway/run.py` | Main gateway process loop |
| `gateway/platform_registry.py` | Platform loader for all messaging surfaces |
| `skills/jarvis-prime/SKILL.md` | Jarvis Prime identity and mode definitions |
| `skills/aos-enterprise-council/operating-registry/registry.json` | Source of truth for active council |
| `skills/aos-enterprise-council/scripts/verify_registry.py` | Registry integrity gate |
| `hermes_cli/terminal_tool.py` | Owner gate approval callbacks |

---

## 8. Tests — Current Coverage

### Tests that exist and are likely to cover Jarvis Prime behavior indirectly:

| Test File / Dir | Relevance |
|-----------------|-----------|
| `tests/cli/test_cli_*.py` | CLI argument parsing; covers `hermes_cli.main` |
| `tests/test_hermes_state.py` (129 KB) | Session and memory state |
| `tests/test_hermes_bootstrap.py` | UTF-8 bootstrap |
| `tests/gateway/test_gateway_*.py` | Gateway process management |
| `tests/skills/` | Skills system discovery and loading |
| `tests/tools/test_model_tools*.py` | Tool system |
| `tests/integration/` | End-to-end integration |

### Tests that do NOT exist but should:

| Missing Test | What It Should Cover |
|-------------|---------------------|
| `tests/test_jarvis_prime_entrypoint.py` | `jarvis-prime --help` resolves; no import error |
| `tests/test_jarvis_prime_classify.py` | `classify` command routes to correct mode |
| `tests/test_jarvis_prime_owner_gates.py` | Owner gate phrase enforcement; blocked actions |
| `tests/test_jarvis_prime_council_routing.py` | AOS council activation from Jarvis surface |
| `tests/test_jarvis_prime_mobile_capture.py` | Short-response enforcement; task packet output |
| `tests/test_jarvis_prime_registry_integrity.py` | Registry verifier passes in CI |

### Tests run this session:

```
python -m pytest tests/test_jarvis_prime_*.py -q  →  NO FILES MATCHED (0 tests collected)
python skills/aos-enterprise-council/scripts/verify_registry.py  →  PASS
```

---

## 9. Owner-Gated Actions — Current State

| Action | Gate Status |
|--------|------------|
| Merging to main | ❌ NO programmatic block; relies on discipline + skill docs |
| Force push | ❌ Same |
| Package publish (PyPI) | ❌ Same |
| Deploy gateway to production | ❌ Same |
| Credential/OAuth changes | ❌ Same |
| App store submissions | ❌ Same |
| AOS registry broad mutation | ❌ Same; `policies.no_more_always_active_agents` is a JSON policy, not a runtime guard |
| Terminal command requiring sudo | ✅ Code gate via `terminal_tool.py` approval callback |
| Owner gate phrase check | ✅ Documented: "Yes, with authorization." |

---

## 10. Files Inspected

```
hermes_cli/main.py
hermes_cli/__init__.py
hermes_cli/gateway.py
hermes_cli/gateway_windows.py
hermes_cli/slack_cli.py
hermes_cli/pairing.py
hermes_cli/auth.py
hermes_cli/commands.py
hermes_cli/terminal_tool.py
hermes_state.py
hermes_constants.py
hermes_bootstrap.py
hermes_logging.py
run_agent.py
pyproject.toml
setup.py
docs/jarvis-prime-operating-system.md
docs/jarvis-verification-gates.md
docs/aos-jarvis-agent-routing.md
docs/jarvis-code-operator-workflow.md
docs/mobile-voice-development-workflow.md
docs/slack-mobile-command-policy.md
docs/memory-and-personality-policy.md
skills/jarvis-prime/SKILL.md
skills/jarvis-code-operator/SKILL.md
skills/mobile-voice-development/SKILL.md
skills/aos-enterprise-council/SKILL.md
skills/aos-enterprise-council/operating-registry/registry.json
skills/aos-enterprise-council/scripts/verify_registry.py
skills/aos-enterprise-council/runnable-agents/*.md (6 files)
skills/aos-enterprise-council/specialists/*.md (8 files)
skills/aos-enterprise-council/workers/*.md (8 files)
agent/process_bootstrap.py
agent/memory_manager.py
agent/prompt_builder.py
gateway/run.py
gateway/platform_registry.py
gateway/session.py
tools/terminal_tool.py
constraints-termux.txt
```

**Not found (expected to exist per audit spec):**
```
hermes_cli/jarvis_prime/    → NOT FOUND
CANONICAL_REPO.md           → NOT FOUND
tests/test_jarvis_prime_*   → NOT FOUND
```

---

## 11. Recommended Wave 1 Branch

**Branch name:** `wave-1/jarvis-prime-native-module`

**Scope:**
1. Create `hermes_cli/jarvis_prime/` as a Python package with `__init__.py`, `classify.py`, and `__main__.py`
2. Wire `jarvis-prime` CLI entry point to a Jarvis-specific dispatcher that delegates to `hermes_cli.main` for all standard commands but adds `capture`, `classify`, and `council` subcommands
3. Create `CANONICAL_REPO.md` at repo root
4. Create `tests/test_jarvis_prime_entrypoint.py` and `tests/test_jarvis_prime_classify.py`
5. Update `docs/aos-jarvis-agent-routing.md` to match the 6-member registry

**Out of scope for Wave 1:**
- Gateway changes
- AOS registry additions (Logistics, Career Strategy)
- Mobile auto-detection
- Owner gate code enforcement
- Merge or publish

**Owner gates required before Wave 1 starts:** None (docs + module scaffold only, no runtime changes that break existing behavior)
