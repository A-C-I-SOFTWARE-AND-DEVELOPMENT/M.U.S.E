"""Shared fixtures for the ``prime`` plugin tests.

The suite runs against a real (tiny) repository written into ``tmp_path`` so
every assertion is about the plugin's actual output on real files — no mocks
of the walk, the AST parse, or the stores.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# The fixture repo. Paths are POSIX-relative; contents are chosen so each
# navigation signal has something real to find:
#
#   pkg/timeout_config.py   defines load_timeout / TimeoutConfig
#   pkg/client.py           imports + calls load_timeout  (IMPORTS/CALLS/deps)
#   tests/test_timeout_config.py  mirrors the name and imports it (TESTS)
#   docs/architecture.md    names pkg/timeout_config.py verbatim (CITES)
#   web/app.js              a non-python file for the regex symbol lane
_FIXTURE_FILES: dict[str, str] = {
    "pkg/__init__.py": "",
    "pkg/timeout_config.py": '''
"""Timeout configuration."""

DEFAULT_TIMEOUT = 30


class TimeoutConfig:
    def __init__(self, seconds: int = DEFAULT_TIMEOUT):
        self.seconds = seconds


def load_timeout(seconds: int | None = None) -> int:
    return seconds if seconds is not None else DEFAULT_TIMEOUT
''',
    "pkg/client.py": '''
"""HTTP-ish client that honours the configured timeout."""

from pkg.timeout_config import load_timeout


def fetch(url: str, seconds: int | None = None) -> str:
    timeout = load_timeout(seconds)
    return f"{url}:{timeout}"
''',
    "pkg/unrelated.py": '''
def paint_the_shed() -> str:
    return "green"
''',
    "tests/test_timeout_config.py": '''
from pkg.timeout_config import load_timeout


def test_load_timeout():
    assert load_timeout() == 30
''',
    "docs/architecture.md": (
        "# Architecture\n\n"
        "Timeouts are resolved in pkg/timeout_config.py and consumed by "
        "pkg/client.py.\n"
    ),
    "README.md": "# fixture repo\n\nNothing to see here.\n",
    "pyproject.toml": '[project]\nname = "fixture"\n',
    "web/app.js": (
        "import { helper } from './helper';\n"
        "export const APP_NAME = 'fixture';\n"
        "function renderApp() { return helper(APP_NAME); }\n"
    ),
    # Must be pruned by the walk, never indexed.
    "node_modules/junk/index.js": "module.exports = 1;\n",
    "__pycache__/stale.py": "broken(\n",
}


def write_repo(root: Path, files: dict[str, str] | None = None) -> Path:
    """Materialise a file map under ``root``. Returns ``root``."""

    for rel, body in (files if files is not None else _FIXTURE_FILES).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # newline="" keeps the bytes LF on every platform, so line counts and
        # AST offsets are identical on Windows and POSIX.
        target.write_text(body, encoding="utf-8", newline="")
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A small, real repository to navigate/index."""

    return write_repo(tmp_path / "fixture_repo")


@pytest.fixture
def index(repo: Path):
    from plugins.prime.navigation import RepoIndex

    return RepoIndex.build(repo)


@pytest.fixture
def symbols(index):
    from plugins.prime.navigation import SymbolGraph

    return SymbolGraph.build(index)


@pytest.fixture
def navigator(repo: Path):
    """A Navigator with the git-recency signal off (tmp_path is not a repo,
    and leaving it on would make rankings depend on the ambient checkout)."""

    from plugins.prime.navigation import Navigator

    return Navigator.for_repo(repo, use_git=False)
