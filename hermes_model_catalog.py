"""Loader + validator for the pre-wired model catalog.

The catalog (``config/model-catalog.yaml``) enumerates every OSS model
Hermes ships ready to go, the provider plugin that serves each one, and
the environment key that unlocks it. This module turns that YAML into a
typed view and answers the two questions the CLI / app / ``hermes
doctor`` actually ask:

* *Which models are READY right now?* — i.e. their provider's env key is
  present (local providers are always ready; connectivity is checked
  separately by the daemon).
* *What's the best default for a tier?* — the first READY model in the
  tier's preference list.

It deliberately does **no** network I/O and never reads secret *values*
— only whether a key is set — so it is safe to import anywhere and easy
to unit-test.

Installed-vs-catalog reconciliation (2026-06-27)
------------------------------------------------
The ``ollama-local`` provider block in ``config/model-catalog.yaml`` was
reconciled against ``ollama show`` on the reference box (RTX 5070 Laptop,
8GB VRAM): the phantom ``gemma4-26b`` / ``gemma4-31b`` / ``llama3.2``
entries were removed, and the six models actually installed there
(``qwen3-coder-30b``, ``gpt-oss-20b``, ``gemma4-12b``, ``qwen3_5-9b``,
``qwythos-mythos-9b``, ``ornith-9b``) were added with a CONSERVATIVE
32768-token context floor — the native 256K–1M windows are unreachable at
8GB. ``defaults.fast`` / ``defaults.local`` were repointed at the
installed-first ordering (the removed ``llama3.2`` ref no longer dangles).
``gemma4-e2b`` / ``gemma4-e4b`` stay listed as downloadable-on-other-machines
candidates but are not installed here. This module's behavior is unchanged;
only the data it loads was reconciled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "config" / "model-catalog.yaml"


@dataclass(frozen=True)
class CatalogModel:
    """One selectable model. ``ref`` is the stable ``provider/id`` handle."""

    provider: str
    id: str
    model: str
    family: str
    params_b: float
    context: int
    tags: tuple[str, ...]
    requires_env: str | None
    plugin: str
    base_url: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.provider}/{self.id}"

    def is_ready(self, env: dict[str, str] | None = None) -> bool:
        """READY when no key is required (local) or the key is set."""
        if self.requires_env is None:
            return True
        source = env if env is not None else os.environ
        return bool(source.get(self.requires_env, "").strip())


@dataclass(frozen=True)
class MediaProvider:
    kind: str  # "image" | "video"
    provider: str
    requires_env: str | None
    plugin: str
    models: tuple[str, ...]

    def is_ready(self, env: dict[str, str] | None = None) -> bool:
        if self.requires_env is None:
            return True
        source = env if env is not None else os.environ
        return bool(source.get(self.requires_env, "").strip())


@dataclass
class ModelCatalog:
    version: int
    models: list[CatalogModel] = field(default_factory=list)
    defaults: dict[str, list[str]] = field(default_factory=dict)
    media: list[MediaProvider] = field(default_factory=list)

    # --- lookups -----------------------------------------------------------

    def by_ref(self, ref: str) -> CatalogModel | None:
        return next((m for m in self.models if m.ref == ref), None)

    def ready_models(self, env: dict[str, str] | None = None) -> list[CatalogModel]:
        return [m for m in self.models if m.is_ready(env)]

    def models_for_provider(self, provider: str) -> list[CatalogModel]:
        return [m for m in self.models if m.provider == provider]

    def default_for(
        self, tier: str, env: dict[str, str] | None = None
    ) -> CatalogModel | None:
        """First READY model in the tier's preference list, else None."""
        for ref in self.defaults.get(tier, []):
            model = self.by_ref(ref)
            if model is not None and model.is_ready(env):
                return model
        return None

    def ready_media(
        self, kind: str, env: dict[str, str] | None = None
    ) -> list[MediaProvider]:
        return [m for m in self.media if m.kind == kind and m.is_ready(env)]

    def readiness_report(self, env: dict[str, str] | None = None) -> dict[str, Any]:
        """Compact summary for ``hermes doctor`` / diagnostics screens."""
        ready = self.ready_models(env)
        return {
            "models_total": len(self.models),
            "models_ready": len(ready),
            "ready_refs": [m.ref for m in ready],
            "missing_env": sorted({
                m.requires_env
                for m in self.models
                if m.requires_env and not m.is_ready(env)
            }),
            "defaults": {
                tier: (
                    default.ref if (default := self.default_for(tier, env)) else None
                )
                for tier in self.defaults
            },
            "media_ready": {
                kind: [mp.provider for mp in self.ready_media(kind, env)]
                for kind in ("image", "video")
            },
        }


def load_catalog(path: str | Path | None = None) -> ModelCatalog:
    """Parse and validate the catalog YAML into a :class:`ModelCatalog`.

    Raises ``ValueError`` on a malformed catalog (duplicate refs, missing
    required model fields) so a typo fails loudly rather than silently
    dropping a model.
    """
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}

    version = int(raw.get("version", 0))
    models: list[CatalogModel] = []
    seen_refs: set[str] = set()

    providers = raw.get("providers", {}) or {}
    for provider_name, pdata in providers.items():
        pdata = pdata or {}
        requires_env = pdata.get("requires_env")
        plugin = pdata.get("plugin", "")
        base_url = pdata.get("base_url")
        for entry in pdata.get("models", []) or []:
            _require_fields(provider_name, entry, ("id", "model", "family"))
            model = CatalogModel(
                provider=provider_name,
                id=str(entry["id"]),
                model=str(entry["model"]),
                family=str(entry["family"]),
                params_b=float(entry.get("params_b", 0) or 0),
                context=int(entry.get("context", 0) or 0),
                tags=tuple(entry.get("tags", []) or []),
                requires_env=requires_env,
                plugin=plugin,
                base_url=base_url,
            )
            if model.ref in seen_refs:
                raise ValueError(f"Duplicate model ref in catalog: {model.ref}")
            seen_refs.add(model.ref)
            models.append(model)

    media: list[MediaProvider] = []
    media_raw = raw.get("media", {}) or {}
    for kind in ("image", "video"):
        for entry in media_raw.get(kind, []) or []:
            media.append(
                MediaProvider(
                    kind=kind,
                    provider=str(entry["provider"]),
                    requires_env=entry.get("requires_env"),
                    plugin=str(entry.get("plugin", "")),
                    models=tuple(entry.get("models", []) or []),
                )
            )

    defaults = {
        tier: [str(r) for r in refs]
        for tier, refs in (raw.get("defaults", {}) or {}).items()
    }

    catalog = ModelCatalog(
        version=version, models=models, defaults=defaults, media=media
    )
    _validate_defaults(catalog)
    return catalog


def _require_fields(
    provider: str, entry: dict[str, Any], fields: tuple[str, ...]
) -> None:
    missing = [f for f in fields if not entry.get(f)]
    if missing:
        raise ValueError(
            f"Catalog model under provider '{provider}' is missing fields {missing}: {entry!r}"
        )


def _validate_defaults(catalog: ModelCatalog) -> None:
    """Every default ref must resolve to a real model."""
    for tier, refs in catalog.defaults.items():
        for ref in refs:
            if catalog.by_ref(ref) is None:
                raise ValueError(
                    f"defaults.{tier} references unknown model '{ref}' (not in catalog)"
                )


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    import json

    cat = load_catalog()
    print(json.dumps(cat.readiness_report(), indent=2))
