"""Adapter ABC + provider registry.

Each adapter handles one stage of production (e.g. video generation,
3D mesh synthesis, voice cloning). The registry picks the best adapter
for a (capability, quality) tuple based on available API keys + cost
budget.

Adapters MUST be safe to call without keys — they fall back to stub
manifest output so the full pipeline DAG can dry-run end-to-end.
"""
from __future__ import annotations

import abc
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent.studio.types import Provider, Quality, StageResult


class Adapter(abc.ABC):
    """Base class for a single generative-AI capability."""

    capability: str = ""    # e.g. "video", "mesh3d", "voice", "music"
    provider: Provider = Provider.STUB
    requires_env: List[str] = []   # env vars that must be set for real calls
    est_unit_cost_usd: float = 0.0  # rough per-call cost

    def available(self) -> bool:
        """True if real API keys are present; else stub mode."""
        return all(os.environ.get(k) for k in self.requires_env)

    def run(self, prompt: str, workdir: Path, **kwargs) -> StageResult:
        t0 = time.perf_counter()
        try:
            if self.available():
                artifacts, notes = self._real(prompt, workdir, **kwargs)
                status = "ok"
                cost = self._estimate_cost(**kwargs)
            else:
                artifacts, notes = self._stub(prompt, workdir, **kwargs)
                status = "stubbed"
                cost = 0.0
        except Exception as exc:
            return StageResult(
                stage=self.capability,
                provider=self.provider,
                status="failed",
                duration_s=time.perf_counter() - t0,
                notes=f"{type(exc).__name__}: {exc}",
            )
        return StageResult(
            stage=self.capability,
            provider=self.provider,
            status=status,
            artifacts=artifacts,
            duration_s=time.perf_counter() - t0,
            est_cost_usd=cost,
            notes=notes,
        )

    def _estimate_cost(self, **kwargs) -> float:
        return self.est_unit_cost_usd * kwargs.get("units", 1)

    def _stub(self, prompt: str, workdir: Path, **kwargs) -> tuple[List[str], str]:
        """Default stub — writes a JSON manifest describing what *would* be made."""
        workdir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "capability": self.capability,
            "provider": self.provider.value,
            "prompt": prompt[:400],
            "kwargs": {k: str(v)[:200] for k, v in kwargs.items()},
            "would_cost_usd": self._estimate_cost(**kwargs),
            "stub": True,
        }
        fname = f"{self.capability}_{int(time.time()*1000)}.json"
        out = workdir / fname
        out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return [str(out)], f"stub manifest ({self.provider.value})"

    @abc.abstractmethod
    def _real(self, prompt: str, workdir: Path, **kwargs) -> tuple[List[str], str]:
        """Actual API call. Override in concrete adapter. Return (artifacts, notes)."""
        raise NotImplementedError


# ── Registry ────────────────────────────────────────────────────────

class AdapterRegistry:
    """Picks the best adapter for a capability based on Quality + availability."""

    def __init__(self) -> None:
        self._by_capability: Dict[str, List[Adapter]] = {}

    def register(self, adapter: Adapter, priority: int = 50) -> None:
        bucket = self._by_capability.setdefault(adapter.capability, [])
        bucket.append(adapter)
        # Keep most preferred (higher priority + available) first
        bucket.sort(key=lambda a: (-int(a.available()), -priority, a.est_unit_cost_usd))

    def pick(
        self,
        capability: str,
        quality: Quality = Quality.PREVIZ,
        prefer: Optional[Provider] = None,
    ) -> Optional[Adapter]:
        bucket = self._by_capability.get(capability, [])
        if not bucket:
            return None
        if prefer:
            for a in bucket:
                if a.provider == prefer:
                    return a
        # Prefer available real adapters; fall back to first stub
        for a in bucket:
            if a.available():
                return a
        return bucket[0]

    def all_for(self, capability: str) -> List[Adapter]:
        return list(self._by_capability.get(capability, []))


# Global default registry — populated by adapters/__init__.py
default_registry = AdapterRegistry()
