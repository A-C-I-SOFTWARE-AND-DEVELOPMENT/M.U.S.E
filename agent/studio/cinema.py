"""Cinema master packaging for native-stereo, ACES, audio, and QC evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from .render_manifest import RenderManifest
from .stereo import StereoQcResult, StereoShot


@dataclass(frozen=True)
class CinemaPackage:
    root: Path
    shot_id: str
    passed: bool
    render_failures: tuple[str, ...]
    stereo_failures: tuple[str, ...]
    deliverables: Mapping[str, str]
    checksums: Mapping[str, str]
    imax_certified: bool = False
    external_certification: str = "required"


class CinemaPackager:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def create(
        self,
        shot: StereoShot,
        renders: RenderManifest,
        qc: StereoQcResult,
        *,
        aces_reference: str = "ACES 2.0",
        audio_manifest: Mapping[str, object] | None = None,
        editorial_manifest: Mapping[str, object] | None = None,
        rights_manifest: Mapping[str, object] | None = None,
    ) -> CinemaPackage:
        package_root = self.root / (shot.shot_id or "shot")
        package_root.mkdir(parents=True, exist_ok=True)
        render_validation = renders.validate()
        missing_outputs: list[str] = []
        exr_root = package_root / "OpenEXR"
        for record in renders.latest():
            source = Path(record.output_path) if record.output_path else None
            if source is None or not source.is_file() or source.suffix.lower() != ".exr":
                missing_outputs.append(f"{record.shot_id}:{record.frame}:{record.eye}")
                continue
            destination = exr_root / record.eye / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        render_failures = list(render_validation.failures)
        if missing_outputs:
            render_failures.append("missing_openexr_output")
        stereo_failures = tuple(issue.code for issue in qc.issues)
        manifests = {
            "stereo-shot.json": asdict(shot),
            "render-manifest.json": [asdict(record) for record in renders.latest()],
            "stereo-qc.json": asdict(qc),
            "aces.json": {"config": aces_reference, "version": "2", "external_review": True},
            "audio-spatial-mix.json": dict(audio_manifest or {}),
            "editorial-conform.json": dict(editorial_manifest or {}),
            "rights.json": dict(rights_manifest or {}),
            "archive.json": {
                "shot_id": shot.shot_id,
                "eyes": ["left", "right"],
                "imax_certified": False,
                "external_certification": "required",
            },
        }
        deliverables: dict[str, str] = {}
        for name, payload in manifests.items():
            path = package_root / name
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            deliverables[name] = str(path)
        checksums = self._inventory(package_root)
        checksum_path = package_root / "checksums.sha256"
        checksum_path.write_text(
            "".join(f"{digest.removeprefix('sha256:')}  {path}\n" for path, digest in checksums.items()),
            encoding="utf-8",
        )
        deliverables["checksums.sha256"] = str(checksum_path)
        rights_status = str((rights_manifest or {}).get("status", "")).lower()
        rights_passed = rights_status in {"passed", "verified", "approved"}
        passed = not render_failures and not stereo_failures and rights_passed
        return CinemaPackage(
            root=package_root,
            shot_id=shot.shot_id,
            passed=passed,
            render_failures=tuple(dict.fromkeys(render_failures)),
            stereo_failures=stereo_failures,
            deliverables=deliverables,
            checksums=checksums,
        )

    @staticmethod
    def _inventory(root: Path) -> dict[str, str]:
        inventory: dict[str, str] = {}
        for path in sorted((item for item in root.rglob("*") if item.is_file())):
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            inventory[path.relative_to(root).as_posix()] = "sha256:" + digest.hexdigest()
        return inventory


__all__ = ["CinemaPackage", "CinemaPackager"]
