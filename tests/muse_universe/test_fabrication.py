from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from agent.studio.source_map import SourceRegistry
from plugins.muse_universe.fabrication import FabricationGateError, FabricationSession
from plugins.muse_universe.workspaces import WorkspaceCheckpoint


class RecordingBroker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def checkpoint(self, lease_id: str, label: str) -> WorkspaceCheckpoint:
        self.calls.append((lease_id, label))
        return WorkspaceCheckpoint(lease_id, "abc123", label, 1.0)


def test_edit_changes_only_isolated_workspace_and_returns_diff(tmp_path: Path) -> None:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    source.mkdir()
    (source / "Atlas.tsx").write_text("const color = 'gold';\n", encoding="utf-8")
    shutil.copytree(source, workspace)
    registry = SourceRegistry(workspace, revision="rev_1")
    registry.register("atlas.ring", "Atlas.tsx", 1, "material.color")
    session = FabricationSession(
        workspace,
        registry,
        required_gates=("test",),
        commands={"test": ("verify",)},
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok", ""),
    )
    edit = session.edit("atlas.ring", "'cyan'", expected_text="'gold'")
    assert "-const color = 'gold';" in edit.diff
    assert "+const color = 'cyan';" in edit.diff
    assert "gold" in (source / "Atlas.tsx").read_text(encoding="utf-8")
    assert "cyan" in (workspace / "Atlas.tsx").read_text(encoding="utf-8")


def test_apply_requires_gates_and_checkpoints_before_acceptance(tmp_path: Path) -> None:
    source = tmp_path / "Atlas.tsx"
    source.write_text("const color = 'gold';\n", encoding="utf-8")
    registry = SourceRegistry(tmp_path, revision="rev_1")
    registry.register("atlas.ring", "Atlas.tsx", 1, "material.color")
    broker = RecordingBroker()
    session = FabricationSession(
        tmp_path,
        registry,
        lease_id="lease_1",
        broker=broker,  # type: ignore[arg-type]
        required_gates=("test",),
        commands={"test": ("verify",)},
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok", ""),
    )
    edit = session.edit("atlas.ring", "'cyan'", expected_text="'gold'")
    with pytest.raises(FabricationGateError):
        session.apply(edit.id)
    assert session.verify().passed is True
    applied = session.apply(edit.id)
    assert applied.status == "applied"
    assert broker.calls and broker.calls[0][0] == "lease_1"


def test_failed_required_gate_blocks_apply_and_rollback_restores_source(tmp_path: Path) -> None:
    source = tmp_path / "Atlas.tsx"
    source.write_text("const color = 'gold';\n", encoding="utf-8")
    registry = SourceRegistry(tmp_path, revision="rev_1")
    registry.register("atlas.ring", "Atlas.tsx", 1, "material.color")
    session = FabricationSession(
        tmp_path,
        registry,
        required_gates=("test",),
        commands={"test": ("verify",)},
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1, "", "failed"),
    )
    edit = session.edit("atlas.ring", "'cyan'", expected_text="'gold'")
    assert session.verify().passed is False
    with pytest.raises(FabricationGateError):
        session.apply(edit.id)
    session.rollback(edit.id)
    assert "gold" in source.read_text(encoding="utf-8")
