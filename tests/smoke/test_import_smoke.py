"""Every module in the four zero-test packages must import cleanly.

This is the cheapest test in the repository that would have caught the
failure mode this project has actually had: a merge that leaves a module
importing something that no longer exists.  Nothing in ``hermes_cli``,
``gateway``, ``agent`` or ``tools`` had a test file before this module, so a
module could be broken at import and stay broken until a user ran it.

The parametrisation is discovered from disk (see
:mod:`tests.smoke._discovery`), so a package added tomorrow is covered
without editing this file.

A module that cannot import because of a missing optional dependency,
missing credential, absent accelerator or a POSIX-only stdlib module on
Windows is **skipped with the specific reason**.  A module that cannot
import because it references a first-party module that does not exist, or
blows up at module scope for any other reason, **fails** — that is the
signal this layer is here to produce, and it is not downgraded to a skip.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from tests.smoke._discovery import (
    MIN_DISCOVERED,
    REPO_ROOT,
    ZERO_TEST_PACKAGES,
    all_discovered_modules,
    classify_import_failure,
    discover_modules,
)

_MODULES = all_discovered_modules()


@pytest.fixture(scope="session", autouse=True)
def _repo_root_on_syspath():
    """Import the packages the way production does: from the repo root."""
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
        yield
        sys.path.remove(root)
    else:
        yield


@pytest.mark.parametrize("package", ZERO_TEST_PACKAGES)
def test_discovery_found_a_realistic_module_count(package: str) -> None:
    """Guard against a vacuously-green suite.

    If ``discover_modules`` silently returned a handful of modules, every
    import assertion below would pass while testing almost nothing.  The
    floors are well under the counts observed on 2026-08-17 (hermes_cli 619,
    gateway 120, agent 254, tools 162) so an ordinary deletion does not trip
    them — only a discovery collapse does.
    """
    found = discover_modules(package)
    floor = MIN_DISCOVERED[package]
    assert len(found) >= floor, (
        f"discovery found only {len(found)} modules under {package!r}; "
        f"expected at least {floor}. Either the package moved or module "
        f"discovery is broken — the import smoke layer is not actually "
        f"covering anything."
    )


def test_every_discovered_module_has_a_test_case() -> None:
    """The parametrised set below is the whole discovered set, not a sample."""
    expected = sum(len(discover_modules(p)) for p in ZERO_TEST_PACKAGES)
    assert len(_MODULES) == expected
    assert len(set(_MODULES)) == len(_MODULES), "duplicate module in parametrisation"


@pytest.mark.parametrize("module_name", _MODULES, ids=_MODULES)
def test_module_imports(module_name: str) -> None:
    """Importing *module_name* must not raise.

    Deliberately imports for real rather than compiling the source: a
    ``py_compile`` pass proves syntax, not that ``from gateway.restart
    import X`` resolves.
    """
    try:
        importlib.import_module(module_name)
    except BaseException as exc:  # noqa: BLE001 - classification is the point
        verdict = classify_import_failure(module_name, exc)
        if verdict.action == "skip":
            pytest.skip(verdict.reason)
        raise AssertionError(verdict.reason) from exc
