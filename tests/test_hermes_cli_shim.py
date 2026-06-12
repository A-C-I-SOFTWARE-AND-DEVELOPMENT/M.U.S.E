"""The permanent ``hermes_cli`` → ``muse_cli`` compat shim.

These tests pin the dual-identity contract of the rename: every old-name
import resolves to the *same module object* as the new name, string-based
patch targets keep working, and ``python -m hermes_cli.main`` still runs.
The old names are intentionally used throughout this file — do not "fix"
them to ``muse_cli``.
"""

import importlib
import subprocess
import sys
import warnings
from unittest import mock


def test_package_identity():
    import hermes_cli  # noqa: deprecated alias under test
    import muse_cli

    assert hermes_cli is muse_cli


def test_submodule_identity():
    import hermes_cli.main as old_main  # noqa: deprecated alias under test  # ty: ignore[unresolved-import]
    import muse_cli.main as new_main

    assert old_main is new_main


def test_dynamic_import_identity():
    old = importlib.import_module("hermes_cli.jarvis_prime")
    new = importlib.import_module("muse_cli.jarvis_prime")
    assert old is new


def test_from_import_resolves():
    from hermes_cli import config as old_config  # noqa: deprecated alias  # ty: ignore[unresolved-import]

    import muse_cli.config as new_config

    assert old_config is new_config


def test_string_patch_target_hits_shared_module():
    """mock.patch with the OLD dotted path must patch the real module."""
    import muse_cli.config as new_config

    sentinel = object()
    with mock.patch("hermes_cli.config.load_config", sentinel):
        assert new_config.load_config is sentinel
    assert new_config.load_config is not sentinel


def test_deprecation_warning_emitted():
    # Force re-resolution through the finder: a submodule not yet imported
    # in this process would be ideal, but re-importing the package is enough
    # when the warning also fires from the shim body / finder.
    sys.modules.pop("hermes_cli.env_loader", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("hermes_cli.env_loader")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_python_dash_m_old_name_still_runs():
    proc = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
