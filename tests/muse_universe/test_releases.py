from __future__ import annotations

from pathlib import Path

import pytest

from plugins.muse_universe.releases import ReleaseBlocked, ReleaseManager


def _bundle(version: str = "1.0.0", **overrides: object) -> dict[str, object]:
    gates: dict[str, object] = {
        "verification": "passed",
        "provenance": "passed",
        "rights": "passed",
        "security": "passed",
        "performance": "passed",
        "accessibility": "passed",
    }
    gates.update(overrides.pop("gates", {}))
    value: dict[str, object] = {
        "project_id": "atlas",
        "version": version,
        "artifact_ref": f"bundle-{version}",
        "rollback_source": f"git:{version}",
        "gates": gates,
    }
    value.update(overrides)
    return value


class PassingAdapter:
    def publish(self, candidate: object) -> dict[str, object]:
        version = getattr(candidate, "version")
        return {
            "success": True,
            "provider": "test",
            "deployment_id": f"dep-{version}",
            "url": f"https://example.invalid/{version}",
        }

    def rollback(self, release: object) -> dict[str, object]:
        return {"success": True, "deployment_id": getattr(release, "deployment_id")}


class FailingAdapter(PassingAdapter):
    def publish(self, candidate: object) -> dict[str, object]:
        return {"success": False, "error": "provider unavailable"}


def test_preview_never_auto_promotes(tmp_path: Path) -> None:
    releases = ReleaseManager(tmp_path)
    preview = releases.create_preview(_bundle())
    assert preview.visibility == "private"
    assert preview.production_eligible is False
    assert releases.current_public("atlas") is None


def test_failed_publish_preserves_previous_version(tmp_path: Path) -> None:
    releases = ReleaseManager(tmp_path)
    previous = releases.promote(
        _bundle("1.0.0"), approval_id="apr_1", adapter=PassingAdapter()
    )
    result = releases.promote(
        _bundle("1.1.0"), approval_id="apr_2", adapter=FailingAdapter()
    )
    assert result.status == "failed"
    assert result.partial_success is False
    assert releases.current_public("atlas").id == previous.id  # type: ignore[union-attr]


def test_release_requires_all_rights_security_and_product_gates(tmp_path: Path) -> None:
    releases = ReleaseManager(tmp_path)
    with pytest.raises(ReleaseBlocked) as exc:
        releases.stage(_bundle(gates={"rights": "missing"}))
    assert "rights" in exc.value.failed_gates


def test_rollback_restores_prior_durable_release_and_keeps_evidence(tmp_path: Path) -> None:
    releases = ReleaseManager(tmp_path)
    previous = releases.promote(
        _bundle("1.0.0"), approval_id="apr_1", adapter=PassingAdapter()
    )
    current = releases.promote(
        _bundle("1.1.0"), approval_id="apr_2", adapter=PassingAdapter()
    )
    result = releases.rollback("atlas", reason="regression", adapter=PassingAdapter())
    assert result.status == "rolled_back"
    assert releases.current_public("atlas").id == previous.id  # type: ignore[union-attr]
    state = (tmp_path / "release-state.json").read_text(encoding="utf-8")
    assert current.id in state
    assert result.id in state
