"""Slash-command registration for MUSE (B2 from final release review)."""

from __future__ import annotations

from hermes_cli.commands import COMMAND_REGISTRY, resolve_command


def test_jarvis_prime_command_registered() -> None:
    entry = resolve_command("jarvis-prime")
    assert entry is not None
    assert entry.name == "jarvis-prime"
    assert "jarvis" in entry.aliases
    assert "jp" in entry.aliases
    assert "muse" in entry.aliases
    assert "m" in entry.aliases
    assert entry.category == "Tools & Skills"


def test_aliases_resolve_to_same_canonical() -> None:
    canonical = resolve_command("jarvis-prime")
    assert canonical is not None
    assert resolve_command("jarvis") is canonical
    assert resolve_command("jp") is canonical
    assert resolve_command("muse") is canonical
    assert resolve_command("m") is canonical
    # leading slash and case insensitivity
    assert resolve_command("/JP") is canonical
    assert resolve_command("/MUSE") is canonical


def test_m_alias_owned_by_jarvis_prime_only() -> None:
    """`/m` must not be claimed by any other registered command."""
    owners = [
        c.name
        for c in COMMAND_REGISTRY
        if c.name in {"m", "muse"} or "m" in c.aliases or "muse" in c.aliases
    ]
    assert owners == ["jarvis-prime"]


def test_jarvis_prime_in_registry() -> None:
    names = {c.name for c in COMMAND_REGISTRY}
    assert "jarvis-prime" in names
