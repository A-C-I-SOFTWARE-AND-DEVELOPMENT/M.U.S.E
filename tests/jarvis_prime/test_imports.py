"""Wave 0 import-surface tests for hermes_cli.jarvis_prime."""

import importlib


def test_package_imports_cleanly():
    mod = importlib.import_module("hermes_cli.jarvis_prime")
    assert mod is not None


def test_work_packet_symbols_exported():
    mod = importlib.import_module("hermes_cli.jarvis_prime")
    for name in ("WorkPacket", "WorkPacketValidationFinding", "VALID_RISK_CLASSES"):
        assert hasattr(mod, name), f"hermes_cli.jarvis_prime missing export: {name}"
    assert name in mod.__all__


def test_work_packet_is_dataclass_constructible():
    from hermes_cli.jarvis_prime import WorkPacket

    wp = WorkPacket()
    assert wp.mission == ""
    assert wp.confidence == 0.0


def test_import_does_not_pull_heavy_subsystems():
    """The Wave 0 import surface must stay stdlib-only.

    If a later wave adds heavy imports here, that change should land on
    its own branch with explicit justification — not silently expand the
    foundation.
    """
    import sys

    for name in list(sys.modules):
        if name.startswith("hermes_cli.jarvis_prime"):
            del sys.modules[name]

    before = set(sys.modules)
    importlib.import_module("hermes_cli.jarvis_prime")
    after = set(sys.modules)
    new = after - before

    forbidden_prefixes = (
        "anthropic",
        "openai",
        "httpx",
        "requests",
        "pydantic",
        "rich",
        "prompt_toolkit",
    )
    leaked = sorted(
        m for m in new if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)
    )
    assert not leaked, f"Wave 0 import surface leaked heavy modules: {leaked}"
