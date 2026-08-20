"""Build the *complete* ``hermes`` argparse tree without dispatching a command.

``hermes_cli/main.py::main`` builds all 50+ subparsers inline and then
immediately parses ``sys.argv`` and dispatches.  There is no seam that
returns the finished parser, and §5.3 explicitly prescribes characterization
tests and seam extraction for that function rather than a rewrite — so this
module introspects it instead of changing it.

The trick: ``main()`` obtains the top-level parser from
``hermes_cli._parser.build_top_level_parser`` via a *function-local* import,
so wrapping that attribute captures the object ``main`` then decorates with
every subparser.  Running ``main()`` with ``argv = ["hermes", "--help"]``
makes argparse print help and raise ``SystemExit(0)`` the instant parsing
starts — after the tree is fully built and before any command runs.

Three pre-argparse side effects are neutralised for the duration, because
none of them is under test and one of them is dangerous:

* ``_cleanup_quarantined_exes`` deletes ``hermes.exe.old.*`` files next to
  the interpreter.  A test must not delete anything on the operator's disk.
* ``get_container_exec_info`` — if the operator has NixOS container mode
  configured, ``main`` calls ``os.execvp`` and *replaces the pytest
  process*.  Forcing ``None`` keeps the test in-process.
* ``configure_windows_stdio`` reconfigures ``sys.stdout``/``sys.stderr``,
  which fights pytest's capture.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from functools import lru_cache


class CliSurfaceError(RuntimeError):
    """Raised when the CLI parser tree could not be built at all."""


@lru_cache(maxsize=1)
def build_cli_parser():
    """Return ``(top_level_parser, subparsers_action)`` for the hermes CLI."""
    import hermes_cli._parser as parser_mod
    import hermes_cli.config as config_mod
    import hermes_cli.main as main_mod
    import hermes_cli.stdio as stdio_mod

    captured: dict[str, object] = {}
    real_builder = parser_mod.build_top_level_parser
    real_cleanup = main_mod._cleanup_quarantined_exes
    real_container = config_mod.get_container_exec_info
    real_stdio = stdio_mod.configure_windows_stdio

    def _capturing_builder():
        parser, subparsers, chat_parser = real_builder()
        captured["parser"] = parser
        captured["subparsers"] = subparsers
        return parser, subparsers, chat_parser

    buffer = io.StringIO()
    saved_argv = sys.argv[:]
    parser_mod.build_top_level_parser = _capturing_builder
    main_mod._cleanup_quarantined_exes = lambda *a, **k: None
    config_mod.get_container_exec_info = lambda *a, **k: None
    stdio_mod.configure_windows_stdio = lambda *a, **k: False
    try:
        sys.argv = ["hermes", "--help"]
        with redirect_stdout(buffer), redirect_stderr(buffer):
            main_mod.main()
    except SystemExit:
        # Expected: argparse printed --help and exited.
        pass
    except BaseException as exc:  # noqa: BLE001
        if "subparsers" not in captured:
            raise CliSurfaceError(
                f"hermes CLI parser tree could not be built: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
    finally:
        sys.argv = saved_argv
        parser_mod.build_top_level_parser = real_builder
        main_mod._cleanup_quarantined_exes = real_cleanup
        config_mod.get_container_exec_info = real_container
        stdio_mod.configure_windows_stdio = real_stdio

    if "subparsers" not in captured:
        raise CliSurfaceError(
            "hermes_cli.main.main() returned without ever calling "
            "build_top_level_parser(); the CLI has no parser tree to inspect."
        )
    return captured["parser"], captured["subparsers"]


def _child_parsers(parser):
    """Yield ``(name, subparser)`` for one level below *parser*."""
    container = getattr(parser, "_subparsers", None)
    if container is None:
        return
    for action in container._group_actions:
        for name, child in getattr(action, "choices", {}).items():
            yield name, child


@lru_cache(maxsize=1)
def command_paths() -> tuple[tuple[str, ...], ...]:
    """Every registered command path, e.g. ``("gateway", "install")``.

    Discovered by walking the live parser tree, so a subcommand added to
    ``main.py`` tomorrow is covered without editing a test.
    """
    _parser, subparsers = build_cli_parser()
    paths: list[tuple[str, ...]] = []

    def walk(prefix: tuple[str, ...], parser, depth: int) -> None:
        if depth > 4:  # argparse trees here are 2 deep; this is a cycle guard
            return
        for name, child in _child_parsers(parser):
            path = (*prefix, name)
            paths.append(path)
            walk(path, child, depth + 1)

    for name, child in sorted(subparsers.choices.items()):
        paths.append((name,))
        walk((name,), child, 1)
    return tuple(paths)


def parser_for(path: tuple[str, ...]):
    """Resolve a command path to its argparse parser."""
    _parser, subparsers = build_cli_parser()
    current = subparsers.choices[path[0]]
    for segment in path[1:]:
        current = dict(_child_parsers(current))[segment]
    return current


def top_level_command_names() -> tuple[str, ...]:
    _parser, subparsers = build_cli_parser()
    return tuple(sorted(subparsers.choices))
