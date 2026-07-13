#!/usr/bin/env python3
"""
MUSE Voice - Full Control Server
Complete Hermes/MUSE integration: every feature, every agent, all from voice.
"""

import asyncio
import json
import os
import sys
import subprocess
import tempfile
import uuid
import shutil
import time
import re
import signal
from pathlib import Path
from aiohttp import web, WSMsgType

# ─── Config ──────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 9120
STATIC_DIR = Path(__file__).parent / "static"
AUDIO_CACHE = Path.home() / "AppData" / "Local" / "hermes" / "audio_cache"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

# Concurrency limit for agent processes
MAX_CONCURRENT_AGENTS = 5
_agent_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)

# Track active agent runs
_active_runs = {}

def find_hermes():
    for name in ("hermes", "muse"):
        path = shutil.which(name)
        if path:
            return path
    for base in [
        Path.home() / "AppData" / "Local" / "hermes",
    ]:
        candidate = base / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"
        if candidate.exists():
            return str(candidate)
        candidate = base / "M.U.S.E" / "venv" / "Scripts" / "hermes.exe"
        if candidate.exists():
            return str(candidate)
    return "hermes"

HERMES_BIN = find_hermes()

# ─── Helper: Run Hermes CLI ──────────────────────────────────────────────────

async def run_hermes_cmd(args, timeout=120, stdin_data=None):
    """Run any hermes subcommand and return stdout/stderr/returncode."""
    cmd = [HERMES_BIN] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(
                input=stdin_data.encode() if stdin_data else None
            ),
            timeout=timeout
        )
        return {
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except:
            pass
        return {"stdout": "", "stderr": "Timeout", "returncode": -1, "error": "timeout"}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Hermes not found: {HERMES_BIN}", "returncode": -1, "error": "not_found"}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def health_handler(request):
    """Full system health check — runs all checks concurrently for speed."""
    status_result, gateway_result, dashboard_result = await asyncio.gather(
        run_hermes_cmd(["status"], timeout=15),
        run_hermes_cmd(["gateway", "status"], timeout=10),
        run_hermes_cmd(["dashboard", "--status"], timeout=10),
    )
    return web.json_response({
        "status": "ok",
        "hermes_bin": HERMES_BIN,
        "hermes_available": shutil.which(HERMES_BIN) is not None or os.path.isfile(HERMES_BIN),
        "hermes_status": status_result["stdout"][:500] if status_result["stdout"] else status_result["stderr"][:500],
        "gateway_status": gateway_result["stdout"][:300] if gateway_result["stdout"] else "offline",
        "dashboard_status": dashboard_result["stdout"][:300] if dashboard_result["stdout"] else "stopped",
        "active_runs": len(_active_runs),
        "max_agents": MAX_CONCURRENT_AGENTS,
        "version": "2.0.0",
    })


async def chat_handler(request):
    """
    POST /api/chat — Full agent execution with all tools.
    Body: {"message": "...", "yolo": true, "session": null, "model": null, "toolsets": null}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    message = data.get("message", "").strip()
    if not message:
        return web.json_response({"error": "Empty message"}, status=400)

    yolo = data.get("yolo", True)
    session = data.get("session")
    model = data.get("model")
    toolsets = data.get("toolsets")
    workdir = data.get("workdir")
    skills = data.get("skills")

    cmd = [HERMES_BIN, "-z", message]
    if yolo:
        cmd.append("--yolo")
    if session:
        cmd.extend(["--resume", session])
    if model:
        cmd.extend(["-m", model])
    if toolsets:
        cmd.extend(["-t", toolsets])
    if skills:
        cmd.extend(["--skills", skills])

    env = {**os.environ, "NO_COLOR": "1", "TERM": "dumb"}
    cwd = workdir if workdir else None

    async with _agent_semaphore:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            output = stdout.decode("utf-8", errors="replace").strip()
            err_output = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0 and not output:
                return web.json_response({
                    "error": f"Exit code {proc.returncode}",
                    "stderr": err_output[-2000:] if err_output else "",
                }, status=500)

            return web.json_response({
                "response": output,
                "stderr": err_output[-500:] if err_output else "",
                "returncode": proc.returncode,
            })

        except asyncio.TimeoutError:
            return web.json_response({"error": "Agent timed out (300s)"}, status=504)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)


# ─── WebSocket: Streaming Chat + Agent Monitor ───────────────────────────────

async def ws_handler(request):
    """
    WebSocket /ws — unified channel for:
    - Chat streaming
    - Agent activity events
    - System status updates
    """
    ws = web.WebSocketResponse(max_msg_size=0)
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "error": "Invalid JSON"})
                continue

            msg_type = data.get("type", "message")

            if msg_type == "message":
                await _handle_ws_chat(ws, data)
            elif msg_type == "command":
                await _handle_ws_command(ws, data)
            elif msg_type == "delegate":
                await _handle_ws_delegate(ws, data)
            elif msg_type == "status":
                status = await _get_full_status()
                await ws.send_json({"type": "status", "data": status})

        elif msg.type == WSMsgType.ERROR:
            break

    return ws


async def _handle_ws_chat(ws, data):
    """Handle a chat message via WebSocket with streaming output."""
    message = data.get("text", "").strip()
    if not message:
        return

    yolo = data.get("yolo", True)
    session = data.get("session")
    model = data.get("model")
    toolsets = data.get("toolsets")

    cmd = [HERMES_BIN, "-z", message]
    if yolo:
        cmd.append("--yolo")
    if session:
        cmd.extend(["--resume", session])
    if model:
        cmd.extend(["-m", model])
    if toolsets:
        cmd.extend(["-t", toolsets])

    run_id = str(uuid.uuid4())[:8]
    _active_runs[run_id] = {
        "type": "chat",
        "message": message[:80],
        "started": time.time(),
    }

    await ws.send_json({"type": "thinking", "run_id": run_id})

    try:
        async with _agent_semaphore:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            )

            buffer = ""
            while True:
                chunk = await proc.stdout.read(512)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                buffer += text
                await ws.send_json({"type": "chunk", "text": text, "run_id": run_id})

            await proc.wait()
            full_output = buffer.strip()

            # Capture any stderr
            stderr_data = await proc.stderr.read()
            stderr_text = stderr_data.decode("utf-8", errors="replace").strip()

            await ws.send_json({
                "type": "done",
                "text": full_output,
                "run_id": run_id,
                "stderr": stderr_text[-300:] if stderr_text else "",
            })

    except FileNotFoundError:
        await ws.send_json({"type": "error", "error": f"Hermes not found: {HERMES_BIN}", "run_id": run_id})
    except Exception as e:
        await ws.send_json({"type": "error", "error": str(e), "run_id": run_id})
    finally:
        _active_runs.pop(run_id, None)


async def _handle_ws_command(ws, data):
    """Handle a structured hermes command (not a chat message)."""
    subcommand = data.get("command", "")
    args = data.get("args", [])
    timeout = data.get("timeout", 30)

    if not subcommand:
        await ws.send_json({"type": "error", "error": "No command specified"})
        return

    # Whitelist of allowed subcommands
    ALLOWED = {
        "sessions", "cron", "kanban", "skills", "memory", "tools",
        "models", "config", "gateway", "status", "dashboard",
        "jarvis", "hooks", "webhook", "profile", "plugins",
        "checkpoints", "backup", "logs", "insights", "bundles",
    }

    if subcommand not in ALLOWED:
        await ws.send_json({"type": "error", "error": f"Command '{subcommand}' not allowed"})
        return

    cmd_args = [subcommand] + [str(a) for a in args]
    result = await run_hermes_cmd(cmd_args, timeout=timeout)

    await ws.send_json({
        "type": "command_result",
        "command": subcommand,
        "args": args,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "returncode": result["returncode"],
    })


async def _handle_ws_delegate(ws, data):
    """Delegate a task to a subagent."""
    goal = data.get("goal", "").strip()
    if not goal:
        await ws.send_json({"type": "error", "error": "No goal specified"})
        return

    yolo = data.get("yolo", True)
    toolsets = data.get("toolsets", "")

    # Use hermes -z with delegation instructions
    cmd = [HERMES_BIN, "-z", f"Delegate this task: {goal}"]
    if yolo:
        cmd.append("--yolo")
    if toolsets:
        cmd.extend(["-t", toolsets])

    run_id = str(uuid.uuid4())[:8]
    _active_runs[run_id] = {
        "type": "delegate",
        "goal": goal[:80],
        "started": time.time(),
    }

    await ws.send_json({"type": "delegate_started", "run_id": run_id, "goal": goal})

    try:
        async with _agent_semaphore:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            )

            buffer = ""
            while True:
                chunk = await proc.stdout.read(512)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                buffer += text
                await ws.send_json({"type": "chunk", "text": text, "run_id": run_id})

            await proc.wait()
            await ws.send_json({
                "type": "done",
                "text": buffer.strip(),
                "run_id": run_id,
            })
    except Exception as e:
        await ws.send_json({"type": "error", "error": str(e), "run_id": run_id})
    finally:
        _active_runs.pop(run_id, None)


async def _get_full_status():
    """Gather comprehensive system status."""
    tasks = [
        run_hermes_cmd(["status"], timeout=10),
        run_hermes_cmd(["gateway", "status"], timeout=8),
        run_hermes_cmd(["sessions", "list"], timeout=10),
        run_hermes_cmd(["cron", "list"], timeout=10),
        run_hermes_cmd(["tools", "--summary"], timeout=8),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        "system": results[0].get("stdout", str(results[0])) if isinstance(results[0], dict) else str(results[0]),
        "gateway": results[1].get("stdout", str(results[1])) if isinstance(results[1], dict) else str(results[1]),
        "sessions": results[2].get("stdout", str(results[2])) if isinstance(results[2], dict) else str(results[2]),
        "cron": results[3].get("stdout", str(results[3])) if isinstance(results[3], dict) else str(results[3]),
        "tools": results[4].get("stdout", str(results[4])) if isinstance(results[4], dict) else str(results[4]),
        "active_runs": list(_active_runs.keys()),
    }


# ─── Structured API Endpoints ────────────────────────────────────────────────

async def sessions_handler(request):
    """GET /api/sessions — list sessions."""
    result = await run_hermes_cmd(["sessions", "list"], timeout=15)
    return web.json_response(result)


async def session_stats_handler(request):
    """GET /api/sessions/stats — session store stats."""
    result = await run_hermes_cmd(["sessions", "stats"], timeout=10)
    return web.json_response(result)


async def cron_handler(request):
    """GET /api/cron — list cron jobs."""
    result = await run_hermes_cmd(["cron", "list"], timeout=10)
    return web.json_response(result)


async def cron_create_handler(request):
    """POST /api/cron/create — create a cron job.
    Body: {"prompt": "...", "schedule": "30m", "name": "...", "skills": [...]}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    prompt = data.get("prompt", "").strip()
    schedule = data.get("schedule", "60m").strip()
    name = data.get("name", "").strip()

    if not prompt:
        return web.json_response({"error": "No prompt"}, status=400)

    args = ["cron", "create", "--prompt", prompt, "--schedule", schedule]
    if name:
        args.extend(["--name", name])
    if data.get("skills"):
        args.extend(["--skills", ",".join(data["skills"])])

    result = await run_hermes_cmd(args, timeout=15)
    return web.json_response(result)


async def cron_action_handler(request):
    """POST /api/cron/action — pause/resume/remove/run a cron job.
    Body: {"action": "pause|resume|remove|run", "job_id": "..."}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    action = data.get("action", "")
    job_id = data.get("job_id", "")

    if action not in ("pause", "resume", "remove", "run"):
        return web.json_response({"error": "Invalid action"}, status=400)

    result = await run_hermes_cmd(["cron", action, job_id], timeout=15)
    return web.json_response(result)


async def skills_handler(request):
    """GET /api/skills — list all skills."""
    result = await run_hermes_cmd(["skills", "list"], timeout=10)
    return web.json_response(result)


async def tools_handler(request):
    """GET /api/tools — list all tools and their status."""
    result = await run_hermes_cmd(["tools", "list"], timeout=10)
    return web.json_response(result)


async def tools_toggle_handler(request):
    """POST /api/tools/toggle — enable/disable a tool.
    Body: {"action": "enable|disable", "tool": "..."}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    action = data.get("action", "")
    tool = data.get("tool", "")

    if action not in ("enable", "disable") or not tool:
        return web.json_response({"error": "Invalid action or tool"}, status=400)

    result = await run_hermes_cmd(["tools", action, tool], timeout=10)
    return web.json_response(result)


async def models_handler(request):
    """GET /api/models — extract model info from config."""
    result = await run_hermes_cmd(["config", "show"], timeout=10)
    stdout = result.get("stdout", "")
    # Extract model-related lines from config output
    model_lines = []
    for line in stdout.split("\n"):
        low = line.lower().strip()
        if any(k in low for k in ("model", "provider", "aggregator", "fusion", "fallback")):
            model_lines.append(line.strip())
    return web.json_response({
        "stdout": "\n".join(model_lines) if model_lines else stdout[:600],
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", 0),
    })


async def config_handler(request):
    """GET /api/config — show config, POST /api/config — set config."""
    if request.method == "GET":
        result = await run_hermes_cmd(["config", "show"], timeout=10)
        return web.json_response(result)
    else:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        key = data.get("key", "")
        value = data.get("value", "")
        if not key:
            return web.json_response({"error": "No key"}, status=400)
        result = await run_hermes_cmd(["config", "set", key, str(value)], timeout=10)
        return web.json_response(result)


async def gateway_handler(request):
    """GET /api/gateway — gateway status. POST controls it."""
    if request.method == "GET":
        result = await run_hermes_cmd(["gateway", "status"], timeout=10)
        return web.json_response(result)
    else:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        action = data.get("action", "status")
        if action not in ("start", "stop", "restart", "status", "ensure"):
            return web.json_response({"error": "Invalid action"}, status=400)
        result = await run_hermes_cmd(["gateway", action], timeout=30)
        return web.json_response(result)


async def dashboard_handler(request):
    """GET /api/dashboard — dashboard status. POST controls it."""
    if request.method == "GET":
        result = await run_hermes_cmd(["dashboard", "--status"], timeout=10)
        return web.json_response(result)
    else:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        action = data.get("action", "status")
        if action == "stop":
            result = await run_hermes_cmd(["dashboard", "--stop"], timeout=15)
        elif action == "status":
            result = await run_hermes_cmd(["dashboard", "--status"], timeout=10)
        else:
            return web.json_response({"error": "Invalid action"}, status=400)
        return web.json_response(result)


async def memory_handler(request):
    """GET /api/memory — show memory status."""
    result = await run_hermes_cmd(["memory", "status"], timeout=10)
    return web.json_response(result)


async def status_handler(request):
    """GET /api/status — full hermes status."""
    result = await run_hermes_cmd(["status"], timeout=15)
    return web.json_response(result)


async def logs_handler(request):
    """GET /api/logs?lines=50 — recent logs."""
    lines = request.query.get("lines", "50")
    result = await run_hermes_cmd(["logs", "--lines", str(lines)], timeout=10)
    return web.json_response(result)


async def jarvis_handler(request):
    """POST /api/jarvis — launch or stop jarvis.
    Body: {"action": "launch|stop"}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    action = data.get("action", "launch")
    if action not in ("launch", "stop"):
        return web.json_response({"error": "Invalid action"}, status=400)
    result = await run_hermes_cmd(["jarvis", action], timeout=60)
    return web.json_response(result)


async def profile_handler(request):
    """GET /api/profile — list profiles."""
    result = await run_hermes_cmd(["profile", "list"], timeout=10)
    return web.json_response(result)


async def search_sessions_handler(request):
    """GET /api/sessions/search?q=... — search session history via list + server-side filter."""
    query = request.query.get("q", "").strip().lower()
    if not query:
        return web.json_response({"error": "No query"}, status=400)
    result = await run_hermes_cmd(["sessions", "list"], timeout=15)
    lines = result.get("stdout", "")
    # Filter lines containing the query (case-insensitive)
    matching = [l for l in lines.split("\n") if query in l.lower()]
    return web.json_response({
        "stdout": "\n".join(matching) if matching else f"No sessions matching '{query}'",
        "stderr": "",
        "returncode": 0,
        "query": query,
        "match_count": len(matching),
    })


async def delegate_handler(request):
    """POST /api/delegate — delegate a task to a subagent.
    Body: {"goal": "...", "toolsets": [...], "context": "..."}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    goal = data.get("goal", "").strip()
    if not goal:
        return web.json_response({"error": "No goal"}, status=400)

    toolsets = data.get("toolsets", "")
    yolo = data.get("yolo", True)

    cmd = [HERMES_BIN, "-z", f"Delegate this task using delegate_task: {goal}"]
    if yolo:
        cmd.append("--yolo")
    if toolsets:
        cmd.extend(["-t", toolsets])

    async with _agent_semaphore:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            return web.json_response({
                "response": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip()[-500:],
                "returncode": proc.returncode,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)


async def active_runs_handler(request):
    """GET /api/runs — list active agent runs."""
    runs = []
    for rid, info in _active_runs.items():
        elapsed = time.time() - info.get("started", time.time())
        runs.append({
            "id": rid,
            "type": info.get("type", "unknown"),
            "detail": info.get("message", info.get("goal", ""))[:80],
            "elapsed": round(elapsed, 1),
        })
    return web.json_response({"runs": runs})


# ─── CORS Middleware ─────────────────────────────────────────────────────────

@web.middleware
async def cors_middleware(request, handler):
    """Handle CORS preflight and add headers — replaces catch-all OPTIONS route."""
    if request.method == "OPTIONS":
        return web.Response(status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ─── App Setup ───────────────────────────────────────────────────────────────

def create_app():
    app = web.Application(middlewares=[cors_middleware])

    # Core
    app.router.add_get("/api/health", health_handler)
    app.router.add_post("/api/chat", chat_handler)
    app.router.add_get("/ws", ws_handler)
    app.router.add_post("/api/delegate", delegate_handler)
    app.router.add_get("/api/runs", active_runs_handler)

    # Sessions
    app.router.add_get("/api/sessions", sessions_handler)
    app.router.add_get("/api/sessions/stats", session_stats_handler)
    app.router.add_get("/api/sessions/search", search_sessions_handler)

    # Cron
    app.router.add_get("/api/cron", cron_handler)
    app.router.add_post("/api/cron/create", cron_create_handler)
    app.router.add_post("/api/cron/action", cron_action_handler)

    # Skills
    app.router.add_get("/api/skills", skills_handler)

    # Tools
    app.router.add_get("/api/tools", tools_handler)
    app.router.add_post("/api/tools/toggle", tools_toggle_handler)

    # Models
    app.router.add_get("/api/models", models_handler)

    # Config (GET + POST)
    app.router.add_get("/api/config", config_handler)
    app.router.add_post("/api/config", config_handler)

    # Gateway (GET + POST)
    app.router.add_get("/api/gateway", gateway_handler)
    app.router.add_post("/api/gateway", gateway_handler)

    # Dashboard (GET + POST)
    app.router.add_get("/api/dashboard", dashboard_handler)
    app.router.add_post("/api/dashboard", dashboard_handler)

    # Memory
    app.router.add_get("/api/memory", memory_handler)

    # Status
    app.router.add_get("/api/status", status_handler)

    # Logs
    app.router.add_get("/api/logs", logs_handler)

    # Jarvis
    app.router.add_post("/api/jarvis", jarvis_handler)

    # Profile
    app.router.add_get("/api/profile", profile_handler)

    # Serve index.html for root
    async def index_handler(request):
        return web.FileResponse(STATIC_DIR / "index.html")

    app.router.add_get("/", index_handler)

    # Static files
    if STATIC_DIR.exists():
        app.router.add_static("/static/", STATIC_DIR, show_index=False)

    # CORS middleware — defined at module level, applied in create_app()
    # (See @web.middleware cors_middleware above create_app definition)

    return app


async def main():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)

    print()
    print("  ============================================================")
    print("  |              M.U.S.E Voice — Full Control               |")
    print("  ============================================================")
    print(f"  |  URL:     http://{HOST}:{PORT}{'':<34}|")
    print(f"  |  Hermes:  {HERMES_BIN[:46]:<46}|")
    print(f"  |  Agents:  {MAX_CONCURRENT_AGENTS} max concurrent{'':<33}|")
    print(f"  |  Endpoints: 20+ API routes{'':<35}|")
    print("  ============================================================")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    await site.start()

    if sys.platform == "win32":
        try:
            os.startfile(f"http://{HOST}:{PORT}")
        except Exception:
            pass

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n  Shutting down...")
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Goodbye!")
