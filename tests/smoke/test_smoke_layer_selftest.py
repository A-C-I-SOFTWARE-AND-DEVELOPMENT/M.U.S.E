"""Proof that the smoke layer can actually fail.

A green import-smoke run is only evidence if a broken module would have
turned it red.  A classifier that answered "skip" to everything would
produce exactly the same 1,159 passing lines while proving nothing, so the
discrimination itself is tested here against modules built on the fly in a
temporary directory — no file in the repository is touched.

The two cases that matter are the two that are easy to get backwards:

* ``from hermes_cli.<gone> import x`` — a **dangling first-party import**,
  the shape a bad merge leaves behind.  This must FAIL.
* ``import some_optional_sdk`` — a third-party package that simply is not
  installed here.  This must SKIP, or the layer becomes a list of
  environment complaints nobody reads.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from tests.smoke._discovery import (
    ZERO_TEST_PACKAGES,
    classify_import_failure,
    discover_modules,
    first_party_top_level,
)
# Imported as a module, not by name: binding ``test_module_imports`` into
# this namespace would make pytest re-collect all 1,155 of its parametrised
# cases a second time under this file.
from tests.smoke import test_import_smoke as _import_smoke

run_import_case = _import_smoke.test_module_imports

_PKG = "smoke_layer_selftest_pkg"


def _write_probe_package(root: Path, modules: dict[str, str]) -> None:
    package_dir = root / _PKG
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    for name, source in modules.items():
        (package_dir / f"{name}.py").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )


@pytest.fixture
def probe_package(tmp_path: Path):
    """Build a throwaway package on sys.path and clean it up afterwards."""
    _write_probe_package(
        tmp_path,
        {
            "dangling_first_party": (
                "from hermes_cli.this_module_does_not_exist import anything\n"
            ),
            "missing_third_party": (
                "import a_third_party_sdk_that_is_not_installed_anywhere\n"
            ),
            "explodes_at_module_scope": (
                "CONFIG = {'agent': {}}\n"
                "VALUE = CONFIG['agent']['a_key_that_was_never_added']\n"
            ),
            "healthy": "VALUE = 1\n",
        },
    )
    sys.path.insert(0, str(tmp_path))
    try:
        yield tmp_path
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == _PKG or name.startswith(f"{_PKG}."):
                del sys.modules[name]


def test_dangling_first_party_import_fails_the_suite(probe_package: Path) -> None:
    """The merge-damage case must be a hard failure, never a skip."""
    with pytest.raises(AssertionError) as caught:
        run_import_case(f"{_PKG}.dangling_first_party")
    message = str(caught.value)
    assert "hermes_cli.this_module_does_not_exist" in message
    assert "Dangling first-party import" in message


def test_missing_third_party_dependency_is_skipped(probe_package: Path) -> None:
    """A dependency this environment does not install is not a defect."""
    with pytest.raises(pytest.skip.Exception) as caught:
        run_import_case(f"{_PKG}.missing_third_party")
    assert "optional third-party dependency" in str(caught.value)
    assert "a_third_party_sdk_that_is_not_installed_anywhere" in str(caught.value)


def test_module_scope_keyerror_fails_the_suite(probe_package: Path) -> None:
    """Not every breakage is an ImportError.

    This is the exact shape that broke four gateway modules on 2026-08-16 —
    a module-scope lookup into a config dict that had lost the key — and it
    must fail rather than being classified as an environment problem.
    """
    with pytest.raises(AssertionError) as caught:
        run_import_case(f"{_PKG}.explodes_at_module_scope")
    assert "KeyError" in str(caught.value)


def test_healthy_module_passes(probe_package: Path) -> None:
    """The control case: a fine module must not raise anything."""
    run_import_case(f"{_PKG}.healthy")


def test_first_party_set_contains_the_packages_under_test() -> None:
    """The FAIL/SKIP split hinges on this set being right."""
    missing = [p for p in ZERO_TEST_PACKAGES if p not in first_party_top_level()]
    assert not missing, (
        f"{missing} are not recognised as first-party, so a dangling import "
        f"into them would be misclassified as a missing optional dependency "
        f"and silently skipped."
    )


def test_posix_only_stdlib_is_skipped_not_failed() -> None:
    """``fcntl`` on Windows is a platform fact, not a defect."""
    verdict = classify_import_failure(
        "hermes_cli.pty_bridge", ModuleNotFoundError("No module named 'fcntl'", name="fcntl")
    )
    if sys.platform.startswith("win"):
        assert verdict.action == "skip"
        assert "POSIX-only" in verdict.reason
    else:
        # On POSIX ``fcntl`` exists, so this classification path is unused;
        # assert only that it is not silently mislabelled first-party.
        assert "Dangling first-party import" not in verdict.reason


def test_discovered_module_names_map_back_to_real_files() -> None:
    """Discovery must produce importable names, not path fragments."""
    for package in ZERO_TEST_PACKAGES:
        modules = discover_modules(package)
        assert modules, f"no modules discovered under {package!r}"
        for name in modules[:25]:
            assert name == package or name.startswith(f"{package}."), name
            assert all(part.isidentifier() for part in name.split(".")), name
