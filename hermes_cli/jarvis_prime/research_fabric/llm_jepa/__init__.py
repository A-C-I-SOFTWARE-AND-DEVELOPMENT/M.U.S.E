"""muse LLM-JEPA fine-tuning engine (sibling of the autoresearch engine).

LLM-JEPA (Huang, LeCun & Balestriero, arXiv 2509.14252) adds a JEPA term to the
standard next-token loss, treating ``(text, code)`` as two views of the same
knowledge::

    L = L_LLM + lambda * d(Pred(Enc(text)), Enc(code))

This package is the muse integration of that *objective* (Phase 2 / Option D of
the JEPA plan). It is a **sibling** of the autoresearch engine and follows the
same conventions:

* ``vendor/`` holds the training harness treated as inert, do-not-edit data
  (see ``VENDOR.md`` and ``checksums.json``); it is never imported by muse code
  or tests and is mutated only inside disposable workspaces under
  ``$HERMES_HOME/llm_jepa/workspaces/<tag>/``.
* The muse-side modules (``engine.py``, ``views.py``) are exposed lazily
  (PEP 562) so importing this package is cheap and **torch-free** — torch is
  only imported inside the vendored ``train.py`` run in a workspace, on owner
  hardware, behind the ``MUSE_LLM_JEPA_ALLOW_SPAWN`` gate.

Like autoresearch, this package is intentionally NOT registered in
``research_fabric/__init__.py`` (which imports submodules eagerly) — import it
by full path: ``hermes_cli.jarvis_prime.research_fabric.llm_jepa``.
"""

from __future__ import annotations

from typing import Any

_LAZY = {
    # engine
    "JepaFinetuneConfig": "engine",
    "JepaFinetuneResult": "engine",
    "jepa_gate_score": "engine",
    "parse_summary": "engine",
    "plan_finetune": "engine",
    "seed_workspace": "engine",
    "run_finetune": "engine",
    "evaluate_finetune": "engine",
    "propose_promotion": "engine",
    "VENDOR_DIR": "engine",
    # two-view builder
    "TwoView": "views",
    "build_views": "views",
    "from_git_log": "views",
    "from_flywheel": "views",
    "views_to_jsonl": "views",
    "views_from_jsonl": "views",
}

__all__ = sorted(_LAZY)


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f".{module_name}", __name__)
    return getattr(module, name)
