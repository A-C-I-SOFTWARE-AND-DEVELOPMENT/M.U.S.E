"""Declared entry points resolve to callables with the signature they need.

``pyproject.toml``'s ``[project.scripts]`` table is a contract with the
installed environment: pip writes a launcher that does
``from <module> import <attr>; sys.exit(<attr>())``.  If the module fails to
import, or the attribute is missing, or the callable requires an argument,
the installed ``hermes`` binary is broken while every unit test still passes —
because nothing in the repository exercised the console-script path.

The entry points are read from ``pyproject.toml`` at collection time, so a
new script added there is covered without editing this file.
"""

from __future__ import annotations

import importlib
import inspect
import tomllib
from pathlib import Path

import pytest

from tests.smoke._discovery import REPO_ROOT, first_party_top_level

_PYPROJECT = REPO_ROOT / "pyproject.toml"


def _console_scripts() -> list[tuple[str, str, str]]:
    """Return ``(script_name, module, attribute)`` for every console script."""
    if not _PYPROJECT.is_file():
        return []
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    scripts = data.get("project", {}).get("scripts", {}) or {}
    parsed: list[tuple[str, str, str]] = []
    for name, target in sorted(scripts.items()):
        module, _, attr = str(target).partition(":")
        parsed.append((name, module, attr or "main"))
    return parsed


_SCRIPTS = _console_scripts()
_IDS = [f"{name}={module}:{attr}" for name, module, attr in _SCRIPTS]


def test_pyproject_declares_console_scripts() -> None:
    """Guard against a vacuously-green suite (4 scripts on 2026-08-16)."""
    assert _SCRIPTS, (
        f"no [project.scripts] entries were parsed out of {_PYPROJECT}; the "
        f"entry-point assertions below would cover nothing."
    )


@pytest.mark.parametrize("name,module_name,attr", _SCRIPTS, ids=_IDS or None)
def test_console_script_target_imports(name: str, module_name: str, attr: str) -> None:
    """``pip``'s generated launcher must be able to import its target."""
    module = importlib.import_module(module_name)
    assert hasattr(module, attr), (
        f"console script {name!r} points at {module_name}:{attr}, but "
        f"{module_name} has no attribute {attr!r}. The installed {name!r} "
        f"command would fail with ImportError."
    )


@pytest.mark.parametrize("name,module_name,attr", _SCRIPTS, ids=_IDS or None)
def test_console_script_target_is_callable_with_no_arguments(
    name: str, module_name: str, attr: str
) -> None:
    """The launcher calls the target with zero arguments.

    Every parameter must therefore have a default (or be ``*args``/
    ``**kwargs``).  A required positional parameter means the installed
    command raises ``TypeError`` before it does anything.
    """
    module = importlib.import_module(module_name)
    target = getattr(module, attr)
    assert callable(target), f"{module_name}:{attr} is not callable: {target!r}"

    signature = inspect.signature(target)
    required = [
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]
    assert not required, (
        f"console script {name!r} -> {module_name}:{attr}{signature} requires "
        f"{required}; the generated launcher calls it with no arguments."
    )


@pytest.mark.parametrize("name,module_name,attr", _SCRIPTS, ids=_IDS or None)
def test_console_script_target_is_defined_in_this_repository(
    name: str, module_name: str, attr: str
) -> None:
    """A console script must not silently resolve to a third-party callable."""
    module = importlib.import_module(module_name)
    target = getattr(module, attr)
    origin = getattr(target, "__module__", "") or ""
    root = origin.split(".")[0]
    assert root in first_party_top_level(), (
        f"console script {name!r} resolves to {origin}:{attr}, whose "
        f"top-level package {root!r} is not part of this repository."
    )


def test_pyproject_console_scripts_have_no_duplicate_targets_for_one_name() -> None:
    """Two scripts may share a target (``hermes``/``hermes-agent``); a name may not.

    ``tomllib`` would already reject a duplicate key, so this is a cheap
    assertion that the table parsed into the shape the rest of the module
    assumes rather than a re-test of the TOML parser.
    """
    names = [name for name, _, _ in _SCRIPTS]
    assert len(names) == len(set(names))
    for name, module_name, attr in _SCRIPTS:
        assert module_name, f"console script {name!r} has an empty module part"
        assert attr, f"console script {name!r} has an empty attribute part"


def test_entrypoint_modules_are_real_files() -> None:
    """Each entry-point module resolves to a file inside the repository."""
    for name, module_name, _attr in _SCRIPTS:
        module = importlib.import_module(module_name)
        origin = getattr(module, "__file__", None)
        assert origin, f"console script {name!r} target {module_name} has no __file__"
        resolved = Path(origin).resolve()
        assert REPO_ROOT in resolved.parents, (
            f"console script {name!r} target {module_name} resolves to "
            f"{resolved}, which is outside {REPO_ROOT}."
        )
