"""Freeze test for the cockpit wire contract (EPIC-COCKPIT-SEAM Phase 0).

Regenerates the contract in-memory from the live route tables (via the
generator's own ``build_contract`` — no subprocess) and asserts it equals the
committed ``docs/contracts/cockpit-wire-contract.json`` /
``.md`` artifacts. Any change to the cockpit wire surface (route added,
removed, re-pathed, re-authed, owner gate moved, handler renamed) fails here
until ``scripts/generate_cockpit_contract.py`` is re-run and the diff is
committed in the same PR.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_cockpit_contract.py"

DRIFT_MESSAGE = (
    "cockpit wire-contract drift — if intentional, regenerate via "
    "scripts/generate_cockpit_contract.py and commit the diff in the same PR"
)


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_cockpit_contract", GENERATOR_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_json_matches_committed() -> None:
    gen = _load_generator()
    regenerated = gen.build_contract()
    committed = json.loads(gen.JSON_PATH.read_text(encoding="utf-8"))
    assert regenerated == committed, DRIFT_MESSAGE


def test_contract_markdown_matches_committed() -> None:
    gen = _load_generator()
    regenerated = gen.render_markdown(gen.build_contract())
    committed = gen.MD_PATH.read_text(encoding="utf-8")
    assert regenerated == committed, DRIFT_MESSAGE


def test_contract_build_is_deterministic() -> None:
    gen = _load_generator()
    first = gen.render_json(gen.build_contract())
    second = gen.render_json(gen.build_contract())
    assert first == second, "build_contract() must be deterministic run-to-run"
