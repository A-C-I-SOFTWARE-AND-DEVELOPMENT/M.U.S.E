from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
UE = REPO / "apps" / "synapse-ue"
UNIVERSE = UE / "Source" / "SynapseUniverse"
CINEMATIC = UE / "Source" / "SynapseCinematic"
CONTRACT_LOCK = UE / "Config" / "UniverseContract.lock.json"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_source(module: Path) -> str:
    return "\n".join(
        _text(path)
        for path in sorted(module.rglob("*"))
        if path.suffix in {".h", ".cpp", ".cs"}
    )


def test_uproject_declares_universe_cinematic_and_ue56_plugins() -> None:
    project = json.loads(_text(UE / "Synapse.uproject"))
    assert project["EngineAssociation"] == "5.6"
    modules = {module["Name"] for module in project["Modules"]}
    assert {"SynapseUniverse", "SynapseCinematic"}.issubset(modules)
    plugins = {
        plugin["Name"]: plugin["Enabled"] for plugin in project["Plugins"]
    }
    for plugin in ("OpenXR", "MovieRenderPipeline", "USDImporter", "PixelStreaming2"):
        assert plugins[plugin] is True


def test_contract_lock_pins_routes_and_checked_in_schema_hashes() -> None:
    lock = json.loads(_text(CONTRACT_LOCK))
    assert lock["contract"] == "muse-universe"
    assert lock["schema_major"] == 1
    assert lock["engine_association"] == "5.6"
    assert lock["routes"] == {
        "commands": "/v1/plugins/muse-universe/commands",
        "events": "/v1/plugins/muse-universe/events",
        "snapshot": "/v1/plugins/muse-universe/snapshot",
    }
    for name, record in lock["schemas"].items():
        schema = REPO / record["path"]
        assert schema.name == name
        assert hashlib.sha256(schema.read_bytes()).hexdigest() == record["sha256"]


def test_universe_subsystem_uses_authoritative_routes_cursor_and_resync() -> None:
    source = _text(UNIVERSE / "Private" / "MuseUniverseSubsystem.cpp")
    header = _text(UNIVERSE / "Public" / "MuseUniverseSubsystem.h")
    assert "/v1/plugins/muse-universe/snapshot" in source
    assert "/v1/plugins/muse-universe/events" in source
    assert "/v1/plugins/muse-universe/commands" in source
    assert "actor_id=%s" in source
    assert "ActiveActorId" in source
    assert "LastAcknowledgedCursor" in header
    assert "Authorization" in source
    assert "ExpectedVersion" in source
    assert "CommandId" in source
    assert "RequestResync" in source
    assert "ApplyOnlyIncreasingVersion" in source
    assert "ConnectionGeneration" in source and "RequestGeneration" in source
    assert "bReplayingSnapshotHistory" in source
    assert "LastRealmVersion" in source
    assert "ExpectedEventCount" in source
    assert "ScheduleSnapshotRetry" in source
    assert source.lower().count("owner_authorization") == 1
    assert 'SetStringField(TEXT("owner_authorization")' not in source
    assert "owner phrase" not in source.lower()


def test_typed_records_cover_every_frozen_entity_family() -> None:
    header = _text(UNIVERSE / "Public" / "MuseUniverseTypes.h")
    for record in (
        "FMuseUniverseEvent",
        "FMuseRealmProjection",
        "FMuseStationProjection",
        "FMuseVesselProjection",
        "FMuseVesselModuleProjection",
        "FMusePlayerProjection",
        "FMuseCivilizationProjection",
        "FMuseMembershipProjection",
        "FMuseFleetProjection",
        "FMuseMissionProjection",
        "FMuseBlueprintProjection",
        "FMuseOperationalLedgerProjection",
        "FMuseCreatorLedgerProjection",
        "FMuseWorkspaceLeaseProjection",
        "FMuseReleaseProjection",
        "FMuseCinematicShotProjection",
        "FMuseProvenanceRecord",
    ):
        assert f"struct {record}" in header
    assert "SchemaVersion" in header
    assert "Unknown fields are intentionally ignored" in header


def test_metric_conversion_ring_motion_and_stationary_dock_are_explicit() -> None:
    math_header = _text(UNIVERSE / "Public" / "MuseUniverseMath.h")
    actor_source = _text(UNIVERSE / "Private" / "AtlasCrownActor.cpp")
    assert "MetersToCentimeters" in math_header
    assert "100.0" in math_header
    assert "AtlasSphereDiameterMeters = 210.0" in math_header
    assert "AxialSpineLengthMeters = 1800.0" in math_header
    assert "CrownRingDiameterMeters = 1200.0" in math_header
    assert "CounterRotationPair" in actor_source
    assert "StationaryDockingSpine" in actor_source
    assert "CrownRingA" in actor_source and "CrownRingB" in actor_source


def test_agent_vessel_visuals_are_projection_driven_and_simulation_labeled() -> None:
    source = _text(UNIVERSE / "Private" / "AgentVesselActor.cpp")
    assert "ApplyProjection" in source
    assert "AgentBinding.AgentId" in source
    assert "bSimulationDamage" in source
    assert "SIMULATION" in source
    assert "capability" not in re.sub(r"//.*", "", source).lower() or "SetCapability" not in source


def test_stereo_rig_uses_two_physical_cameras_and_symmetric_offsets() -> None:
    header = _text(CINEMATIC / "Public" / "MuseStereoRigActor.h")
    source = _text(CINEMATIC / "Private" / "MuseStereoRigActor.cpp")
    assert "UCineCameraComponent" in header
    assert "LeftEyeCamera" in header
    assert "RightEyeCamera" in header
    assert "-HalfInteraxialCm" in source
    assert "+HalfInteraxialCm" in source
    assert "65.0" in _text(CINEMATIC / "Public" / "MuseStereoTypes.h")
    for field in (
        "InteraxialMillimeters",
        "ConvergenceDistanceMeters",
        "ZeroParallaxDistanceMeters",
        "DisplayWidthMeters",
        "DepthBudgetPercent",
    ):
        assert field in _text(CINEMATIC / "Public" / "MuseStereoTypes.h")
    assert "SafeGuide190" in source
    assert "SafeGuide143" in source
    assert "SymmetricToeIn" in source
    assert "off-axis stereo requires a verified projection-matrix extension" in source


def test_mrq_jobs_are_native_stereo_deterministic_exr_records() -> None:
    source = _text(
        CINEMATIC / "Private" / "MuseRenderManifestSubsystem.cpp"
    )
    assert "UMoviePipelineQueueEngineSubsystem" in source
    assert "UMoviePipelineImageSequenceOutput_EXR" in source
    assert "{shot_name}" in source
    assert "{frame_number}" in source
    assert "eye_L" in source and "eye_R" in source
    assert "LeftEyeSequence" in source and "RightEyeSequence" in source
    assert "LeftEyeCamera" in source and "RightEyeCamera" in source
    assert "ACES" in source
    assert "SceneRevision" in source
    assert "DeterministicSeed" in source
    assert "FrameHash" in source
    assert "RejectPostConvertedDepthCard" in source
    assert "bPostConvertedDepthCard" in source
    assert "cannot be labeled or queued as native stereo" in source


def test_delivery_config_is_private_fail_safe_and_identity_preserving() -> None:
    engine = _text(UE / "Config" / "DefaultEngine.ini")
    game = _text(UE / "Config" / "DefaultGame.ini")
    scalability = _text(UE / "Config" / "DefaultScalability.ini")
    combined = engine + game + scalability
    assert "bAutoStartPixelStreaming=False" in game
    assert "MUSE_PIXEL_STREAMING_URL" in game
    assert "RequireTlsForExternal=True" in game
    assert "PixelStreamingURL=" not in combined
    assert "Bearer " not in combined
    assert "token=" not in combined.lower()
    for tier in ("Cinema", "Ultra", "High", "Balanced", "Accessible2D"):
        assert tier in scalability
    assert "StationSilhouette=1" in scalability
    assert "r.VolumetricFog=0" in scalability
    assert "SelectedTierReason" in game


def test_new_sources_do_not_embed_secret_values_or_public_stream_endpoints() -> None:
    source = _module_source(UNIVERSE) + _module_source(CINEMATIC)
    forbidden = ("sk-", "ghp_", "bearer test", "wss://example")
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered
    for rejected_key in (
        "api_key",
        "access_token",
        "credential_pool",
        "authorization_phrase",
        "owner_authorization",
    ):
        assert rejected_key in lowered
    assert "ReadBearerToken" not in source
    assert "CreateAuthorizedJsonRequest" in source


def test_automation_specs_cover_runtime_stereo_and_recovery_invariants() -> None:
    universe_tests = _text(
        UNIVERSE / "Private" / "Tests" / "MuseUniverseTests.cpp"
    )
    stereo_tests = _text(
        CINEMATIC / "Private" / "Tests" / "MuseStereoTests.cpp"
    )
    for name in (
        "SchemaRejection",
        "CursorGapResync",
        "StaleEntityVersion",
        "MeterConversion",
        "CounterRotation",
        "StationaryDock",
        "OneActiveVessel",
        "SimulationDamageLabel",
        "NoTokenSerialization",
    ):
        assert name in universe_tests
    for name in (
        "PhysicalSeparation",
        "Convergence",
        "TemporalParity",
        "EyeNaming",
        "FrameParity",
        "MetadataHash",
        "SafeGuides",
        "VerticalAlignment",
        "PostConversionRejection",
    ):
        assert name in stereo_tests
