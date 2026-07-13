from __future__ import annotations

from pathlib import Path

from agent.studio.provenance import AssetProvenance, sha256_file, verify_provenance


def test_public_asset_fails_without_license(tmp_path: Path) -> None:
    asset = tmp_path / "hull.glb"
    asset.write_bytes(b"glTF")
    provenance = AssetProvenance(
        asset_id="ast_1",
        creator="owner",
        source="original",
        content_hash=sha256_file(asset),
        allowed_uses=("private",),
    )
    result = verify_provenance(asset, provenance)
    assert result.passed is False
    assert "license" in result.failures
    assert "allowed_uses" in result.failures


def test_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    asset = tmp_path / "asset.bin"
    asset.write_bytes(b"changed")
    provenance = AssetProvenance(
        asset_id="ast_2",
        content_hash="sha256:" + "0" * 64,
        creator="owner",
        license="Proprietary",
        allowed_uses=("public",),
        safety_status="passed",
    )
    assert "content_hash" in verify_provenance(asset, provenance).failures


def test_public_record_has_prompt_reference_not_prompt_text(tmp_path: Path) -> None:
    asset = tmp_path / "asset.bin"
    asset.write_bytes(b"generated")
    provenance = AssetProvenance(
        asset_id="ast_3",
        content_hash=sha256_file(asset),
        creator="owner",
        generator="muse",
        model_version="1",
        source="generated",
        prompt_ref="sha256:" + "1" * 64,
        license="Owner generated",
        allowed_uses=("public",),
        safety_status="passed",
    )
    record = provenance.public_record()
    assert record["prompt_ref"].startswith("sha256:")
    assert "prompt" not in record
    assert verify_provenance(asset, provenance).passed is True
