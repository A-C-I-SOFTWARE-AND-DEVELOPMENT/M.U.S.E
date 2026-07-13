# JARVIS Prime — Mobile-First Architecture

**Date:** 2026-05-25  
**Status:** Architecture document — no runtime code changed  
**Scope:** How Jarvis Prime should function on Termux, Slack mobile, voice capture, and focused desktop follow-up

---

## Premise

Jeremiah operates Jarvis Prime in two distinct physical contexts:

1. **Moving** — jogging, walking, driving, in transit. Phone-first. Quick capture. Short responses. No code review. No diffs. No deploys. Task packets only.
2. **Focused** — desktop, Termux session, VS Code. Full technical depth. Builder mode available. Reviews, diffs, AOS council, code builds.

The runtime must serve both contexts from the same codebase without mode confusion.

---

## Surface Map

```
┌────────────────────────────────────────────────────────────┐
│                    MOVING / MOBILE                         │
│                                                            │
│  Slack DM → jarvis capture / jarvis focused / jarvis build │
│  Termux (Android) → hermes "JARVIS capture: <idea>"        │
│  Voice (dictated) → rough message detected → mobile mode   │
│                                                            │
└────────────────┬───────────────────────────────────────────┘
                 │ Task packet stored
                 ▼
┌────────────────────────────────────────────────────────────┐
│                   FOCUSED / DESKTOP                        │
│                                                            │
│  Termux (session) → hermes "JARVIS focused: <task title>"  │
│  VS Code + Claude Code → full builder mode                 │
│  Desktop Slack → full AOS council review                   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Termux (Android Cockpit)

### Current State

The Hermes runtime runs on Android via Termux. Key facts:

- Python 3.11+ runs natively in Termux
- `constraints-termux.txt` pins packages for Android arm64
- `pyproject.toml` defines `termux` and `termux-all` extras
- Manual install path documented in `SETUP.md` and `README.md`
- No Jarvis Prime–specific launch wrapper; users must type full `cd /data/data/.../hermes-agent && hermes ...`

### Target Architecture

**Alias file: `scripts/install-termux-aliases.sh`**

```bash
#!/data/data/com.termux/files/usr/bin/bash
# Install short Jarvis Prime aliases for Termux mobile use

JP_HOME="/data/data/com.termux/files/home/hermes-agent"

alias jp="cd $JP_HOME && hermes"
alias jpc="jp 'JARVIS capture: '"
alias jpf="jp 'JARVIS focused: '"
alias jps="jp 'JARVIS status'"

echo "JARVIS Prime aliases installed. Use: jp, jpc <idea>, jpf <task>, jps"
```

**Why:**
- Reduces typing from 70+ characters to 3 characters
- Makes Termux the practical mobile command layer
- Short enough to use while briefly stopped during a run

### Termux Command Flow

```
User types: jpc "add verify step to build gate"
    ↓
hermes "JARVIS capture: add verify step to build gate"
    ↓
hermes_cli/main.py → JARVIS Prime skill activation
    ↓
Mobile Voice Mode: capture + clean task title + next action
    ↓
Response ≤6 lines. No code. No diff. Task packet only.
    ↓
Later: jpf "add verify step to build gate" → full expansion
```

---

## Layer 2: Slack (Mobile Command Layer)

### Current State

The Slack gateway is fully wired:
- `hermes_cli/gateway.py` — process management
- `hermes_cli/slack_cli.py` — manifest generator with full OAuth scopes
- `gateway/platforms/` — Slack platform runtime
- Socket mode enabled
- Slash commands: manifest generated but not yet Jarvis Prime–branded

### Target Architecture

**Slack slash commands to register:**

| Command | Action | Max Response |
|---------|--------|-------------|
| `/jarvis capture <idea>` | Mobile Voice Mode — capture + task packet | 6 fields |
| `/jarvis focused <task>` | Expand task into full focused-mode packet | 10 sections |
| `/jarvis build <task>` | Builder Mode — route to code operator | Builder packet |
| `/jarvis critic <topic>` | Critic Mode — challenge with strongest objection | 3–5 bullet points |
| `/jarvis strategy <decision>` | Strategy Mode — tradeoffs + path | 3–5 bullet points |
| `/jarvis council <topic>` | Activate AOS council for judgment | Structured output |
| `/jarvis remember <fact>` | Save durable memory | ACK + memory slug |
| `/jarvis forget <slug>` | Delete memory | ACK |
| `/jarvis correct <memory>` | Correct an existing memory | ACK + updated slug |
| `/jarvis status` | Show gateway status, active model, memory count | Status block |

**Mobile response rules (enforced programmatically, not just by skill):**

```python
MOBILE_SURFACES = {"slack_dm", "slack_mobile", "termux_voice"}
MOBILE_MAX_LINES = 12
MOBILE_MAX_CODE_BLOCKS = 0
MOBILE_MAX_DIFF_SIZE = 0
```

When `surface in MOBILE_SURFACES`, response renderer truncates at `MOBILE_MAX_LINES` and appends: `"[Full expansion available in focused mode: /jarvis focused <task>]"`

### Surface Detection (GAP-011 closure)

```python
# hermes_cli/jarvis_prime/surface_detector.py

def detect_surface(message_metadata: dict) -> str:
    """Return 'mobile', 'termux', or 'desktop'."""
    
    if message_metadata.get("channel_type") == "im":
        # Slack DM → likely mobile
        return "mobile"
    
    if message_metadata.get("source") == "termux":
        return "termux"
    
    msg = message_metadata.get("text", "")
    if len(msg) < 80 and not "\n" in msg:
        # Short, no newlines → likely dictated or thumb-typed
        return "mobile"
    
    return "desktop"
```

---

## Layer 3: Voice Capture Flow

### Problem

Dictated messages are rough. They contain fillers, corrections, double thoughts. Jarvis Prime must:
1. Preserve raw intent exactly
2. Extract the clean task
3. NOT ask for clarification (moving = bad UX)
4. NOT produce long output

### Capture Protocol

```
INPUT (raw voice capture):
  "uhh yeah so I want to add like a verify step maybe to the build gate 
   or something, like before we say it's done you know what I mean"

JARVIS PRIME MOBILE RESPONSE:
  Captured idea: add a verify step to the build gate before marking done
  Clean task title: build-gate-verify-step
  Short summary: Enforce a test/check pass before any build is declared complete
  Recommended agent: jarvis-code-operator
  Recommended worker: claude-code-builder
  Next focused action: jpf "build-gate-verify-step" from desktop
```

**Rules:**
- Never rephrase in a way that loses the core intent
- Never add new requirements not in the raw capture
- Never ask "did you mean X or Y?" while mobile
- Save to memory only if explicitly asked with `/jarvis remember`

---

## Layer 4: Focused Mode Expansion

### When Focused Mode Activates

```
/jarvis focused "build-gate-verify-step"
```

Or from desktop Termux:
```
hermes "JARVIS focused: build-gate-verify-step"
```

### Focused Mode Output Format (10 sections)

```
1. Mission
   Add a verification pass to the build gate before any build is marked complete.

2. Context
   Source: captured during mobile session 2026-05-25
   Repo: hermes-agent
   Branch: to be created (wave-1/build-gate-verify)

3. Assumptions
   - "build gate" means docs/jarvis-verification-gates.md Build Gate section
   - "verify step" means a required test run or py_compile check
   - no runtime code change without owner review

4. Recommended agent / specialist
   JARVIS Code Operator → Claude Code Builder

5. Recommended worker
   Claude Code Builder (primary)
   Codex Reviewer (review after build)

6. Files likely affected
   docs/jarvis-verification-gates.md
   tests/test_jarvis_prime_build_gate.py (new)

7. Acceptance criteria
   - Build Gate section names ≥1 verification command
   - Verification test exists and passes

8. Verification plan
   python -m pytest tests/test_jarvis_prime_build_gate.py -q
   git diff --check

9. Rollback plan
   git revert <commit> — docs change; safe to revert

10. Owner gates
    None required for docs-only change
    Test addition requires no owner gate
```

---

## Layer 5: Mode Switching

Jarvis Prime must not require the user to explicitly declare a mode switch. Mode should be inferred:

| Trigger | Mode |
|---------|------|
| Surface = mobile | Mobile Voice Mode |
| Message is short + no code context | Mobile Voice Mode or Companion Mode |
| Request contains "build", "PR", "code", "test", "branch" | Builder Mode |
| Request contains "audit", "review", "critic", "flaw", "risk" | Critic Mode |
| Request contains "strategy", "roadmap", "business", "investor", "pricing" | Strategy Mode |
| Emotional language, personal context | Companion Mode (first), then route if needed |
| Request contains "council", "AOS", "specialist" | Operator Mode → AOS |

Mode is a soft inference, not a hard lock. Jarvis Prime can blend modes in a single response (e.g., Companion acknowledgment + Operator routing) but must not confuse them.

---

## Layer 6: Memory and Durable State (Mobile-Relevant)

### What Gets Saved on Mobile

Only save when user says "remember" or `/jarvis remember`.

Never auto-save:
- raw voice captures
- temporary emotional states  
- task progress (save task packets, not emotions)
- specific PR numbers or issue numbers (these expire)
- one-off status reports

Always save:
- user corrections to Jarvis behavior
- product direction decisions
- agent routing improvements the user explicitly approved
- lessons learned from failed builds

### Memory Location

```
C:\Users\Echer\.hermes\memories\    (desktop)
/data/data/com.termux/files/home/.hermes/memories/    (Android)
```

Memory syncs via the gateway session context — same memory, different surfaces.

---

## Layer 7: Short-Response Enforcement

### Current State (GAP — not enforced in code)

Mobile response length is currently enforced only by SKILL.md guidelines ("keep responses short while moving"). Nothing in the Python runtime truncates or flags responses as too long for mobile.

### Target: `hermes_cli/jarvis_prime/response_formatter.py`

```python
MAX_MOBILE_LINES = 12
MAX_MOBILE_CODE_BLOCKS = 0
MAX_MOBILE_DIFF_CHARS = 0

def enforce_mobile_limits(response: str, surface: str) -> str:
    if surface not in ("mobile", "termux"):
        return response
    
    lines = response.splitlines()
    if len(lines) > MAX_MOBILE_LINES:
        truncated = "\n".join(lines[:MAX_MOBILE_LINES])
        return truncated + "\n\n[Full response available in focused mode]"
    
    return response
```

---

## Architecture Diagram — Full Stack

```
                    ANDROID / TERMUX
                    ─────────────────
                    Termux terminal
                    jp / jpc / jpf aliases
                           │
                           ▼
              ┌─────────────────────────┐
              │    hermes_cli.main      │
              │    (jarvis-prime CLI)   │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │ hermes_cli.jarvis_prime  │   ← Wave 1: create this module
              │  ├── __main__.py        │
              │  ├── classify.py        │
              │  ├── surface_detector.py│   ← Wave 2
              │  ├── owner_gate.py      │   ← Wave 2
              │  └── response_formatter │   ← Wave 2
              └────────────┬────────────┘
                           │
         ┌─────────────────┼───────────────────┐
         │                 │                   │
         ▼                 ▼                   ▼
  Mobile Voice Mode   Builder Mode        AOS Council
  (capture/format)   (code operator)     (6-member active)
         │                 │                   │
         ▼                 ▼                   ▼
  Task Packet Output  Claude Code Builder  Deliberation Output
                      Codex Reviewer
                      Local Test Runner
                      GitHub PR Publisher

                    SLACK (mobile surface)
                    ──────────────────────
                    /jarvis capture
                    /jarvis focused
                    /jarvis build
                    /jarvis council
                    /jarvis status
                           │
                           ▼
              gateway/platforms/slack.py
              gateway/run.py
              gateway/delivery.py
```

---

## Wave 2 Mobile Work Plan

After Wave 1 creates the module foundation:

1. **Surface detector** — infer mobile vs. desktop from message metadata
2. **Response formatter** — enforce mobile line limits programmatically
3. **Termux alias installer** — `scripts/install-termux-aliases.sh`
4. **Slack slash command registration** — `/jarvis capture`, `/jarvis focused`, `/jarvis status`
5. **Owner gate enforcement at module level** — block destructive actions from mobile surface
6. **Mobile test suite** — `tests/test_jarvis_prime_mobile.py`

All Wave 2 items require owner review before merge. No production gateway changes without Jeremiah's authorization.

---

## Owner Gates for Mobile Work

| Action | Gate Required |
|--------|--------------|
| Register new Slack slash commands | Yes — app manifest change |
| Deploy gateway update | Yes |
| Push Termux install script | No (docs/scripts only) |
| Create `surface_detector.py` | No (new file, not modifying existing behavior) |
| Enable response truncation in production | Yes — changes user-visible output |
| Save memory from mobile surface | User must say "remember" |
| Run deploy or merge from mobile | Never without explicit gate phrase |
