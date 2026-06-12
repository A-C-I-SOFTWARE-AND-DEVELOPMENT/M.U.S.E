"""Compat shim — the implementation moved to ``research_fabric/ue5.py``.

This module kept only the original dependency-free builders; the live
Remote Control client and the owner-gated spawn live in ``ue5``.
"""

from muse_cli.jarvis_prime.research_fabric.ue5 import (
    build_offscreen_render_command,
    build_prompt_packet,
    remote_control_websocket,
)

__all__ = [
    "build_offscreen_render_command",
    "remote_control_websocket",
    "build_prompt_packet",
]
