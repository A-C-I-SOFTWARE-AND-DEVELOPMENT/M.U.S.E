"""Emergency-stop primitive for JARVIS Prime (B1 from final release review)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.owner_auth import OwnerAuth
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime


@pytest.fixture
def jp(tmp_path: Path) -> JarvisPrime:
    config = JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        owner_auth=OwnerAuth(),
        proactive_tick_enabled=True,
    )
    return JarvisPrime(config=config)


def test_stop_clears_pending_owner_gates(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("production_deploy", risk_class="RC3", rationale="ship")
    jp.config.owner_auth.request("force_push", risk_class="RC3", rationale="rewrite history")
    assert len(jp.config.owner_auth.pending) == 2

    result = jp.stop()

    assert result["cleared"] == 2
    assert set(result["cleared_actions"]) == {"production_deploy", "force_push"}
    assert jp.config.owner_auth.pending == []


def test_stop_disables_proactive_tick(jp: JarvisPrime) -> None:
    assert jp.config.proactive_tick_enabled is True
    result = jp.stop()
    assert result["tick_disabled"] is True
    assert jp.config.proactive_tick_enabled is False


def test_stop_journals_session_record(jp: JarvisPrime) -> None:
    result = jp.stop(reason="user_panic")
    assert result["reason"] == "user_panic"
    hits = jp.config.memory.recollect("emergency_stop")
    assert any(r.key == "emergency_stop" and r.value == "user_panic" for r in hits)
