"""MUSE wrapper around Karpathy's autoresearch engine (vendored, MIT).

``vendor/`` holds the byte-identical upstream payload (see ``VENDOR.md`` and
``checksums.json``) — data, never imported. The MUSE-side modules are exposed
lazily (PEP 562) so importing this package is cheap and torch-free; torch is
only ever imported inside functions, on owner GPU hardware, behind the
``MUSE_AUTORESEARCH_ALLOW_SPAWN`` gate.

NOTE: this package is intentionally NOT registered in
``research_fabric/__init__.py`` (which imports submodules eagerly) — import it
by full path: ``hermes_cli.jarvis_prime.research_fabric.autoresearch``.
"""

from __future__ import annotations

from typing import Any

_LAZY = {
    # engine
    "ExperimentConfig": "engine",
    "ExperimentResult": "engine",
    "AutoresearchRun": "engine",
    "bpb_gate_score": "engine",
    "gate_margin_for_bpb_delta": "engine",
    "parse_summary": "engine",
    "seed_workspace": "engine",
    "run_single_experiment": "engine",
    "run_experiment_loop": "engine",
    # platform shim
    "DeviceProfile": "platform",
    "detect": "platform",
    "honest_mfu": "platform",
    "default_vram_budget_mb": "platform",
    "H100_BF16_PEAK_FLOPS": "platform",
    # ideas (default edit providers)
    "KnobIdea": "ideas",
    "DEFAULT_IDEAS": "ideas",
    "CatalogEditProvider": "ideas",
    "LlmEditProvider": "ideas",
    "ChainEditProvider": "ideas",
    "default_edit_provider": "ideas",
    # swarm
    "LaneSpec": "swarm",
    "LaneAssignment": "swarm",
    "SwarmPlan": "swarm",
    "SwarmOutcome": "swarm",
    "plan_swarm": "swarm",
    "run_swarm": "swarm",
}

__all__ = sorted(_LAZY)


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f".{module_name}", __name__)
    return getattr(module, name)
