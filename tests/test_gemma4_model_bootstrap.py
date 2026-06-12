"""Gemma 4 — bootstrap recommendation tests (no downloads, no network)."""

from __future__ import annotations

from muse_cli.jarvis_prime import model_bootstrap as mb
from muse_cli.local_models.hardware_probe import HardwareProfile


def test_compute_local_defaults_picks_gemma_for_reasoning() -> None:
    defaults = {d.purpose: d for d in mb.compute_local_defaults()}
    reasoning = defaults["local_reasoning"]
    assert reasoning.model_id == "gemma4"
    assert reasoning.ollama_tag == "gemma4:e4b"


def test_compute_local_defaults_routes_gemma_by_job_weight() -> None:
    """Fast daily → E2B; deeper reasoning → E4B; never 26B/31B as a default.

    (Coding's *defaults-layer* family follows the OSS catalog — a dedicated
    coder may lead — but the router promotes Gemma E4B for coding lanes; that
    is covered in ``test_gemma4_task_router``.)
    """
    defaults = {d.purpose: d for d in mb.compute_local_defaults()}
    # Fast daily driver pins the small E2B.
    assert "local_fast" in defaults
    assert defaults["local_fast"].model_id == "gemma4"
    assert defaults["local_fast"].ollama_tag == "gemma4:e2b"
    # Deeper reasoning uses E4B.
    assert defaults["local_reasoning"].ollama_tag == "gemma4:e4b"
    # 26B / 31B are NEVER emitted as an auto local default.
    tags = {d.ollama_tag for d in defaults.values()}
    assert "gemma4:26b" not in tags
    assert "gemma4:31b" not in tags


def test_gemma_variant_tag_resolves_from_catalog() -> None:
    assert mb._gemma_variant_tag("gemma4-e2b") == "gemma4:e2b"
    assert mb._gemma_variant_tag("gemma4-e4b") == "gemma4:e4b"


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
