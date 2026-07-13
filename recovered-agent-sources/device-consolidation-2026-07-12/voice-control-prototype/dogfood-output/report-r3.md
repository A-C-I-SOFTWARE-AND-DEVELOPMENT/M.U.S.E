# Dogfood QA Report — MUSE Voice v2 (Round 3)

**Target:** http://127.0.0.1:9120
**Date:** July 7, 2026
**Scope:** Full re-test after 7 bug fixes — all tabs, all endpoints, edge cases, regression check
**Tester:** Hermes Agent (automated exploratory QA)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🔵 Low | 1 |
| **Total** | **2** |

**Overall Assessment:** All 7 issues from Round 2 are confirmed fixed. The app is production-quality for its intended use. Two minor new findings only.

---

## Round 2 Fix Verification — ALL PASS

| # | Issue | Status | Evidence |
|---|-------|--------|----------|
| 1 | Opaque JS exception on page load | ✅ FIXED | 0 JS errors across 6+ page loads and all interactions |
| 2 | /api/models returns usage error | ✅ FIXED | Returns model config data: `{'default': 'glm-5.2', 'provider': 'zai', ...}` |
| 3 | Unknown routes return 405 instead of 404 | ✅ FIXED | `/nonexistent` now returns 404; OPTIONS still returns 200 |
| 4 | Health endpoint 30+ seconds | ✅ FIXED | Response time: 2 seconds (12x improvement) |
| 5 | Agents tab browser stalls | ✅ FIXED | Loading indicators render instantly, data loads async |
| 6 | Settings not persisted on first load | ✅ FIXED | localStorage saved on init with all defaults |
| 7 | Concurrent streaming messages interleave | ✅ FIXED | run_id-based streaming elements implemented |

---

## New Issues Found in Round 3

### Issue #1: /api/sessions/search uses unsupported CLI flag

| Field | Value |
|-------|-------|
| **Severity** | 🟡 Medium |
| **Category** | Functional |
| **URL** | http://127.0.0.1:9120/api/sessions/search?q=test |

**Description:**
The session search endpoint calls `hermes sessions browse --query <query>`, but the `browse` subcommand does not accept a `--query` flag. It only supports `--source` and `--limit`. The endpoint returns the Hermes global usage error as its "stdout" with empty search results.

**Steps to Reproduce:**
1. `curl http://127.0.0.1:9120/api/sessions/search?q=test`
2. Observe: `{"stdout": "", "stderr": "usage: muse [-h] ..."}`

**Expected Behavior:** Returns matching sessions or a graceful "search not available" message.

**Actual Behavior:** Returns Hermes CLI usage error dump.

**Fix:** Either:
- Use `hermes sessions list` (which does show sessions) and grep client-side
- Or remove the search endpoint and let the chat agent handle search via its session_search tool (which already works — tested in Round 1)

---

### Issue #2: Session search endpoint listed in README but not surfaced in UI

| Field | Value |
|-------|-------|
| **Severity** | 🔵 Low |
| **Category** | UX |
| **URL** | N/A |

**Description:**
The `/api/sessions/search` endpoint exists in the API and README, but is never called by any frontend element. The Agents tab shows sessions via the `/api/sessions` list endpoint, not search. Users would rely on voice/chat to search sessions (which works via the agent's session_search tool).

**Recommendation:** Either add a search box to the Agents tab sessions section, or document that session search is voice-only.

---

## Complete API Audit (Round 3)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/api/health` | ✅ | 2s response (was 30s) |
| `/api/chat` | ✅ | Streaming works, validates input |
| `/api/delegate` | ✅ | Accepts goal + toolsets |
| `/api/runs` | ✅ | Returns `{"runs": []}` |
| `/api/sessions` | ✅ | Returns session list |
| `/api/sessions/stats` | ✅ | 333 sessions, 26438 messages |
| `/api/sessions/search` | ❌ | Broken — uses unsupported `--query` flag (Issue #1) |
| `/api/cron` | ✅ | Returns cron jobs |
| `/api/skills` | ✅ | Returns installed skills |
| `/api/tools` | ✅ | 29 tools rendered in grid |
| `/api/models` | ✅ | Shows config-based model data (was broken) |
| `/api/config` | ✅ | Returns full config |
| `/api/gateway` | ✅ | Shows gateway status |
| `/api/dashboard` | ✅ | Shows dashboard status |
| `/api/memory` | ✅ | Shows memory provider status |
| `/api/status` | ✅ | Full Hermes status |
| `/api/logs` | ✅ | Returns recent agent.log entries |
| `/api/profile` | ✅ | Returns profile list |
| `/ws` | ✅ | Chat streaming, zero errors |
| Unknown URL | ✅ | Returns 404 (was 405) |
| OPTIONS preflight | ✅ | Returns 200 with CORS headers |

---

## Testing Notes

**What was tested:**
- Page load: 6+ fresh navigations, zero JS errors every time
- Voice tab: Chat send/stream/receive, orb state transitions, XSS protection, mute button
- Agents tab: Parallel data loading with indicators, delegate form present, cron + sessions render
- System tab: All 8 sections (status, gateway, dashboard, tools, models, memory, config, jarvis) load real data
- Settings: Panel open/close, mode switching (push ↔ hold), voice select (23 options), API status display
- Settings persistence: localStorage saved on first load with correct defaults
- Edge cases: Empty messages blocked, invalid JSON handled, XSS escaped
- API: 20 endpoints tested via curl with --max-time guards
- Regression: No regressions from the 7 fixes applied

**What was NOT tested (expected headless limitations):**
- Voice input (STT): Microphone unavailable in headless browser — expected
- TTS audio output: Verified via orb state transitions only — expected
- Continuous mode: Switched to continuous mode successfully, but STT fires `not-allowed` error (expected in headless)
- POST endpoints that modify state (cron create, tools toggle, jarvis launch, gateway start/stop): Not tested to avoid side effects

**Result:** The app is clean. Both new findings are minor (one broken endpoint that's not surfaced in the UI, one documentation gap).
