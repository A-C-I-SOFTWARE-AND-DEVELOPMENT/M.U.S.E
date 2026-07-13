# M.U.S.E Voice — Full Control

Voice-first AI assistant with complete control over every Hermes/MUSE feature, agent, and capability.

## Quick Start

**Desktop shortcut:** Double-click "MUSE Voice" on your Desktop
**Manual:** Run `start.bat` (Windows) or `bash start.sh` (git-bash)
**URL:** http://127.0.0.1:9120 (opens automatically, use Chrome or Edge)

## What MUSE Voice Can Do

MUSE Voice gives you full voice control over the entire Hermes Agent system. Speak naturally and MUSE executes with all 24 toolsets, all agent capabilities, and all system management features.

### Voice Tab (Primary)
- Tap the orb and speak — MUSE listens, processes, and speaks back
- Full agent execution: terminal, file ops, web search, browser automation, code execution, image gen, delegation
- Streaming responses over WebSocket in real-time
- Three modes: Push-to-Talk, Hold-to-Talk, Always Listening (wake word)
- Text fallback input

### Agents Tab
- **Active Runs** — see what agents are currently working
- **Delegate Task** — dispatch subagents for parallel work
- **Cron Jobs** — view and manage scheduled tasks
- **Recent Sessions** — browse conversation history

### System Tab
- **System Status** — full Hermes status report
- **Gateway** — start/stop/restart messaging gateway
- **Dashboard** — control the web dashboard
- **Tools** — toggle any of the 24 toolsets on/off
- **Models** — view available AI models
- **Memory** — check memory provider status
- **Jarvis** — launch Jarvis or emergency stop
- **Configuration** — view and edit Hermes config

## Voice Commands (Examples)

Just speak naturally — MUSE understands:
- "Give me a system status report"
- "Spawn a subagent to search the web for latest AI news"
- "Check my cron jobs"
- "List my recent sessions"
- "Open a project and start coding"
- "What tools do you have?"
- "Enable the browser toolset"
- "Restart the gateway"
- "Create a cron job that checks my email every 30 minutes"
- "Delegate a task to write a Python script"

## API Endpoints (20+)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Full system health |
| `/api/chat` | POST | Agent execution with all tools |
| `/api/delegate` | POST | Spawn subagent |
| `/api/runs` | GET | Active agent runs |
| `/api/sessions` | GET | Session history |
| `/api/sessions/search` | GET | Search sessions |
| `/api/cron` | GET | List cron jobs |
| `/api/cron/create` | POST | Create cron job |
| `/api/cron/action` | POST | Pause/resume/remove cron |
| `/api/skills` | GET | List skills |
| `/api/tools` | GET | List tools |
| `/api/tools/toggle` | POST | Enable/disable tool |
| `/api/models` | GET | Available models |
| `/api/config` | GET/POST | View/set config |
| `/api/gateway` | GET/POST | Gateway control |
| `/api/dashboard` | GET/POST | Dashboard control |
| `/api/memory` | GET | Memory status |
| `/api/status` | GET | Full Hermes status |
| `/api/logs` | GET | Recent logs |
| `/api/jarvis` | POST | Launch/stop Jarvis |
| `/ws` | WS | Streaming chat + agent events |

## Architecture

```
[Voice] → Web Speech API (STT) → WebSocket → Backend
                                               ↓
                                    hermes -z "message" --yolo
                                    (24 toolsets, all features)
                                               ↓
[Browser TTS] ← Frontend ← WebSocket ← Streaming Response ←─┘
```

The backend (`server.py`) is a full Hermes CLI proxy with:
- 20+ structured API endpoints for every Hermes subsystem
- WebSocket streaming for real-time chat and agent monitoring
- Concurrency limiting (5 max agents)
- Active run tracking
- Full CORS support

## File Structure

```
muse-voice/
├── server.py          # Full Hermes proxy backend (20+ API routes)
├── start.bat          # Windows launcher
├── start.sh           # Bash launcher
├── README.md
└── static/
    ├── index.html     # 3-tab interface (Voice / Agents / System)
    ├── voice.css      # MUSE dark theme
    ├── app.js         # Voice engine + full API integration
    └── geometry.js    # Sacred geometry animated canvas
```

## Dogfood Bug Fixes Applied

1. Infinite STT error loop on mic denial — FIXED (permission flag blocks auto-restart)
2. Audio analyser requesting mic on page load — FIXED (deferred to first user interaction)
3. Broken TTS endpoint — REMOVED (browser TTS used exclusively)

## Requirements

- Hermes/MUSE installed and on PATH
- Chrome or Edge browser (Web Speech API)
- Python 3.11+ with aiohttp (auto-uses Hermes venv)
- Microphone access

Port: 9120 (configurable in server.py)
