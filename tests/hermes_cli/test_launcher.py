"""Tests for the top-level `./hermes` launcher script."""

import runpy
import sys
import types
from pathlib import Path


def test_launcher_delegates_to_argparse_entrypoint(monkeypatch):
    """`./hermes` should use `muse_cli.main`, not the legacy Fire wrapper."""
    launcher_path = Path(__file__).resolve().parents[2] / "hermes"
    called = []

    fake_main_module = types.ModuleType("muse_cli.main")

    def fake_main():
        called.append("muse_cli.main")

    fake_main_module.main = fake_main  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    monkeypatch.setitem(sys.modules, "muse_cli.main", fake_main_module)

    fake_cli_module = types.ModuleType("cli")

    def legacy_cli_main(*args, **kwargs):
        raise AssertionError("launcher should not import cli.main")

    fake_cli_module.main = legacy_cli_main  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    monkeypatch.setitem(sys.modules, "cli", fake_cli_module)

    fake_fire_module = types.ModuleType("fire")

    def legacy_fire(*args, **kwargs):
        raise AssertionError("launcher should not invoke fire.Fire")

    fake_fire_module.Fire = legacy_fire  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    monkeypatch.setitem(sys.modules, "fire", fake_fire_module)

    monkeypatch.setattr(sys, "argv", [str(launcher_path), "gateway", "status"])

    runpy.run_path(str(launcher_path), run_name="__main__")

    assert called == ["muse_cli.main"]
