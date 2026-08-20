"""Every registered ``hermes`` command resolves and renders its ``--help``.

``hermes_cli/main.py::main`` is one of the §5.3 complexity hotspots and had
no coverage of its own registration surface: a subcommand could be
registered against a handler that no longer exists, or with an argparse
configuration that raises while formatting help, and nothing would notice
until a user typed the command.

Both assertions here are cheap and structural:

* the command's ``func`` default resolves to a real first-party callable;
* ``parser.format_help()`` renders — which is what argparse does for
  ``hermes <command> --help``, and is where a bad ``%(default)s`` in a help
  string or a broken formatter class actually blows up.

The command list is walked out of the live parser tree, so a subcommand
added to ``main.py`` tomorrow is covered without editing this file.
"""

from __future__ import annotations

import pytest

from tests.smoke._cli_surface import (
    command_paths,
    parser_for,
    top_level_command_names,
)
from tests.smoke._discovery import first_party_top_level

# Built at collection so the command list can be parametrised.  A failure
# here must not abort collection — ``test_cli_parser_tree_builds`` reports it.
_BUILD_ERROR: Exception | None = None
try:
    _COMMAND_PATHS = command_paths()
    _TOP_LEVEL = top_level_command_names()
except Exception as exc:  # noqa: BLE001 - includes CliSurfaceError
    _BUILD_ERROR = exc
    _COMMAND_PATHS = ()
    _TOP_LEVEL = ()

_IDS = [" ".join(p) for p in _COMMAND_PATHS]


def test_cli_parser_tree_builds() -> None:
    """The whole registration surface must be constructible at all."""
    assert _BUILD_ERROR is None, (
        f"the hermes CLI parser tree could not be built, so no command could "
        f"be checked: {type(_BUILD_ERROR).__name__}: {_BUILD_ERROR}"
    )


def test_cli_exposes_a_realistic_command_surface() -> None:
    """Guard against a vacuously-green suite.

    53 top-level commands and 312 command paths (top-level plus nested
    subcommands) were observed on 2026-08-17.  The floors sit well below
    that so removing a command does not trip them, but a capture that
    silently returned an empty tree does.
    """
    assert len(_TOP_LEVEL) >= 40, (
        f"only {len(_TOP_LEVEL)} top-level hermes commands were discovered; "
        f"expected 40+. Parser capture is probably broken, which would make "
        f"every command assertion below vacuous."
    )
    assert len(_COMMAND_PATHS) >= 200, (
        f"only {len(_COMMAND_PATHS)} command paths were discovered "
        f"(top-level + subcommands); expected 200+."
    )


@pytest.mark.parametrize("path", _COMMAND_PATHS, ids=_IDS)
def test_command_help_renders(path: tuple[str, ...]) -> None:
    """``hermes <path> --help`` must format without raising."""
    parser = parser_for(path)
    help_text = parser.format_help()
    assert help_text.strip(), f"hermes {' '.join(path)} --help rendered nothing"
    assert "usage" in help_text.lower(), (
        f"hermes {' '.join(path)} --help produced no usage line:\n{help_text[:400]}"
    )


@pytest.mark.parametrize("name", _TOP_LEVEL, ids=list(_TOP_LEVEL))
def test_top_level_command_resolves_to_first_party_callable(name: str) -> None:
    """Each top-level command dispatches to a real function in this repo.

    A command registered with ``set_defaults(func=...)`` pointing at
    something that is not callable — or at a stub outside the repository —
    is broken for every user who types it.
    """
    parser = parser_for((name,))
    handler = parser.get_default("func")
    assert handler is not None, (
        f"hermes {name} registers no `func` default, so main() has nothing to "
        f"dispatch to."
    )
    assert callable(handler), f"hermes {name} -> func is not callable: {handler!r}"
    origin = getattr(handler, "__module__", "") or ""
    root = origin.split(".")[0]
    assert root in first_party_top_level(), (
        f"hermes {name} dispatches to {origin}.{getattr(handler, '__name__', handler)!r}, "
        f"whose top-level package {root!r} is not part of this repository."
    )


@pytest.mark.parametrize("path", _COMMAND_PATHS, ids=_IDS)
def test_subcommand_func_default_is_callable_when_declared(
    path: tuple[str, ...],
) -> None:
    """Where a subcommand declares a handler, that handler must be callable.

    Not every nested subcommand sets one — several dispatch on the ``dest``
    string inside ``main()`` instead — so this asserts the contract only
    where the contract was declared, rather than inventing a requirement the
    CLI does not have.
    """
    parser = parser_for(path)
    handler = parser.get_default("func")
    if handler is None:
        pytest.skip(
            f"hermes {' '.join(path)} dispatches on its `dest` string rather "
            f"than a `func` default; there is no handler object to check."
        )
    assert callable(handler), (
        f"hermes {' '.join(path)} -> func is not callable: {handler!r}"
    )
