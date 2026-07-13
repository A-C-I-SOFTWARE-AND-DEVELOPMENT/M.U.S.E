from __future__ import annotations

from pathlib import Path

import pytest

from agent.studio.source_map import SourceRegistry, SourceRevisionConflict


def test_component_map_resolves_to_repo_relative_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "AtlasCrown.tsx"
    source.parent.mkdir()
    source.write_text("export const ringMaterial = 'gold';\n", encoding="utf-8")
    registry = SourceRegistry(tmp_path, revision="abc")
    registry.register("atlas.crown.ring", "src/AtlasCrown.tsx", 1, "ringMaterial")
    ref = registry.resolve("atlas.crown.ring")
    assert ref.file == "src/AtlasCrown.tsx"
    assert ref.line == 1
    assert ref.revision == "abc"


def test_registry_rejects_escape_and_stale_revision(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path, revision="abc")
    registry.register("atlas", "Atlas.tsx", 1, "material")
    with pytest.raises(ValueError, match="workspace"):
        registry.register("bad", "../secret.env", 1, "x")
    with pytest.raises(SourceRevisionConflict):
        registry.resolve("atlas", revision="def")


def test_registry_rejects_sensitive_and_non_allowlisted_properties(tmp_path: Path) -> None:
    registry = SourceRegistry(
        tmp_path,
        revision="abc",
        allowed_properties={"atlas": ("material.color",)},
    )
    with pytest.raises(ValueError, match="allowlisted"):
        registry.register("atlas", "Atlas.tsx", 1, "material.opacity")
    with pytest.raises(ValueError, match="sensitive"):
        registry.register("secret", "Atlas.tsx", 1, "api_key")
