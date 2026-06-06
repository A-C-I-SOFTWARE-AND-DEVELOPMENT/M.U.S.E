"""Offscreen Unreal Engine bridge — a safe, dependency-free stub.

The original design called for a hidden/background UE5 rendering bridge for
multimodal generation. This module only *builds command strings and prompt
packets*; it never launches a process, touches the network, or assumes UE is
installed. Real rendering is intentionally out of scope for the safety substrate
and must be smoke-tested on the target platform before use.
"""

from __future__ import annotations

import os
import shlex
from typing import Any, Optional


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
    """Build an ``UnrealEditor-Cmd`` Movie-Render-Queue command line (string only)."""

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
    return " ".join(shlex.quote(p) for p in parts)


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


__all__ = [
    "build_offscreen_render_command",
    "remote_control_websocket",
    "build_prompt_packet",
]
