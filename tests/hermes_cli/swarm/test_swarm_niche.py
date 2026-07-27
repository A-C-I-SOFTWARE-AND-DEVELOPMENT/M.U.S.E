"""Smoke / unit coverage for run_swarm_niche + Scout integration."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.swarm.coordinator import (
    SwarmGrainResult,
    run_swarm_niche,
)
from hermes_cli.swarm.grain import SwarmPlan
from hermes_cli.swarm.specialist import GrainAgentSpec


class _FakeExecutor:
    """Skip git worktrees — only verifies Scout injection happened."""

    def run(self, repo: Path, plan: SwarmPlan, specs: dict[str, GrainAgentSpec]):
        # Scout must have annotated system prompts / context
        for spec in specs.values():
            assert "SCOUT/" in (spec.context or "") or "Scout prefetch" in (spec.context or "")
            assert "Prefer SCOUT" in (spec.system_prompt or "")
        return [
            SwarmGrainResult(grain_id=g.grain_id, state="succeeded")
            for g in plan.grains
        ]


def test_run_swarm_niche_scout_prompt_only(tmp_path: Path):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "beta" / "b.py").write_text("print('b')\n", encoding="utf-8")

    grains = [
        {
            "grain_id": "g-alpha",
            "intent": "touch alpha module for flaky pytest",
            "globs": ("alpha/**",),
        },
        {
            "grain_id": "g-beta",
            "intent": "touch beta module for security injection",
            "globs": ("beta/**",),
        },
    ]
    result = run_swarm_niche(
        "stabilize flaky pytest and review security injection",
        tmp_path,
        grains=grains,
        executor=_FakeExecutor(),
        claim_domains=False,
        apply_reversible=False,
    )
    assert result.scout_packets > 0
    assert len(result.grains) == 2
    assert any("scout:" in n for n in result.notes)
    assert isinstance(result.niches_used, list)
    assert result.ledger_path
    ledger_text = Path(result.ledger_path).read_text(encoding="utf-8")
    assert "Scout packet" in ledger_text or "scout" in ledger_text.lower()
    if result.niches_used:
        assert any(nid in ledger_text for nid in result.niches_used)


def test_muse_local_executor_constructs_with_kwargs():
    """AIAgentExecutor must be built from config fields, not the config object."""
    from hermes_cli.swarm.ai_executor import AIAgentExecutor
    from hermes_cli.swarm.coordinator import muse_local_executor_config

    cfg = muse_local_executor_config()
    ex = AIAgentExecutor(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=cfg.model,
        provider=cfg.provider,
        max_iterations=cfg.max_iterations,
        concurrency=cfg.concurrency,
        quiet_mode=cfg.quiet_mode,
    )
    assert ex.config.base_url.endswith("/v1")
