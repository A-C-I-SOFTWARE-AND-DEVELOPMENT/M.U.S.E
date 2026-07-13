# JARVIS Prime — Revolutionary Build Plan

**Date:** 2026-05-25  
**Source audit:** `docs/jarvis-prime-current-state-audit.md`  
**Gap map:** `docs/jarvis-prime-gap-map.md`  
**Status:** PLAN ONLY — no code changed  
**Owner gate required to execute:** No (planning is read-only)  
**Owner gate required to merge Wave 1:** Yes, before merging to main

---

## What "Revolutionary" Means Here

Revolutionary does not mean rewrite. The Hermes runtime is production-grade, load-bearing, and should not be touched except at approved extension points.

Revolutionary means:

1. **Jarvis Prime gets a native Python module** — not just a skill manifest
2. **Jarvis Prime gets a test suite** — not just doc gates
3. **Jarvis Prime gets programmatic subcommands** — not just SKILL.md interpretation
4. **The council gets closed gaps** — stale docs corrected, missing specialists added
5. **Mobile surfaces get first-class support** — Termux aliases, Slack commands, short-response enforcement
6. **Every change is verified before claiming done**

This plan is deliberate, not maximalist. It closes the highest-risk gaps without rebuilding what already works.

---

## North Star

When this plan is complete:

```bash
# Works
jarvis-prime --help                           # native help
jarvis classify "review this build"           # returns: Builder Mode
jarvis capture "add verify to build gate"     # returns: 6-field mobile packet
jarvis council "should we add a specialist?"  # routes to AOS council
python -m pytest tests/test_jarvis_prime_*.py -q  # all pass
```

And the repo has:
- `CANONICAL_REPO.md` — single source of truth document
- `hermes_cli/jarvis_prime/` — native Python module
- `tests/test_jarvis_prime_*.py` — test suite with ≥4 files
- `docs/README.md` — docs index
- Registry verifier in CI
- Stale routing doc corrected

---

## Wave Architecture

```
Wave 1: Foundation (module + tests + doc fixes)         [current wave]
Wave 2: Mobile (surface detection + Slack + Termux)
Wave 3: Council Completion (specialists + personas)
Wave 4: Owner Gate Code (programmatic enforcement)
Wave 5: Production Hardening (CI, packaging, distribution)
```

Each wave produces a PR. No wave merges without owner approval. No wave starts until the prior wave's PR is reviewed (or owner explicitly skips review).

---

## Wave 1 — Foundation

**Branch name:** `wave-1/jarvis-prime-native-module`  
**Estimated scope:** 8–12 files created or edited  
**Owner gate to start:** None  
**Owner gate to merge:** Yes

### 1.1 Create `hermes_cli/jarvis_prime/` Module

**New files:**

#### `hermes_cli/jarvis_prime/__init__.py`
```python
"""
JARVIS Prime — native Python module.
Routes jarvis-prime CLI subcommands to the correct mode.
"""

__version__ = "0.1.0"
```

#### `hermes_cli/jarvis_prime/__main__.py`
```python
"""
Entry point for: python -m hermes_cli.jarvis_prime

Subcommands:
  classify <text>   — classify text into JARVIS Prime operating mode
  capture <text>    — mobile voice capture → task packet
  council <topic>   — route topic to AOS council
  status            — show JARVIS Prime runtime status
"""

import sys
from hermes_cli.jarvis_prime.classify import classify_mode
from hermes_cli.jarvis_prime.capture import capture_task

USAGE = """
JARVIS Prime

Usage:
  jarvis classify <text>
  jarvis capture <text>
  jarvis council <topic>
  jarvis status

Options:
  --help    Show this help message
""".strip()


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print(USAGE)
        sys.exit(0)

    command = args[0]
    payload = " ".join(args[1:]) if len(args) > 1 else ""

    if command == "classify":
        result = classify_mode(payload)
        print(result)
    elif command == "capture":
        result = capture_task(payload)
        print(result)
    elif command == "status":
        print("JARVIS Prime v0.1.0 — runtime: hermes_cli.main")
    else:
        print(f"Unknown command: {command}\n\n{USAGE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

#### `hermes_cli/jarvis_prime/classify.py`
```python
"""
classify.py — Route text to the correct JARVIS Prime operating mode.

Modes: companion, strategy, critic, operator, builder, mobile
"""

MODE_KEYWORDS = {
    "builder": [
        "build", "code", "test", "branch", "pr", "pull request",
        "implement", "debug", "diff", "audit", "repo", "module",
        "function", "class", "file", "review this build"
    ],
    "critic": [
        "critic", "audit", "flaw", "risk", "review", "weak", "challenge",
        "objection", "wrong", "bad idea", "problem", "gap"
    ],
    "strategy": [
        "strategy", "roadmap", "business", "investor", "pricing",
        "monetize", "product", "market", "career", "positioning"
    ],
    "operator": [
        "route", "council", "plan", "task", "convert", "coordinate",
        "issue", "ticket", "slack", "termux", "operator"
    ],
    "mobile": [
        "capture", "walking", "jogging", "driving", "moving",
        "short", "later", "remind me", "note this"
    ],
    "companion": [
        "feel", "tired", "stuck", "burned out", "frustrated",
        "help me think", "what do you think", "am i"
    ],
}

PRIORITY = ["mobile", "builder", "critic", "strategy", "operator", "companion"]


def classify_mode(text: str) -> str:
    """Return the most likely JARVIS Prime mode for the given text."""
    text_lower = text.lower()
    scores = {mode: 0 for mode in PRIORITY}

    for mode, keywords in MODE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[mode] += 1

    best_mode = max(PRIORITY, key=lambda m: scores[m])
    best_score = scores[best_mode]

    if best_score == 0:
        best_mode = "operator"

    return f"Mode: {best_mode} (confidence: {'high' if best_score >= 2 else 'low'})"
```

#### `hermes_cli/jarvis_prime/capture.py`
```python
"""
capture.py — Mobile voice capture → 6-field task packet.
"""


def capture_task(text: str) -> str:
    """Convert a rough voice/mobile input into a task packet."""
    if not text.strip():
        return "Error: provide a task description after 'capture'"

    # Clean title: take first meaningful phrase, lowercase, hyphenate
    words = text.strip().lower().split()
    clean_title = "-".join(words[:6])

    output = [
        f"Captured idea:        {text.strip()}",
        f"Clean task title:     {clean_title}",
        f"Short summary:        Review in focused mode",
        f"Recommended agent:    JARVIS Code Operator",
        f"Recommended worker:   Claude Code Builder",
        f"Next focused action:  jarvis focused \"{clean_title}\"",
    ]
    return "\n".join(output)
```

### 1.2 Update `pyproject.toml` Entry Point

Add a direct module entry point so `python -m hermes_cli.jarvis_prime` works:

The module `__main__.py` already handles this. No pyproject.toml change needed for the module invocation. The existing `jarvis-prime = "hermes_cli.main:main"` script entry stays as-is (it runs the full Hermes CLI under the Jarvis name, which is correct for interactive use).

### 1.3 Create `CANONICAL_REPO.md`

**New file at repo root:**

```markdown
# CANONICAL REPO

Repository: A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent  
Package: jarvis-prime v0.14.0  
Runtime: hermes_cli.main  
Date: 2026-05-25

## Source of Truth

| Layer | Source |
|-------|--------|
| Active AOS council | skills/aos-enterprise-council/operating-registry/registry.json |
| CLI entry points | pyproject.toml [project.scripts] |
| JARVIS Prime identity | skills/jarvis-prime/SKILL.md + docs/jarvis-prime-operating-system.md |
| Wave plan | docs/jarvis-prime-revolutionary-build-plan.md |
| Gap map | docs/jarvis-prime-gap-map.md |
| Verification gates | docs/jarvis-verification-gates.md |

## Load-Bearing Files

hermes_cli/main.py — sole CLI dispatcher  
hermes_state.py — session and memory state  
hermes_constants.py — model catalog and paths  
hermes_bootstrap.py — UTF-8 fix before any imports  
run_agent.py — tool-calling loop  
gateway/run.py — gateway process loop  
skills/jarvis-prime/SKILL.md — JARVIS Prime identity  
skills/aos-enterprise-council/operating-registry/registry.json — active council  
pyproject.toml — entry points and dependency pins  
uv.lock — reproducible install

## Owner Gate Phrase

Yes, with authorization.

## Do Not

- Delete recovered sources under skills/aos-enterprise-council/registry/ or recovered-agent-sources/
- Merge to main without owner approval
- Deploy gateway without owner approval
- Publish package without owner approval
- Mutate AOS registry broadly without owner review
- Edit .env or credential files without owner approval
```

### 1.4 Create Test Suite

**New files:**

#### `tests/test_jarvis_prime_entrypoint.py`
Tests: module imports without error; `--help` exit code; `classify` returns expected mode prefix; `capture` returns 6-field packet.

#### `tests/test_jarvis_prime_classify.py`
Tests: "review this build" → builder; "I'm burned out" → companion; "capture jogging idea" → mobile; empty string → operator fallback.

#### `tests/test_jarvis_prime_owner_gates.py`
Tests: owner gate phrase constant matches `registry.json`; gate phrase is present in SKILL.md.

#### `tests/test_jarvis_prime_registry_integrity.py`
Tests: `verify_registry.py` exits 0; registry JSON is valid; active_council has exactly 6 members.

### 1.5 Fix Stale Routing Doc (GAP-004)

**Edit:** `docs/aos-jarvis-agent-routing.md`

Remove from "Default active council":
- `claude-code-builder` (worker, not council)
- `codex-reviewer` (worker, not council)
- `memory-evidence-curator` (specialist, not council)

Add note: "Workers and specialists are separate from the active council. See operating-registry/registry.json for the verified 6-member council."

### 1.6 Add `docs/README.md` Index (GAP-015)

List all docs files with one-line descriptions.

### 1.7 Add Pointer Header to Root Historical Registry (GAP-013)

Edit `AOS_AGENT_REGISTRY_COMPLETE.md` root copy — add a 3-line header at the top:

```
> HISTORICAL RECOVERY ARTIFACT — NOT THE OPERATING REGISTRY
> Active operating registry: skills/aos-enterprise-council/operating-registry/registry.json
> See CANONICAL_REPO.md for source of truth map.
```

### 1.8 Wire Registry Verifier to CI (GAP-012)

Edit `.github/workflows/ci.yml` (or create if missing):

Add step:
```yaml
- name: Verify AOS registry
  run: python skills/aos-enterprise-council/scripts/verify_registry.py
```

### Wave 1 Verification Checklist

Before declaring Wave 1 done, run ALL of these:

```bash
# 1. Module help
python -m hermes_cli.jarvis_prime --help          # must exit 0

# 2. Classify
python -m hermes_cli.jarvis_prime classify "review this build"
# must print: "Mode: builder ..."

# 3. Capture
python -m hermes_cli.jarvis_prime capture "add verify to build gate"
# must print 6-field packet

# 4. Tests
python -m pytest tests/test_jarvis_prime_*.py -q   # must pass, ≥4 tests

# 5. Registry
python skills/aos-enterprise-council/scripts/verify_registry.py
# must print: "AOS registry verification passed."

# 6. Full CLI still works
python -m hermes_cli.main --help                    # must show 40+ subcommands
```

**All must pass before PR is created.**

---

## Wave 2 — Mobile

**Branch name:** `wave-2/jarvis-prime-mobile`  
**Prerequisites:** Wave 1 merged  
**Owner gate to merge:** Yes

### Deliverables

1. `hermes_cli/jarvis_prime/surface_detector.py` — infer mobile vs. desktop
2. `hermes_cli/jarvis_prime/response_formatter.py` — enforce mobile line limits
3. `scripts/install-termux-aliases.sh` — `jp`, `jpc`, `jpf` aliases
4. Slack slash command registration update in manifest
5. `tests/test_jarvis_prime_mobile.py` — mobile surface tests

### Owner Gates for Wave 2

| Action | Gate |
|--------|------|
| Deploy updated Slack manifest | Yes |
| Enable response truncation in production | Yes |
| Push Termux script (docs-only) | No |
| Create surface_detector.py (new file, no runtime change) | No |

---

## Wave 3 — Council Completion

**Branch name:** `wave-3/jarvis-prime-council-completion`  
**Prerequisites:** Wave 1 merged  
**Owner gate to merge:** Yes

### Deliverables

1. `skills/aos-enterprise-council/specialists/logistics-domain-specialist.md`
2. `skills/aos-enterprise-council/specialists/career-strategy-specialist.md`
3. `skills/aos-enterprise-council/skills/README.md` — super-specialist skills index
4. Stub files for personas and product roles
5. Updated `registry.json` with new specialist entries
6. Registry verifier updated to check specialist files exist

---

## Wave 4 — Owner Gate Code

**Branch name:** `wave-4/jarvis-prime-owner-gates`  
**Prerequisites:** Wave 1 merged  
**Owner gate to start:** Yes (this wave modifies approval callback behavior)

### Deliverables

1. `hermes_cli/jarvis_prime/owner_gate.py` — gate check module
2. Integration with `hermes_cli/terminal_tool.py` approval callback
3. Gate logging: every blocked action logged with timestamp, surface, reason
4. `tests/test_jarvis_prime_owner_gates.py` extended with code-level tests

---

## Wave 5 — Production Hardening

**Branch name:** `wave-5/jarvis-prime-hardening`  
**Prerequisites:** Waves 1–4 merged  
**Owner gate to merge:** Yes

### Deliverables

1. CI pipeline complete (all tests, registry verifier, lint, import checks)
2. PyPI release process documented (not published without owner auth)
3. Termux distribution path validated on Android
4. Windows Scheduled Task gateway install verified
5. Full `docs/README.md` finalized with all docs cross-referenced

---

## What This Plan Does NOT Do

- Does not rebuild Hermes from scratch
- Does not replace `hermes_cli.main`
- Does not create a competing agent registry
- Does not activate all 233 recovered agents
- Does not publish to PyPI (requires explicit owner gate)
- Does not merge without owner approval
- Does not deploy gateway changes without owner approval
- Does not add outside software names to user-facing product language

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Wave 1 module breaks existing `hermes_cli.main` import chain | Module is additive; imports nothing at load time; uses `__main__.py` pattern |
| Tests fail because hermes runtime is not importable in test env | Use `python -c "import hermes_cli"` check in test setup; skip integration tests if env not ready |
| Registry verifier in CI fails for environment reasons | Make CI step non-blocking in Wave 1; make blocking in Wave 2 after stability confirmed |
| Stale routing doc update causes confusion | Doc edit is low-risk; routing doc is reference, not code |
| Wave 2 Slack manifest change breaks existing Slack bot | Test manifest in staging workspace before applying to production |
| Owner gate code change (Wave 4) blocks valid actions | Gate logs must be verbose; rollback plan is to disable gate module |

---

## First PR Plan (Wave 1)

**PR title:** `wave-1: JARVIS Prime native module, test suite, and doc foundations`

**Files changed:**
```
hermes_cli/jarvis_prime/__init__.py           (new)
hermes_cli/jarvis_prime/__main__.py           (new)
hermes_cli/jarvis_prime/classify.py           (new)
hermes_cli/jarvis_prime/capture.py            (new)
tests/test_jarvis_prime_entrypoint.py         (new)
tests/test_jarvis_prime_classify.py           (new)
tests/test_jarvis_prime_owner_gates.py        (new)
tests/test_jarvis_prime_registry_integrity.py (new)
CANONICAL_REPO.md                             (new)
docs/README.md                                (new)
docs/aos-jarvis-agent-routing.md              (edit — remove stale council members)
AOS_AGENT_REGISTRY_COMPLETE.md               (edit — add 3-line pointer header)
.github/workflows/ci.yml                      (edit — add registry verifier step)
```

**Non-goals for this PR:**
- No gateway changes
- No Slack manifest changes
- No runtime behavior changes to existing Hermes commands
- No merge to main without Jeremiah's review

**Rollback plan:**
- All new files can be deleted cleanly
- Doc edits can be reverted with `git revert`
- No runtime changes to reverse

**Owner gates used in this PR:** None required. All changes are additive or doc-level.
