"""Tests for the Hermes Local worker.

The worker writes evidence to a directory tree we control via
``tmp_path``; tests never touch the real repo. Git interactions are
tested by creating a throwaway repo under ``tmp_path`` and either
initialising ``.git`` (when we want repo-aware paths exercised) or
omitting it (to verify the not-a-repo branch).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from muse_cli.workers.hermes_local import (
    HermesLocalWorker,
    TestCommand,
    WorkerStatus,
    _dedup_commands,
    _infer_from_makefile,
    _infer_from_markdown,
    _infer_from_package_json,
    _infer_from_pyproject,
)


# ── fixtures ──────────────────────────────────────────────────────────


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def fake_python_repo(tmp_path: Path) -> Path:
    """A tmp directory shaped like a small Python project."""
    _write(tmp_path / "pyproject.toml", _PYPROJECT_FIXTURE)
    _write(tmp_path / "uv.lock", "# uv lock\n")
    _write(tmp_path / "README.md", _README_FIXTURE)
    _write(tmp_path / "AGENTS.md", "# AGENTS\nrun `pytest -q`\n")
    _write(tmp_path / "Makefile", _MAKEFILE_FIXTURE)
    _write(tmp_path / "package.json", _PACKAGE_JSON_FIXTURE)
    _write(tmp_path / "src" / "app.py", "print('hi')\n")
    _write(tmp_path / "tests" / "test_app.py", "def test_x(): assert True\n")
    _write(tmp_path / "scripts" / "build.sh", "#!/bin/sh\necho build\n")
    # Risky files that should be flagged
    _write(tmp_path / ".env", "SECRET=please-do-not-commit\n")
    _write(tmp_path / "deploy.pem", "----- PRIVATE -----\n")
    return tmp_path


_PYPROJECT_FIXTURE = """\
[project]
name = "demo"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
preview = true

[tool.ty.environment]
python-version = "3.13"
"""

_PACKAGE_JSON_FIXTURE = """\
{
  "name": "demo",
  "version": "0.1.0",
  "scripts": {
    "test": "vitest",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "build": "vite build",
    "dev": "vite",
    "other": "echo skip me"
  }
}
"""

_MAKEFILE_FIXTURE = """\
.PHONY: test lint hello

test:
\tpytest

lint:
\truff check .

hello:
\techo hi
"""

_README_FIXTURE = """\
# Demo

Run the tests:

```bash
pytest -q
```

Also:

```shell
$ make test
```
"""


# ── availability + construction ───────────────────────────────────────


def test_is_available_is_true():
    assert HermesLocalWorker.is_available() is True


def test_paths_default_to_root(tmp_path):
    w = HermesLocalWorker(tmp_path)
    assert w.root == tmp_path.resolve()
    assert w.output_base == tmp_path.resolve()


def test_output_base_overrides_root(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    w = HermesLocalWorker(tmp_path, output_base=out)
    assert w.root == tmp_path.resolve()
    assert w.output_base == out.resolve()


# ── discovery primitives ─────────────────────────────────────────────


def test_top_level_map_lists_dirs_then_files(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    entries = w.top_level_map()
    names = [e["name"] for e in entries]
    # dirs come before files
    kinds = [e["kind"] for e in entries]
    first_file_idx = kinds.index("file")
    assert all(k == "dir" for k in kinds[:first_file_idx])
    # known fixtures show up
    assert "pyproject.toml" in names
    assert "src" in names
    assert "scripts" in names


def test_detect_languages_recognises_python(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    langs = w.detect_languages()
    assert "python" in langs
    # package.json fixture also pulls in node/javascript
    assert "node" in langs
    assert "javascript" in langs


def test_detect_package_managers(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    pms = w.detect_package_managers()
    assert "uv" in pms        # uv.lock + pyproject.toml
    assert "make" in pms      # Makefile present


def test_detect_test_commands_from_pyproject_and_makefile(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    cmds = w.detect_test_commands()
    by_label = {c.label for c in cmds}
    assert "pytest" in by_label
    assert "ruff check" in by_label
    assert "ty check" in by_label
    assert "make test" in by_label
    assert "make lint" in by_label
    assert "npm run test" in by_label
    assert "npm run lint" in by_label
    # README's fenced ``pytest -q`` block surfaces too
    assert any(c.source == "README.md" for c in cmds)


def test_detect_test_commands_no_executions(fake_python_repo, monkeypatch):
    """The worker must NEVER spawn the inferred commands."""

    def _no_spawn(*_a, **_kw):
        raise AssertionError("subprocess.run was called by detect_test_commands")

    monkeypatch.setattr(subprocess, "run", _no_spawn)
    w = HermesLocalWorker(fake_python_repo)
    # Calling discovery must not invoke any subprocesses.
    w.detect_test_commands()
    w.detect_languages()
    w.detect_package_managers()
    w.find_scripts()
    w.find_risky_files()
    w.find_docs_entrypoints()


def test_find_risky_files(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    risky = w.find_risky_files()
    assert ".env" in risky
    assert "deploy.pem" in risky


def test_find_docs_entrypoints(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    docs = w.find_docs_entrypoints()
    assert "README.md" in docs
    assert "AGENTS.md" in docs


def test_find_scripts(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    scripts = w.find_scripts()
    assert "scripts/build.sh" in scripts


def test_git_state_without_dot_git(fake_python_repo):
    w = HermesLocalWorker(fake_python_repo)
    state = w.inspect_git_state()
    assert state["is_git_repo"] is False
    assert state["branch"] == ""
    assert state["status"] == []


def test_git_state_with_dot_git_marker(tmp_path, monkeypatch):
    """When ``.git`` exists, we shell out for branch + porcelain status.

    We don't depend on a working ``git`` binary in the test env — we
    stub the helper so behaviour is deterministic.
    """
    (tmp_path / ".git").mkdir()
    fake_outputs = {
        ("rev-parse", "--abbrev-ref", "HEAD"): "feature/x\n",
        ("status", "--porcelain"): " M README.md\n?? new.txt\n",
    }

    def _fake_git(root, args, *, timeout=5.0):
        return fake_outputs.get(tuple(args), "")

    import muse_cli.workers.hermes_local as mod
    monkeypatch.setattr(mod, "_git", _fake_git)
    state = HermesLocalWorker(tmp_path).inspect_git_state()
    assert state["is_git_repo"] is True
    assert state["branch"] == "feature/x"
    assert state["status"] == [" M README.md", "?? new.txt"]


# ── full run ──────────────────────────────────────────────────────────


def test_run_writes_all_six_artifacts(fake_python_repo, monkeypatch):
    """``run()`` writes the contracted artifact paths and returns ok=True."""
    import muse_cli.workers.hermes_local as mod

    # Avoid relying on a real git binary; ``.git`` is absent here so the
    # helper short-circuits, but stub anyway to prove no shelling out.
    monkeypatch.setattr(mod, "_git", lambda *_a, **_k: "")
    status = HermesLocalWorker(fake_python_repo).run()
    assert isinstance(status, WorkerStatus)
    assert status.ok is True
    assert status.errors == []

    expected = {
        "shared-context/repo-map.md",
        "shared-context/evidence.md",
        "shared-context/test-map.md",
        "shared-context/git-state.md",
        "workers/hermes-local/output.md",
        "workers/hermes-local/status.json",
    }
    assert expected.issubset(set(status.artifacts))
    for rel in expected:
        assert (fake_python_repo / rel).is_file(), f"missing artifact: {rel}"


def test_run_writes_status_json_machine_readable(fake_python_repo):
    HermesLocalWorker(fake_python_repo).run()
    raw = (fake_python_repo / "workers" / "hermes-local" / "status.json").read_text()
    payload = json.loads(raw)
    assert payload["worker"] == "hermes-local"
    assert payload["available"] is True
    assert payload["ok"] is True
    assert isinstance(payload["artifacts"], list)
    assert payload["started_at"]
    assert payload["finished_at"]


def test_run_with_separate_output_base(tmp_path):
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    repo.mkdir()
    out.mkdir()
    _write(repo / "pyproject.toml", "[tool.pytest.ini_options]\n")

    status = HermesLocalWorker(repo, output_base=out).run()
    assert status.ok is True
    # Nothing was written to the repo itself
    assert not (repo / "shared-context").exists()
    assert not (repo / "workers").exists()
    # Everything landed under output_base
    assert (out / "shared-context" / "repo-map.md").is_file()
    assert (out / "workers" / "hermes-local" / "status.json").is_file()


def test_run_captures_unexpected_errors(fake_python_repo, monkeypatch):
    """If an internal step raises, status.json is still written with ok=False."""
    import muse_cli.workers.hermes_local as mod

    def _boom(self):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(mod.HermesLocalWorker, "top_level_map", _boom)
    status = HermesLocalWorker(fake_python_repo).run()
    assert status.ok is False
    assert any("synthetic failure" in e for e in status.errors)
    status_path = fake_python_repo / "workers" / "hermes-local" / "status.json"
    assert status_path.is_file()
    payload = json.loads(status_path.read_text())
    assert payload["ok"] is False


def test_repo_map_content_mentions_top_level_entries(fake_python_repo):
    HermesLocalWorker(fake_python_repo).run()
    body = (fake_python_repo / "shared-context" / "repo-map.md").read_text()
    assert "pyproject.toml" in body
    assert "src" in body


def test_evidence_groups_render_when_empty(tmp_path):
    """An otherwise-empty repo still produces a well-formed evidence file."""
    HermesLocalWorker(tmp_path).run()
    body = (tmp_path / "shared-context" / "evidence.md").read_text()
    assert "Languages / runtimes detected" in body
    assert "Package managers detected" in body
    assert "Risky files at repo root" in body


def test_test_map_groups_by_source(fake_python_repo):
    HermesLocalWorker(fake_python_repo).run()
    body = (fake_python_repo / "shared-context" / "test-map.md").read_text()
    assert "## From `pyproject.toml`" in body
    assert "## From `Makefile`" in body
    assert "## From `package.json`" in body


# ── unit tests for the extractors ────────────────────────────────────


def test_infer_from_pyproject_detects_tools():
    out = _infer_from_pyproject(_PYPROJECT_FIXTURE)
    labels = {c.label for c in out}
    assert "pytest" in labels
    assert "ruff check" in labels
    assert "ty check" in labels


def test_infer_from_pyproject_with_no_tools():
    assert _infer_from_pyproject("[project]\nname = 'x'\n") == []


def test_infer_from_package_json_picks_known_scripts():
    out = _infer_from_package_json(_PACKAGE_JSON_FIXTURE)
    labels = {c.label for c in out}
    assert "npm run test" in labels
    assert "npm run lint" in labels
    assert "npm run typecheck" in labels
    assert "npm run build" in labels
    # ``dev``/``other`` are not in the known-script allowlist
    assert "npm run dev" not in labels
    assert "npm run other" not in labels


def test_infer_from_package_json_handles_bad_json():
    assert _infer_from_package_json("{not json") == []


def test_infer_from_makefile_filters_to_validation_targets():
    out = _infer_from_makefile(_MAKEFILE_FIXTURE)
    labels = {c.label for c in out}
    assert "make test" in labels
    assert "make lint" in labels
    assert "make hello" not in labels


def test_infer_from_markdown_extracts_commands_from_fenced_blocks():
    md = """
```bash
pytest -q
```

```
# not a recognised shell block
pytest -k smoke
```

```shell
$ make test
```
"""
    out = _infer_from_markdown("README.md", md)
    cmds = {c.command for c in out}
    assert "pytest -q" in cmds
    assert "make test" in cmds


def test_dedup_commands_removes_exact_duplicates():
    a = TestCommand("pyproject.toml", "pytest", "pytest")
    b = TestCommand("pyproject.toml", "pytest", "pytest")
    c = TestCommand("Makefile", "make test", "make test")
    out = _dedup_commands([a, b, c])
    assert len(out) == 2
    assert out[0] is a
    assert out[1] is c
