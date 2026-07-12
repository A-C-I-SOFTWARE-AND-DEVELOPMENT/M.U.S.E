from __future__ import annotations

from collections.abc import Mapping
from importlib import util
from pathlib import Path
from typing import Any, Protocol


class AchievementEvidenceAdapter(Protocol):
    def record(self, evidence: dict[str, object]) -> Mapping[str, object] | None: ...


class AchievementBridge:
    """Optional evidence sink; achievement display state never grants authority."""

    def __init__(
        self,
        *,
        adapter: AchievementEvidenceAdapter | None = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.adapter = adapter if adapter is not None else _load_supported_adapter()

    def record_completed_mission(
        self, mission: Mapping[str, Any]
    ) -> dict[str, object] | None:
        if not self.enabled or self.adapter is None:
            return None
        if mission.get("state") != "completed":
            return None
        evidence = mission.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            return None
        mode = mission.get("mode")
        if mode == "simulation" and mission.get("evidence_label") != "simulation":
            return None
        if mode not in {"real", "simulation"}:
            return None
        envelope: dict[str, object] = {
            "mission_id": str(mission.get("id", "")),
            "mode": mode,
            "evidence": tuple(str(item) for item in evidence),
            "source_type": str(mission.get("source_type", "")),
            "source_id": str(mission.get("source_id", "")),
        }
        try:
            reference = self.adapter.record(envelope)
        except Exception:
            return None
        if not isinstance(reference, Mapping):
            return None
        if any(
            key in reference
            for key in ("scope", "scopes", "role", "roles", "approval", "capabilities", "tools")
        ):
            return None
        required = ("session_id", "title", "value")
        if not all(reference.get(key) is not None for key in required):
            return None
        return {key: reference[key] for key in required}


class _CallableAdapter:
    def __init__(self, callback: Any) -> None:
        self._callback = callback

    def record(self, evidence: dict[str, object]) -> Mapping[str, object] | None:
        return self._callback(evidence)


def _load_supported_adapter() -> AchievementEvidenceAdapter | None:
    """Load only an explicit external-evidence seam when the plugin provides one."""

    path = (
        Path(__file__).resolve().parents[1]
        / "hermes-achievements"
        / "dashboard"
        / "plugin_api.py"
    )
    if not path.is_file():
        return None
    try:
        if "def record_external_evidence" not in path.read_text(encoding="utf-8"):
            return None
        spec = util.spec_from_file_location("muse_achievements_plugin_api", path)
        if spec is None or spec.loader is None:
            return None
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    callback = getattr(module, "record_external_evidence", None)
    if not callable(callback):
        return None
    return _CallableAdapter(callback)
