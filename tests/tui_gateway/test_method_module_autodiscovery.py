"""The ``methods_*`` walk must be a drop-in for the old hardcoded tuples.

server.py used to name each handler family twice — an import tuple and a
registration tuple.  ``tui_gateway.method_modules`` replaces both with a
``pkgutil`` walk.  These tests pin the three things that made the swap safe:

* the walk finds exactly the families the tuples named,
* it registers the same method-name set (so no RPC method silently vanished),
* one broken family is logged and skipped instead of taking the gateway down.
"""

from __future__ import annotations

import importlib
import logging
import types

import pytest

from tui_gateway import method_modules, server

# The exact tuple server.py hardcoded before the walk replaced it. Kept
# verbatim as the oracle: if a new methods_* file lands, this list must grow
# deliberately, not by accident.
LEGACY_METHOD_MODULES = (
    "methods_complete",
    "methods_config",
    "methods_images",
    "methods_profiles",
    "methods_prompt",
    "methods_session",
    "methods_tools",
)


def _declared_names(module_name: str) -> list[str]:
    """Method names a family declares, read off its deferred HandlerRegistry."""
    module = importlib.import_module(f"tui_gateway.{module_name}")
    return [name for name, _fn in module._registry._pending]


def test_walk_finds_every_legacy_method_module():
    assert method_modules.discover_method_modules() == sorted(LEGACY_METHOD_MODULES)


def test_walk_order_is_sorted_not_filesystem_order():
    found = method_modules.discover_method_modules()
    assert found == sorted(found)


def test_registered_method_names_match_the_legacy_tuple():
    """The walk must register the same method-name SET as the old tuple."""
    legacy = {name for mod in LEGACY_METHOD_MODULES for name in _declared_names(mod)}
    walked = {
        name
        for mod in method_modules.discover_method_modules()
        for name in _declared_names(mod)
    }

    assert walked == legacy
    # ...and every one of them actually reached the live server registry.
    assert legacy <= set(server._methods)


def test_family_method_names_are_unique_so_order_cannot_matter():
    """Install order is only irrelevant while no two families share a name."""
    seen: dict[str, str] = {}
    clashes: list[str] = []

    for mod in method_modules.discover_method_modules():
        for name in _declared_names(mod):
            if name in seen:
                clashes.append(f"{name}: {seen[name]} vs {mod}")
            seen[name] = mod

    assert not clashes, f"duplicate method names across families: {clashes}"


def _stub_server() -> types.SimpleNamespace:
    return types.SimpleNamespace(_methods={}, _profile_scoped=lambda fn: fn)


def test_install_returns_modules_in_sorted_order():
    stub = _stub_server()
    installed = method_modules.install_method_modules(stub)

    assert installed == sorted(LEGACY_METHOD_MODULES)
    assert set(stub._methods) == {
        name for mod in LEGACY_METHOD_MODULES for name in _declared_names(mod)
    }


def test_a_broken_family_is_logged_and_skipped(monkeypatch, caplog):
    """A family that fails to import must not take the other six down."""
    real_import = importlib.import_module

    def exploding_import(name, package=None):
        if name == ".methods_tools":
            raise ImportError("boom")
        return real_import(name, package)

    monkeypatch.setattr(method_modules.importlib, "import_module", exploding_import)

    stub = _stub_server()
    with caplog.at_level(logging.ERROR, logger=method_modules.logger.name):
        installed = method_modules.install_method_modules(stub)

    assert "methods_tools" not in installed
    assert installed == sorted(set(LEGACY_METHOD_MODULES) - {"methods_tools"})
    assert any("methods_tools" in rec.message for rec in caplog.records)
    # The surviving families still registered their handlers.
    assert set(stub._methods) >= set(_declared_names("methods_session"))


def test_family_without_register_is_skipped(monkeypatch, caplog):
    real_import = importlib.import_module

    def register_less_import(name, package=None):
        if name == ".methods_images":
            return types.SimpleNamespace()
        return real_import(name, package)

    monkeypatch.setattr(method_modules.importlib, "import_module", register_less_import)

    stub = _stub_server()
    with caplog.at_level(logging.WARNING, logger=method_modules.logger.name):
        installed = method_modules.install_method_modules(stub)

    assert "methods_images" not in installed
    assert any("methods_images" in rec.message for rec in caplog.records)


@pytest.mark.parametrize("module_name", LEGACY_METHOD_MODULES)
def test_every_family_exposes_register(module_name):
    module = importlib.import_module(f"tui_gateway.{module_name}")
    assert callable(getattr(module, "register", None))
