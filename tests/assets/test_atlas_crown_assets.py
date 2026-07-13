from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "assets" / "atlas-crown"
ATLAS = ROOT / "atlas-crown.usda"
FLAGSHIP = ROOT / "agent-flagship.usda"
PROVENANCE = ROOT / "provenance.json"
MATERIALS = (
    ROOT / "materials" / "atlas-hull.mtlx",
    ROOT / "materials" / "optical-core.mtlx",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_atlas_source_is_metric_original_and_complete() -> None:
    text = ATLAS.read_text(encoding="utf-8")
    assert "#usda 1.0" in text
    assert "metersPerUnit = 1" in text
    assert 'upAxis = "Z"' in text
    for prim in (
        "NeuralCore",
        "AxialSpine",
        "CrownRingA",
        "CrownRingB",
        "CommandSector",
        "ProductionSector",
        "IntelligenceSector",
        "GovernanceSector",
        "SystemsSector",
        "DockingSpine",
        "Radiators",
    ):
        assert f'"{prim}"' in text

    assert "muse:diameterMeters = 210" in text
    assert 'muse:visualStyle = "photoreal-non-cartoony"' in text
    assert "muse:lengthMeters = 1800" in text
    assert text.count("muse:ringDiameterMeters = 1200") == 2
    assert "muse:angularVelocityDegreesPerSecond = 0.25" in text
    assert "muse:angularVelocityDegreesPerSecond = -0.25" in text


def test_atlas_source_declares_depth_lod_collision_and_navigation_contracts() -> None:
    text = ATLAS.read_text(encoding="utf-8")
    for token in (
        'variantSet "lod"',
        '"source"',
        '"interactive"',
        '"proxy"',
        'purpose = "proxy"',
        "navigationClearanceMeters",
        "triangleBudget",
        "sealedTransferBearing",
        "stationaryDock",
        "serviceVehicleScaleReference",
    ):
        assert token in text


def test_flagship_has_aerospace_systems_and_spatial_room_anchors() -> None:
    text = FLAGSHIP.read_text(encoding="utf-8")
    assert "metersPerUnit = 1" in text
    for prim in (
        "PressureHull",
        "ForwardPressureCompartment",
        "AftPressureCompartment",
        "DockingCollar",
        "RCSClusters",
        "RadiatorWings",
        "SensorMast",
        "NavigationLights",
        "CommandBridgeAnchor",
        "NeuralChamberAnchor",
        "SensorLaboratoryAnchor",
        "FabricationBayAnchor",
        "MemoryVaultAnchor",
        "DroneHangarAnchor",
        "EngineeringAnchor",
        "AirlockSecurityAnchor",
    ):
        assert f'"{prim}"' in text
    assert "muse:exteriorAirlockTransform" in text
    assert "muse:interiorAirlockTransform" in text
    assert 'muse:visualStyle = "photoreal-non-cartoony-aerospace"' in text


def test_materialx_is_parseable_local_and_physically_bounded() -> None:
    combined = ""
    surface_names: set[str] = set()
    for material_path in MATERIALS:
        root = ET.parse(material_path).getroot()
        assert root.tag == "materialx"
        assert root.attrib["version"].startswith("1.38")
        text = material_path.read_text(encoding="utf-8")
        combined += text
        assert "http://" not in text
        assert "https://" not in text
        assert "file=" not in text
        surface_names.update(
            node.attrib.get("name", "")
            for node in root.findall("standard_surface")
        )

    assert {
        "SS_BrushedAlloy",
        "SS_LayeredComposite",
        "SS_ThermalBlanket",
        "SS_OpticalGlass",
        "SS_NavigationEmission",
    }.issubset(surface_names)
    for concept in ("micrometeor", "repair_marking", "roughness", "metalness"):
        assert concept in combined.lower()


def test_provenance_is_hash_complete_and_license_clean() -> None:
    data = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    assert data["design"] == "original-muse-atlas-crown"
    assert data["license"] == "MUSE-ORIGINAL-1.0"
    assert data["third_party_geometry"] == []
    assert data["third_party_textures"] == []
    paths = [asset["path"] for asset in data["assets"]]
    assert paths == sorted(paths)
    assert paths == [
        "agent-flagship.usda",
        "atlas-crown.usda",
        "materials/atlas-hull.mtlx",
        "materials/optical-core.mtlx",
    ]
    for asset in data["assets"]:
        assert asset["sha256"] == _sha256(ROOT / asset["path"])
        assert asset["allowed_uses"]
        assert asset["creator"]
        assert asset["transformation_history"]
