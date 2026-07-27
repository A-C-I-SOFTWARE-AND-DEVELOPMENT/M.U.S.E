"""Load niche YAML specs from disk."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import json
import logging

from hermes_cli.jarvis_prime.niches.schema import NicheSpec

logger = logging.getLogger(__name__)

_PKG = Path(__file__).resolve().parent
SPECS_DIR = _PKG / "specs"
RUNTIME_REGISTRY = _PKG / "runtime_registry.json"


def niches_dir() -> Path:
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    return SPECS_DIR


def _read_yaml(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping")
    return data


def load_niche(niche_id: str) -> Optional[NicheSpec]:
    path = niches_dir() / f"{niche_id}.yaml"
    if not path.exists():
        # also try slash→dot filename
        alt = niches_dir() / f"{niche_id.replace('.', '_')}.yaml"
        path = alt if alt.exists() else path
    if not path.exists():
        return None
    try:
        return NicheSpec.from_dict(_read_yaml(path))
    except Exception as exc:
        logger.warning("failed to load niche %s: %s", path, exc)
        return None


def load_all_niches() -> list[NicheSpec]:
    """Load every *.yaml under specs/."""
    out: list[NicheSpec] = []
    root = niches_dir()
    for path in sorted(root.glob("*.yaml")):
        try:
            spec = NicheSpec.from_dict(_read_yaml(path))
            out.append(spec)
        except Exception as exc:
            logger.warning("skip niche %s: %s", path.name, exc)
    return out


def write_niche(spec: NicheSpec) -> Path:
    """Persist a niche YAML (overwrites)."""
    import yaml

    path = niches_dir() / f"{spec.id}.yaml"
    path.write_text(
        yaml.safe_dump(spec.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def update_runtime_registry(spec: NicheSpec, *, forged: bool = False) -> Path:
    """Soft-register into niches/runtime_registry.json (not AOS curated)."""
    RUNTIME_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"version": "1", "niches": []}
    if RUNTIME_REGISTRY.exists():
        try:
            data = json.loads(RUNTIME_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    niches = list(data.get("niches") or [])
    niches = [n for n in niches if n.get("id") != spec.id]
    niches.append(
        {
            "id": spec.id,
            "domain": spec.domain,
            "description": spec.description or spec.system[:120],
            "forged": forged,
            "path": f"specs/{spec.id}.yaml",
        }
    )
    data["niches"] = niches
    data["count"] = len(niches)
    RUNTIME_REGISTRY.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return RUNTIME_REGISTRY
