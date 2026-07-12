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

    def outbox_for(
        self,
        mission: Mapping[str, Any],
        *,
        realm_id: str,
        command_id: str,
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
        outbox: dict[str, object] = {
            "version": 1,
            "kind": "mission.completed",
            "producer": "muse_universe",
            "mission_id": str(mission.get("id", "")),
            "mode": mode,
            "evidence_references": [str(item) for item in evidence],
            "source_type": str(mission.get("source_type", "")),
            "source_id": str(mission.get("source_id", "")),
            "provenance": {
                "realm_id": realm_id,
                "command_id": command_id,
            },
        }
        if mode == "simulation":
            outbox["simulation_label"] = "simulation"
        return outbox

    def record_outbox(
        self, outbox: Mapping[str, Any], *, occurred_at: str
    ) -> dict[str, object] | None:
        if not self.enabled or self.adapter is None:
            return None
        provenance = outbox.get("provenance")
        if not isinstance(provenance, Mapping):
            return None
        envelope = {
            **dict(outbox),
            "evidence_references": list(outbox.get("evidence_references", ())),
            "provenance": {**dict(provenance), "occurred_at": occurred_at},
        }
        try:
            reference = self.adapter.record(envelope)
        except Exception:
            return None
        if not isinstance(reference, Mapping):
            return None
        if set(reference) != {"status", "record_id", "dedupe_key"}:
            return None
        if reference.get("status") not in {"accepted", "duplicate"}:
            return None
        if any(
            not isinstance(reference.get(key), str) or not reference[key]
            for key in ("record_id", "dedupe_key")
        ):
            return None
        return {key: reference[key] for key in ("status", "record_id", "dedupe_key")}


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
