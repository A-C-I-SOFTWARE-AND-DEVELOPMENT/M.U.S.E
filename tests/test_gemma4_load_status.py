"""Gemma 4 — persisted load-status store + router gate (no Ollama, no network)."""

from __future__ import annotations

from hermes_cli.jarvis_prime import gemma_load_status as gls


def test_canonical_variant_normalises_spellings() -> None:
    assert gls.canonical_variant("gemma4-e4b") == "gemma4-e4b"
    assert gls.canonical_variant("gemma4:e4b") == "gemma4-e4b"
    assert gls.canonical_variant("ollama-local/gemma4-e2b") == "gemma4-e2b"
    assert gls.canonical_variant("gemma4:26b") == "gemma4-26b"


def test_record_and_load_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Unknown before any record.
    assert gls.load_status() == {}
    assert gls.variant_status("gemma4-e4b") is None
    assert gls.variant_failed("gemma4-e4b") is False  # unknown ≠ failed

    path = gls.record_status("gemma4-e4b", ok=True, detail="completion ok")
    assert path.is_file()
    assert path.stat().st_mode & 0o777 == 0o600
    assert gls.variant_status("gemma4-e4b") == gls.STATUS_OK
    assert gls.variant_failed("gemma4-e4b") is False


def test_failed_status_is_the_only_downgrade_signal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    gls.record_status("gemma4-e4b", ok=False, detail="OOM on 8GB")
    assert gls.variant_status("gemma4-e4b") == gls.STATUS_FAILED
    assert gls.variant_failed("gemma4-e4b") is True
    # Spelling-insensitive read.
    assert gls.variant_failed("gemma4:e4b") is True
    # A later clean smoke clears the downgrade.
    gls.record_status("gemma4-e4b", ok=True)
    assert gls.variant_failed("gemma4-e4b") is False


def test_load_is_defensive_on_garbage(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    target = gls.status_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not json{", encoding="utf-8")
    assert gls.load_status() == {}  # degrades, never raises
