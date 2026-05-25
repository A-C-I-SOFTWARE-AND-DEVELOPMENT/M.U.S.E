"""Verify the jarvis_prime package imports cleanly and exports WorkPacket."""

from __future__ import annotations

import importlib


def test_package_imports_cleanly():
    module = importlib.import_module("hermes_cli.jarvis_prime")
    assert module is not None


def test_workpacket_export():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(mission="probe")
    assert packet.mission == "probe"


def test_validation_finding_export():
    from hermes_cli.jarvis_prime import WorkPacketValidationFinding

    finding = WorkPacketValidationFinding(
        field="mission", code="missing_required_field", message="m"
    )
    assert finding.severity == "error"


def test_risk_classes_export():
    from hermes_cli.jarvis_prime import RISK_CLASSES

    assert RISK_CLASSES == ("RC0", "RC1", "RC2", "RC3", "RC4")


def test_all_exports_match_dunder_all():
    import hermes_cli.jarvis_prime as pkg

    assert set(pkg.__all__) == {
        "RISK_CLASSES",
        "WorkPacket",
        "WorkPacketValidationFinding",
    }
