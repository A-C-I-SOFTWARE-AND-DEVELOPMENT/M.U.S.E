"""Unreal Engine 5 automation surface — Remote Control API + gated spawn.

Live control of a running editor goes through UE's Remote Control HTTP
API (default ``127.0.0.1:30010``; enable the *Remote Control API* and
*Python Editor Script* plugins with remote execution ticked):

- ``ping()``      — GET /remote/info
- ``discover()``  — node identity from the same endpoint
- ``console(c)``  — KismetSystemLibrary.ExecuteConsoleCommand
- ``py(script)``  — PythonScriptLibrary.ExecutePythonCommand

Process spawning is owner-gated: ``launch_offscreen_render(...)`` only
calls ``UnrealEditor-Cmd`` when ``muse_UE5_ALLOW_SPAWN=1``; otherwise it
returns the fully built command without touching the system. Network
functions never raise — they return ``{"ok": False, "error": ...}``.

Every action is recorded on the axiom_bridge event chain (``ue5.ping``,
``ue5.console``, ``ue5.py``, ``ue5.render``; python payloads are
recorded as sha256+length, never full scripts).

CLI:
    python -m hermes_cli.jarvis_prime.research_fabric.ue5 ping
    python -m hermes_cli.jarvis_prime.research_fabric.ue5 discover
    python -m hermes_cli.jarvis_prime.research_fabric.ue5 console "stat fps"
    python -m hermes_cli.jarvis_prime.research_fabric.ue5 py "import unreal; unreal.log('muse')"
    python -m hermes_cli.jarvis_prime.research_fabric.ue5 render <project> <map> <sequence>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional, Sequence

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 30010  # Remote Control HTTP
SPAWN_ENV = "muse_UE5_ALLOW_SPAWN"

_KISMET = "/Script/Engine.Default__KismetSystemLibrary"
_PYLIB = "/Engine/PythonTypes.Default__PythonScriptLibrary"


# ----------------------------------------------------------------- recording
def _record(kind: str, payload: dict) -> None:
    """Chain the action via axiom_bridge; soft — never raises."""
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        get_bridge().record_event(kind, payload)
    except Exception:
        pass


# ----------------------------------------------------------------- transport
def _http(method: str, url: str, body: Optional[dict], timeout: float) -> dict:
    """Single urllib seam (tests monkeypatch this). Returns parsed JSON."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — localhost editor API
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def _base(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _call_object(
    object_path: str,
    function_name: str,
    parameters: dict,
    host: str,
    port: int,
    timeout: float,
) -> dict:
    body = {
        "objectPath": object_path,
        "functionName": function_name,
        "parameters": parameters,
        "generateTransaction": False,
    }
    return _http("PUT", f"{_base(host, port)}/remote/object/call", body, timeout)


# ------------------------------------------------------------------- actions
def ping(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0
) -> dict:
    """Is a Remote Control endpoint answering? Never raises."""
    try:
        info = _http("GET", f"{_base(host, port)}/remote/info", None, timeout)
        result = {"ok": True, "info": info, "error": None}
    except Exception as exc:
        result = {"ok": False, "info": None, "error": str(exc)}
    _record("ue5.ping", {"host": host, "port": port, "ok": result["ok"]})
    return result


def discover(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0
) -> dict:
    """Identify the node behind the endpoint; stable fallback id."""
    probe = ping(host, port, timeout)
    if not probe["ok"]:
        return {"ok": False, "node_id": None, "raw": None, "error": probe["error"]}
    info = probe["info"] or {}
    node_id = None
    for key in ("InstanceId", "instanceId", "EngineVersion", "engineVersion"):
        if isinstance(info, dict) and info.get(key):
            node_id = str(info[key])
            break
    if not node_id:
        node_id = hashlib.sha256(f"{host}:{port}".encode("utf-8")).hexdigest()[:12]
    result = {"ok": True, "node_id": node_id, "raw": info, "error": None}
    _record("ue5.discover", {"host": host, "port": port, "node_id": node_id})
    return result


def console(
    cmd: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 5.0,
) -> dict:
    """Run an editor console command (e.g. ``stat fps``). Never raises."""
    try:
        raw = _call_object(
            _KISMET, "ExecuteConsoleCommand", {"Command": cmd}, host, port, timeout
        )
        result = {"ok": True, "raw": raw, "error": None}
    except Exception as exc:
        result = {"ok": False, "raw": None, "error": str(exc)}
    _record("ue5.console", {"command": cmd, "ok": result["ok"]})
    return result


def py(
    script: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 30.0,
) -> dict:
    """Execute Python inside the editor. Never raises."""
    try:
        raw = _call_object(
            _PYLIB, "ExecutePythonCommand", {"PythonCommand": script},
            host, port, timeout,
        )
        result = {"ok": True, "raw": raw, "error": None}
    except Exception as exc:
        result = {"ok": False, "raw": None, "error": str(exc)}
    _record(
        "ue5.py",
        {
            "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
            "script_len": len(script),
            "ok": result["ok"],
        },
    )
    return result


# ------------------------------------------------------- command construction
def build_offscreen_render_args(
    project_file: str,
    map_path: str,
    sequence_path: str,
    *,
    config_asset: Optional[str] = None,
    python_script: Optional[str] = None,
    output_dir: Optional[str] = None,
    offscreen: bool = True,
) -> list[str]:
    """Argv for an ``UnrealEditor-Cmd`` Movie-Render-Queue run."""
    exe = "UnrealEditor-Cmd.exe" if os.name == "nt" else "UnrealEditor-Cmd"
    parts = [exe, project_file, map_path, "-game", f'-LevelSequence="{sequence_path}"']
    if config_asset:
        parts.append(f'-MoviePipelineConfig="{config_asset}"')
    if output_dir:
        parts.append(f'-OutputDirectory="{output_dir}"')
    if offscreen:
        parts.append("-RenderOffscreen")
    if python_script:
        parts.extend(["-ExecutePythonScript", python_script])
    return parts


def build_offscreen_render_command(
    project_file: str,
    map_path: str,
    sequence_path: str,
    *,
    config_asset: Optional[str] = None,
    python_script: Optional[str] = None,
    output_dir: Optional[str] = None,
    offscreen: bool = True,
) -> str:
    """The same command as a single shell-quoted string (string only)."""
    return " ".join(
        shlex.quote(p)
        for p in build_offscreen_render_args(
            project_file,
            map_path,
            sequence_path,
            config_asset=config_asset,
            python_script=python_script,
            output_dir=output_dir,
            offscreen=offscreen,
        )
    )


def remote_control_websocket(host: str = "127.0.0.1", port: int = 30020) -> str:
    return f"ws://{host}:{port}"


def build_prompt_packet(
    prompt: str,
    *,
    modality: str = "text",
    voice: Optional[str] = None,
    style: str = "cinematic",
    no_visible_ui: bool = True,
) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "modality": modality,
        "voice": voice,
        "style": style,
        "no_visible_ui": no_visible_ui,
        "ue5_surface": "background_only",
    }


# --------------------------------------------------------------- gated spawn
def launch_offscreen_render(
    project_file: str,
    map_path: str,
    sequence_path: str,
    *,
    config_asset: Optional[str] = None,
    python_script: Optional[str] = None,
    output_dir: Optional[str] = None,
    offscreen: bool = True,
) -> dict:
    """Spawn the render only when muse_UE5_ALLOW_SPAWN=1 (owner-gated).

    Without the grant: returns the built command and ``spawned: False``
    so callers can show exactly what *would* run.
    """
    args = build_offscreen_render_args(
        project_file,
        map_path,
        sequence_path,
        config_asset=config_asset,
        python_script=python_script,
        output_dir=output_dir,
        offscreen=offscreen,
    )
    command = " ".join(shlex.quote(p) for p in args)
    if os.environ.get(SPAWN_ENV) != "1":
        result = {
            "spawned": False,
            "allowed": False,
            "command": command,
            "reason": f"{SPAWN_ENV} not set (owner-gated)",
        }
        _record("ue5.render", {"command": command, "spawned": False})
        return result
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import _hermes_home

        log_dir = _hermes_home() / "ue5" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"render-{int(time.time())}.log"
        with open(log_path, "ab") as log:
            proc = subprocess.Popen(  # noqa: S603 — owner-gated by SPAWN_ENV
                args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
        result = {
            "spawned": True,
            "allowed": True,
            "command": command,
            "pid": proc.pid,
            "log": str(log_path),
        }
    except Exception as exc:
        result = {
            "spawned": False,
            "allowed": True,
            "command": command,
            "error": str(exc),
        }
    _record(
        "ue5.render",
        {"command": command, "spawned": result["spawned"], "pid": result.get("pid")},
    )
    return result


# ------------------------------------------------------------------------ CLI
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime.research_fabric.ue5",
        description="Drive a running UE5 editor over the Remote Control API.",
    )
    conn = argparse.ArgumentParser(add_help=False)
    conn.add_argument("--host", default=DEFAULT_HOST)
    conn.add_argument("--port", type=int, default=DEFAULT_PORT)
    conn.add_argument("--timeout", type=float, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ping", parents=[conn])
    sub.add_parser("discover", parents=[conn])
    console_p = sub.add_parser("console", parents=[conn])
    console_p.add_argument("cmd")
    py_p = sub.add_parser("py", parents=[conn])
    py_p.add_argument("script", help="python source, or '-' to read stdin")
    render_p = sub.add_parser("render", parents=[conn])
    render_p.add_argument("project_file")
    render_p.add_argument("map_path")
    render_p.add_argument("sequence_path")
    render_p.add_argument("--config-asset")
    render_p.add_argument("--python-script")
    render_p.add_argument("--output-dir")

    args = parser.parse_args(argv)
    kw: dict[str, Any] = {"host": args.host, "port": args.port}
    if args.timeout is not None:
        kw["timeout"] = args.timeout

    if args.command == "ping":
        result = ping(**kw)
    elif args.command == "discover":
        result = discover(**kw)
    elif args.command == "console":
        result = console(args.cmd, **kw)
    elif args.command == "py":
        script = sys.stdin.read() if args.script == "-" else args.script
        result = py(script, **kw)
    elif args.command == "render":
        result = launch_offscreen_render(
            args.project_file,
            args.map_path,
            args.sequence_path,
            config_asset=args.config_asset,
            python_script=args.python_script,
            output_dir=args.output_dir,
        )
    else:
        return 2

    print(json.dumps(result, indent=2))
    ok = result.get("ok", result.get("spawned", result.get("command") is not None))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
