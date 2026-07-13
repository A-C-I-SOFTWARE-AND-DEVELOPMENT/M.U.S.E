# JARVIS Prime — Gap Map

**Date:** 2026-05-25  
**Source:** `docs/jarvis-prime-current-state-audit.md`  
**Status:** READ-ONLY — mapping only, no code changed

---

## How to Read This Map

Each gap has:
- **Severity** — CRITICAL / HIGH / MEDIUM / LOW
- **Type** — MISSING (doesn't exist) | STALE (exists but wrong) | PARTIAL (wired but incomplete) | UNWIRED (doc exists, code does not)
- **Wave** — which build wave should close it

---

## CRITICAL Gaps

### GAP-001: No `hermes_cli/jarvis_prime/` Python Module

| Field | Value |
|-------|-------|
| Severity | CRITICAL |
| Type | MISSING |
| Wave | 1 |
| Impact | `python -m hermes_cli.jarvis_prime --help` crashes. `python -m hermes_cli.jarvis_prime classify` crashes. Jarvis Prime has no extensible Python surface. |
| Owner gate required | No |
| Files to create | `hermes_cli/jarvis_prime/__init__.py`, `hermes_cli/jarvis_prime/__main__.py`, `hermes_cli/jarvis_prime/classify.py` |
| Files to extend | `pyproject.toml` (update `jarvis-prime` entry point or leave as-is and add a new `jarvis-prime-native` entry) |
| Acceptance criteria | `python -m hermes_cli.jarvis_prime --help` shows Jarvis Prime usage without error |
| Verification | `python -m hermes_cli.jarvis_prime --help` exits 0; `python -m hermes_cli.jarvis_prime classify "test"` prints a classification |
| Do NOT do | Do not create a parallel hermes_cli clone. Import from `hermes_cli.main` inside the module. |

---

### GAP-002: No `test_jarvis_prime_*.py` Test Suite

| Field | Value |
|-------|-------|
| Severity | CRITICAL |
| Type | MISSING |
| Wave | 1 |
| Impact | Any new Jarvis Prime behavior ships unverified. CI has no signal for regressions. |
| Owner gate required | No |
| Files to create | `tests/test_jarvis_prime_entrypoint.py`, `tests/test_jarvis_prime_classify.py`, `tests/test_jarvis_prime_owner_gates.py`, `tests/test_jarvis_prime_registry_integrity.py` |
| Acceptance criteria | `python -m pytest tests/test_jarvis_prime_*.py -q` collects and passes |
| Verification | Pytest output shows green; no import errors |

---

### GAP-003: No `CANONICAL_REPO.md`

| Field | Value |
|-------|-------|
| Severity | CRITICAL |
| Type | MISSING |
| Wave | 1 |
| Impact | No single authoritative document naming source of truth, load-bearing files, or wave plan. New build contributors operate without a map. |
| Owner gate required | No |
| Files to create | `CANONICAL_REPO.md` (root) |
| Acceptance criteria | File exists; names load-bearing files; names operating registry; names wave plan; names owner gates |
| Verification | `Test-Path CANONICAL_REPO.md` is True |

---

## HIGH Gaps

### GAP-004: `aos-jarvis-agent-routing.md` Defines 9-Member Council; Registry Has 6

| Field | Value |
|-------|-------|
| Severity | HIGH |
| Type | STALE |
| Wave | 1 |
| Impact | Routing decisions made from stale 9-member plan conflict with the verified 6-member operating council. Three extra roles (`claude-code-builder`, `codex-reviewer`, `memory-evidence-curator`) in the doc are workers, not council members. |
| Owner gate required | No |
| Files to edit | `docs/aos-jarvis-agent-routing.md` |
| Changes needed | Remove 3 worker roles from "Default active council" list; add note that workers are separate from council; link to `operating-registry/registry.json` |
| Acceptance criteria | Council member list in routing doc matches `registry.json` active_council array |
| Verification | Manual diff check |

---

### GAP-005: No Programmatic Owner Gate at the Jarvis Prime Layer

| Field | Value |
|-------|-------|
| Severity | HIGH |
| Type | PARTIAL |
| Wave | 2 |
| Impact | Owner gates exist in skill docs and approval callbacks in terminal_tool.py, but there is no Jarvis Prime–level code that blocks owner-gated actions before they reach the terminal tool. A Jarvis skill invocation for a destructive action passes through unchecked at the Python level. |
| Owner gate required | Yes — any change to approval callback behavior requires owner review |
| Files to create | `hermes_cli/jarvis_prime/owner_gate.py` |
| Acceptance criteria | Calling a destructive action via the Jarvis Prime module returns a blocked status with gate phrase when authorization is absent |
| Verification | Unit test: `test_jarvis_prime_owner_gates.py` |

---

### GAP-006: No Jarvis Prime–Specific CLI Subcommands

| Field | Value |
|-------|-------|
| Severity | HIGH |
| Type | MISSING |
| Wave | 1 |
| Impact | `jarvis-prime capture`, `jarvis-prime classify`, `jarvis-prime council` do not exist. All user-facing Jarvis Prime behavior is delivered via SKILL.md interpretation, not via discrete CLI commands. This means Jarvis Prime cannot be scripted from Termux or cron without a full interactive session. |
| Owner gate required | No |
| Files to extend | `hermes_cli/jarvis_prime/__main__.py` (new); `hermes_cli/main.py` (optional hook) |
| Acceptance criteria | `jarvis capture "idea here"` routes to mobile voice mode; `jarvis classify "review this build"` prints a mode classification |
| Verification | Integration test; Termux command works |

---

## MEDIUM Gaps

### GAP-007: Logistics Specialist Referenced in Docs, No Definition File

| Field | Value |
|-------|-------|
| Severity | MEDIUM |
| Type | UNWIRED |
| Wave | 2 |
| Impact | `jarvis-prime-operating-system.md` names a Logistics specialist (trucking, dispatch, fleet, LTL). No `specialists/logistics-domain-specialist.md` exists in aos-enterprise-council. |
| Owner gate required | No |
| Files to create | `skills/aos-enterprise-council/specialists/logistics-domain-specialist.md` |
| Acceptance criteria | File exists with when-to-use, when-not-to-use, inputs, outputs, verification, owner gate |

---

### GAP-008: Career Strategy Specialist Referenced in Docs, No Definition File

| Field | Value |
|-------|-------|
| Severity | MEDIUM |
| Type | UNWIRED |
| Wave | 2 |
| Impact | `jarvis-prime-operating-system.md` names a Career Strategy specialist. No file exists. |
| Owner gate required | No |
| Files to create | `skills/aos-enterprise-council/specialists/career-strategy-specialist.md` |

---

### GAP-009: `skills/` Subdirectory in aos-enterprise-council Is Empty

| Field | Value |
|-------|-------|
| Severity | MEDIUM |
| Type | PARTIAL |
| Wave | 2 |
| Impact | The council architecture reserves a `skills/` subdirectory for super-specialist skills (narrow procedures). README says "not yet populated." Three existing narrow procedures (mobile capture, code operator, JARVIS verification gates) should be referenced or linked here. |
| Owner gate required | No |
| Files to create | `skills/aos-enterprise-council/skills/README.md` with index |

---

### GAP-010: `personas/` and `product-roles/` Subdirectories Are Empty

| Field | Value |
|-------|-------|
| Severity | MEDIUM |
| Type | PARTIAL |
| Wave | 3 |
| Impact | Architecture defines personas and product roles as reference-only lenses. None are populated. Risk is that operators populate them ad hoc and treat them as runnable agents. |
| Owner gate required | No |
| Files to create | Stub files for at least: customer persona, driver persona, founder product role, admin product role |

---

### GAP-011: No Mobile-Surface Auto-Detection

| Field | Value |
|-------|-------|
| Severity | MEDIUM |
| Type | UNWIRED |
| Wave | 2 |
| Impact | `skills/mobile-voice-development/SKILL.md` defines Mobile Voice Mode rules. Runtime has no way to automatically detect that a request came from a voice/phone surface vs. desktop. Mode selection is entirely skill-interpretation-based. |
| Owner gate required | No |
| Files to create | `hermes_cli/jarvis_prime/surface_detector.py` |
| Acceptance criteria | Surface detector infers mobile context from message metadata (Slack DM vs. channel, message length, time, device hint headers) |

---

### GAP-012: No Registry Verifier in CI

| Field | Value |
|-------|-------|
| Severity | MEDIUM |
| Type | PARTIAL |
| Wave | 1 |
| Impact | `verify_registry.py` passes locally but is not wired into `.github/workflows/`. A registry corruption in a PR would not be caught automatically. |
| Owner gate required | No |
| Files to edit | `.github/workflows/*.yml` (add registry verification step) |

---

## LOW Gaps

### GAP-013: Root `AOS_AGENT_REGISTRY_COMPLETE.md` Has No Pointer to Operating Registry

| Field | Value |
|-------|-------|
| Severity | LOW |
| Type | STALE |
| Wave | 1 |
| Impact | Reader finds 233-agent historical registry at root and may treat it as the operating source of truth. |
| Fix | Add a header block to root `AOS_AGENT_REGISTRY_COMPLETE.md`: "This is the historical recovery artifact. The active operating registry is `skills/aos-enterprise-council/operating-registry/registry.json`." |

---

### GAP-014: No Explicit Termux-Native Launch Wrapper

| Field | Value |
|-------|-------|
| Severity | LOW |
| Type | PARTIAL |
| Wave | 2 |
| Impact | Termux users must type a long `cd /data/data/...` prefix. A short `jp` or `jarvis` alias script in `scripts/install-termux-aliases.sh` would improve mobile UX. |

---

### GAP-015: `docs/` Directory Has No Index File

| Field | Value |
|-------|-------|
| Severity | LOW |
| Type | MISSING |
| Wave | 1 |
| Impact | 10+ docs files exist with no `docs/README.md` index. Navigation is by directory listing only. |

---

## Gap Map Summary Table

| ID | Gap | Severity | Type | Wave |
|----|-----|----------|------|------|
| GAP-001 | No `hermes_cli/jarvis_prime/` module | CRITICAL | MISSING | 1 |
| GAP-002 | No `test_jarvis_prime_*.py` suite | CRITICAL | MISSING | 1 |
| GAP-003 | No `CANONICAL_REPO.md` | CRITICAL | MISSING | 1 |
| GAP-004 | Routing doc has stale 9-member council | HIGH | STALE | 1 |
| GAP-005 | No programmatic owner gate | HIGH | PARTIAL | 2 |
| GAP-006 | No Jarvis-specific CLI subcommands | HIGH | MISSING | 1 |
| GAP-007 | Logistics specialist undefined | MEDIUM | UNWIRED | 2 |
| GAP-008 | Career Strategy specialist undefined | MEDIUM | UNWIRED | 2 |
| GAP-009 | `skills/` subdir in council empty | MEDIUM | PARTIAL | 2 |
| GAP-010 | `personas/` and `product-roles/` empty | MEDIUM | PARTIAL | 3 |
| GAP-011 | No mobile surface auto-detection | MEDIUM | UNWIRED | 2 |
| GAP-012 | Registry verifier not in CI | MEDIUM | PARTIAL | 1 |
| GAP-013 | Root historical registry no pointer | LOW | STALE | 1 |
| GAP-014 | No Termux alias wrapper | LOW | PARTIAL | 2 |
| GAP-015 | No `docs/README.md` index | LOW | MISSING | 1 |

---

## Wave 1 Closure Checklist

Wave 1 is complete when all of the following are true:

- [ ] GAP-001: `hermes_cli/jarvis_prime/__main__.py` exists; `python -m hermes_cli.jarvis_prime --help` exits 0
- [ ] GAP-002: `pytest tests/test_jarvis_prime_*.py -q` passes with ≥4 tests collected
- [ ] GAP-003: `CANONICAL_REPO.md` exists at repo root
- [ ] GAP-004: `docs/aos-jarvis-agent-routing.md` council list matches `registry.json`
- [ ] GAP-006: `jarvis classify "review this build"` outputs a mode classification
- [ ] GAP-012: Registry verifier runs in CI
- [ ] GAP-013: Root `AOS_AGENT_REGISTRY_COMPLETE.md` has header pointer
- [ ] GAP-015: `docs/README.md` exists with file index
