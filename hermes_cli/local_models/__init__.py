"""Local / open-weight model layer for Hermes (Phase 6).

Complements the hosted-provider catalog (`hermes_model_catalog.py`) with the
pieces needed to run models locally and route by measured outcomes:

- :mod:`hardware_probe` — what the box can run (stdlib-only, Termux-safe).
- :mod:`server_adapters` — Ollama / llama.cpp / vLLM / SGLang / OpenAI-compat.
- :mod:`catalog` — open-weight candidate models (license, runtime, RAM/VRAM…).
- :mod:`bootstrap` — tiered plan; downloads only with explicit consent.
- :mod:`scorecards` — pick models by evidence, not hype.

Nothing here downloads on import or normal startup.
"""

from __future__ import annotations

from hermes_cli.local_models.bootstrap import (
    BootstrapItem,
    BootstrapPlan,
    DownloadOutcome,
    execute_bootstrap,
    plan_bootstrap,
    post_download_health_check,
)
from hermes_cli.local_models.catalog import (
    OpenWeightCatalog,
    OpenWeightModel,
    load_open_weight_catalog,
)
from hermes_cli.local_models.hardware_probe import HardwareProfile, probe
from hermes_cli.local_models.scorecards import (
    Scorecard,
    ScorecardSample,
    ScorecardStore,
    aggregate,
    select_model,
)
from hermes_cli.local_models.server_adapters import (
    SUPPORTED_RUNTIMES,
    LaunchPlan,
    ServerAdapter,
    get_adapter,
    installed_runtimes,
)

__all__ = [
    "BootstrapItem",
    "BootstrapPlan",
    "DownloadOutcome",
    "execute_bootstrap",
    "plan_bootstrap",
    "post_download_health_check",
    "OpenWeightCatalog",
    "OpenWeightModel",
    "load_open_weight_catalog",
    "HardwareProfile",
    "probe",
    "Scorecard",
    "ScorecardSample",
    "ScorecardStore",
    "aggregate",
    "select_model",
    "SUPPORTED_RUNTIMES",
    "LaunchPlan",
    "ServerAdapter",
    "get_adapter",
    "installed_runtimes",
]
