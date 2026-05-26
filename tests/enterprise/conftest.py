"""Per-suite fixtures for the enterprise council tests.

Two things to enforce:

1. **Hermes home is hermetic.** Audit files are written under
   ``HERMES_HOME/enterprise/audit/``; the parent ``conftest.py`` already
   redirects HERMES_HOME to a per-test tempdir, but we point a sub-fixture
   at it explicitly so individual tests don't have to remember.
2. **Credential env is seeded.** Each test that exercises ``fetch_secret``
   sets the ``<SERVICE>_API_KEY`` env var it needs and tears it down after.
   We provide a tiny helper that handles both ends.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

SeedSecret = Callable[[str, str], None]


@pytest.fixture
def audit_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HERMES_HOME at the per-test tempdir and return the audit dir."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    target = tmp_path / "enterprise" / "audit"
    target.mkdir(parents=True, exist_ok=True)
    return target


@pytest.fixture
def seed_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[SeedSecret]:
    """Helper to set + unset ``<SERVICE>_API_KEY`` env vars for tests."""
    set_vars: list[str] = []

    def _set(service: str, value: str = "sk-test-FAKEFAKEFAKEFAKEFAKE") -> None:
        key = f"{service.upper().replace('-', '_')}_API_KEY"
        monkeypatch.setenv(key, value)
        set_vars.append(key)

    yield _set
    for key in set_vars:
        os.environ.pop(key, None)
