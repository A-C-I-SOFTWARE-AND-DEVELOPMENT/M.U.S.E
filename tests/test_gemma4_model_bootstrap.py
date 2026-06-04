"""Gemma 4 — bootstrap recommendation tests (no downloads, no network)."""

from __future__ import annotations

from hermes_cli.jarvis_prime import model_bootstrap as mb
from hermes_cli.local_models.hardware_probe import HardwareProfile


def test_compute_local_defaults_picks_gemma_for_reasoning() -> None:
    defaults = {d.purpose: d for d in mb.compute_local_defaults()}
    reasoning = defaults["local_reasoning"]
    assert reasoning.model_id == "gemma4"
    assert reasoning.ollama_tag == "gemma4:e4b"


def test_gemma_recommendations_are_tier_aware() -> None:
    laptop = [r["name"] for r in mb.gemma_recommendations("laptop")]
    assert laptop and laptop[0] == "gemma4-e2b"
    assert "gemma4-31b" not in laptop and "gemma4-26b-a4b" not in laptop

    workstation = [r["name"] for r in mb.gemma_recommendations("workstation")]
    assert workstation and workstation[0] == "gemma4-26b-a4b"

    server = [r["name"] for r in mb.gemma_recommendations("server")]
    assert server and server[0] == "gemma4-31b"


def test_bootstrap_surfaces_small_gemma_on_laptop_without_downloads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    laptop = HardwareProfile("Linux", "x86_64", 8, 16.0, 0.0, 200.0)
    # No runtimes installed; dry-run; no consent → nothing is pulled.
    result = mb.bootstrap(
        dry_run=True,
        hardware=laptop,
        which=lambda _b: None,
        env={},
        record_memory=False,
    )
    recommended = result.config["routes"]["local_oss"]["recommended_local_models"]
    assert any(name.startswith("gemma4-e") for name in recommended)
    # Consent gate held: no download attempted.
    assert result.config["local"]["downloads_accepted"] is False
    assert all(not o.get("attempted") for o in result.download_outcomes)


def test_bootstrap_recommends_large_gemma_only_on_server(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    server = HardwareProfile("Linux", "x86_64", 64, 256.0, 80.0, 4000.0)
    result = mb.bootstrap(
        dry_run=True, hardware=server, which=lambda _b: None, env={}, record_memory=False
    )
    recommended = set(result.config["routes"]["local_oss"]["recommended_local_models"])
    assert "gemma4-31b" in recommended

    laptop = HardwareProfile("Linux", "x86_64", 8, 16.0, 0.0, 200.0)
    laptop_result = mb.bootstrap(
        dry_run=True, hardware=laptop, which=lambda _b: None, env={}, record_memory=False
    )
    laptop_rec = set(laptop_result.config["routes"]["local_oss"]["recommended_local_models"])
    assert "gemma4-31b" not in laptop_rec
