"""Slash-command registration for MUSE (B2 from final release review)."""

from __future__ import annotations

from hermes_cli.commands import COMMAND_REGISTRY, resolve_command


def test_jarvis_prime_command_registered() -> None:
    entry = resolve_command("jarvis-prime")
    assert entry is not None
    assert entry.name == "jarvis-prime"
    assert "jarvis" in entry.aliases
    assert "jp" in entry.aliases
    assert entry.category == "Tools & Skills"


def test_aliases_resolve_to_same_canonical() -> None:
    canonical = resolve_command("jarvis-prime")
    assert canonical is not None
    assert resolve_command("jarvis") is canonical
    assert resolve_command("jp") is canonical
    # leading slash and case insensitivity
    assert resolve_command("/JP") is canonical


def test_jarvis_prime_in_registry() -> None:
    names = {c.name for c in COMMAND_REGISTRY}
    assert "jarvis-prime" in names
