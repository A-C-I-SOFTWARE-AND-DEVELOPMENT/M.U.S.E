#!/usr/bin/env python3
"""Verify AAA pipeline artifacts and acceptance reports.

Usage::

    python scripts/verify_slice.py <project-root>
    python scripts/verify_slice.py <project-root> --json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_MANIFESTS = (
    "pipeline_manifest.json",
    "manifests/world_manifest.json",
    "manifests/asset_manifest.json",
    "manifests/world_systems.json",
    "checkpoints/pipeline_checkpoint.json",
    "provenance/provenance_index.json",
    "reports/acceptance_report.json",
)

REQUIRED_UE5 = (
    "Config/DefaultEngine.ini",
    "Config/DefaultScalability.ini",
    "Config/WorldPartition.ini",
)


def _verify_asset_manifest(root: Path) -> list[str]:
    failures: list[str] = []
    manifest_path = root / "manifests" / "asset_manifest.json"
    if not manifest_path.is_file():
        return ["missing:manifests/asset_manifest.json"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in data.get("entries", []):
        rel = str(entry.get("path", "")).lstrip("/")
        if not rel:
            failures.append(f"asset_missing_path:{entry.get('asset_id', '?')}")
            continue
        artifact = root / rel
        if not artifact.is_file():
            failures.append(f"asset_path_missing:{rel}")
        validation_ref = str(entry.get("validation_ref", "")).strip()
        blocked_reason = str(entry.get("validation_blocked_reason", "")).strip()
        if validation_ref:
            validation_path = root / validation_ref
            if not validation_path.is_file():
                failures.append(f"validation_ref_missing:{validation_ref}")
        elif not blocked_reason:
            failures.append(
                f"validation_ref_unresolved:{entry.get('asset_id', '?')}:no_ref_or_blocked_reason"
            )
        if entry.get("format") == "stub-json" and entry.get("authoritative") is not False:
            failures.append(f"stub_not_marked_non_authoritative:{entry.get('asset_id', '?')}")
    return failures


def _verify_provenance(root: Path) -> list[str]:
    failures: list[str] = []
    prov_dir = root / "provenance"
    if not prov_dir.is_dir():
        return failures
    for path in prov_dir.glob("*.json"):
        if path.name == "provenance_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("source") == "original" and data.get("safety_status") == "passed":
            if "commercial" in data.get("allowed_uses", []):
                failures.append(f"unsafe_stub_provenance:{path.name}")
    return failures


def _verify_gate_report(root: Path) -> list[str]:
    failures: list[str] = []
    gate_report = root / "validation" / "gate_report.json"
    if not gate_report.is_file():
        return ["missing:validation/gate_report.json"]
    data = json.loads(gate_report.read_text(encoding="utf-8"))
    gates = data.get("gates", [])
    if not gates:
        failures.append("gate_report_empty")
        return failures
    all_passed = all(g.get("passed") for g in gates)
    if data.get("gates_passed") is True and not all_passed:
        failures.append("gate_report_overclaims_gates_passed")
    return failures


def verify(project_root: str | Path) -> dict:
    root = Path(project_root)
    if not root.is_dir():
        return {"ok": False, "reason": "project root does not exist", "failures": ["root_missing"]}

    failures: list[str] = []
    present: list[str] = []

    for rel in REQUIRED_MANIFESTS:
        path = root / rel
        if path.is_file() and path.stat().st_size > 0:
            present.append(rel)
        else:
            failures.append(f"missing:{rel}")

    failures.extend(_verify_asset_manifest(root))
    failures.extend(_verify_provenance(root))
    failures.extend(_verify_gate_report(root))

    ue5_dir = root / "ue5_project"
    if ue5_dir.is_dir():
        uprojects = list(ue5_dir.glob("*.uproject"))
        if not uprojects:
            failures.append("missing:ue5_project/*.uproject")
        else:
            present.append(str(uprojects[0].relative_to(root)))
            mod = uprojects[0].stem
            engine_ini = ue5_dir / "Config" / "DefaultEngine.ini"
            if engine_ini.is_file():
                content = engine_ini.read_text(encoding="utf-8")
                expected_mode = f"/Script/{mod}.{mod}GameMode"
                if expected_mode not in content:
                    failures.append(f"ue5_gamemode_mismatch:expected {expected_mode}")
        for rel in REQUIRED_UE5:
            path = ue5_dir / rel
            if path.is_file() and path.stat().st_size > 0:
                present.append(f"ue5_project/{rel}")
            else:
                failures.append(f"missing:ue5_project/{rel}")
    else:
        failures.append("missing:ue5_project/")

    acceptance_path = root / "reports" / "acceptance_report.json"
    acceptance_data = {}
    if acceptance_path.is_file():
        acceptance_data = json.loads(acceptance_path.read_text(encoding="utf-8"))
        if acceptance_data.get("benchmark_claim") and acceptance_data.get("evidence_complete") is False:
            pass
        elif acceptance_data.get("evidence_complete") and not acceptance_data.get("render_comparisons"):
            failures.append("fabricated:render_evidence")
        if acceptance_data.get("quality_gate_passed") and acceptance_data.get("failures"):
            failures.append("acceptance_overrides_quality_gate")

    previs_path = root / "previs" / "previs_manifest.json"
    if previs_path.is_file():
        previs = json.loads(previs_path.read_text(encoding="utf-8"))
        if previs.get("authoritative"):
            failures.append("previs_marked_authoritative")

    toolchain_path = root / "ue5_project" / "Evidence" / "toolchain-report.json"
    toolchain_passed = False
    if toolchain_path.is_file():
        toolchain = json.loads(toolchain_path.read_text(encoding="utf-8"))
        toolchain_passed = toolchain.get("passed") is True
        if not toolchain_passed:
            failures.append("toolchain_report_failed")
        else:
            present.append("ue5_project/Evidence/toolchain-report.json")

    world_audit_path = root / "ue5_project" / "Evidence" / "world-audit.json"
    world_audit_passed = False
    if world_audit_path.is_file():
        world_audit = json.loads(world_audit_path.read_text(encoding="utf-8"))
        world_audit_passed = world_audit.get("passed") is True
        if not world_audit_passed:
            failures.append("world_audit_failed")
        else:
            present.append("ue5_project/Evidence/world-audit.json")

    gate_report_path = root / "validation" / "gate_report.json"
    gate_data = (
        json.loads(gate_report_path.read_text(encoding="utf-8"))
        if gate_report_path.is_file()
        else {}
    )
    production_ready = bool(
        acceptance_data.get("evidence_complete")
        and acceptance_data.get("quality_gate_passed")
        and gate_data.get("gates_passed")
        and toolchain_passed
        and world_audit_passed
    )

    return {
        "ok": not failures,
        "project_root": str(root),
        "present": present,
        "failures": failures,
        "acceptance": {
            "evidence_complete": acceptance_data.get("evidence_complete"),
            "quality_gate_passed": acceptance_data.get("quality_gate_passed"),
            "benchmark_claim": acceptance_data.get("benchmark_claim", "")[:120],
        },
        "toolchain_passed": toolchain_passed,
        "world_audit_passed": world_audit_passed,
        "production_ready": production_ready,
        "reason": "ok" if not failures else "verification failed",
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    json_out = "--json" in args
    paths = [a for a in args if a != "--json"]
    if len(paths) != 1:
        print(json.dumps({"ok": False, "reason": "usage: verify_slice.py <project-root> [--json]"}))
        return 2
    result = verify(paths[0])
    if json_out:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
