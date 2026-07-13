"""In-memory capability graph.

Holds the typed capability nodes plus optional edges. Provides cheap
lookups by id, type, domain, or tag. The graph is intentionally simple:
no database, no async, no networking. The selector and route explainer
build on top of it.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Iterator, Optional

from hermes_cli.jarvis_prime.capabilities.schemas import (
    Capability,
    CapabilityType,
    Edge,
)


class CapabilityGraph:
    """Read-only registry of capabilities and edges.

    Use :class:`hermes_cli.jarvis_prime.capabilities.indexer.CapabilityIndexer`
    to build one from disk. Tests can also build small in-memory graphs
    directly by passing capabilities to :meth:`add` and then calling
    :meth:`freeze` (or just by passing a list to the constructor).
    """

    def __init__(self, capabilities: Optional[Iterable[Capability]] = None) -> None:
        self._by_id: dict[str, Capability] = {}
        self._by_type: dict[CapabilityType, list[str]] = defaultdict(list)
        self._by_domain: dict[str, list[str]] = defaultdict(list)
        self._edges: list[Edge] = []
        if capabilities:
            for cap in capabilities:
                self.add(cap)

    # -- mutation ---------------------------------------------------------

    def add(self, capability: Capability) -> None:
        if capability.id in self._by_id:
            # Later registrations overwrite earlier ones so the indexer can
            # layer per-skill overrides on top of registry defaults.
            self._remove_indices(self._by_id[capability.id])
        self._by_id[capability.id] = capability
        self._by_type[capability.type].append(capability.id)
        if capability.domain:
            self._by_domain[capability.domain].append(capability.id)

    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)

    def _remove_indices(self, capability: Capability) -> None:
        if capability.id in self._by_type.get(capability.type, []):
            self._by_type[capability.type].remove(capability.id)
        if capability.domain and capability.id in self._by_domain.get(capability.domain, []):
            self._by_domain[capability.domain].remove(capability.id)

    # -- accessors --------------------------------------------------------

    def get(self, capability_id: str) -> Optional[Capability]:
        return self._by_id.get(capability_id)

    def __contains__(self, capability_id: str) -> bool:
        return capability_id in self._by_id

    def __iter__(self) -> Iterator[Capability]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def of_type(self, capability_type: CapabilityType) -> list[Capability]:
        return [self._by_id[i] for i in self._by_type.get(capability_type, [])]

    def in_domain(self, domain: str) -> list[Capability]:
        return [self._by_id[i] for i in self._by_domain.get(domain, [])]

    def search_tags(self, *tags: str) -> list[Capability]:
        """Return capabilities whose tag set contains any of ``tags`` (case-insensitive)."""
        wanted = {t.lower() for t in tags}
        out: list[Capability] = []
        for cap in self._by_id.values():
            cap_tags = {t.lower() for t in cap.tags}
            if wanted & cap_tags:
                out.append(cap)
        return out

    def edges_from(self, source: str) -> list[Edge]:
        return [e for e in self._edges if e.source == source]

    def edges_to(self, target: str) -> list[Edge]:
        return [e for e in self._edges if e.target == target]

    # -- helpers used by the selector ------------------------------------

    @property
    def runnable_council(self) -> list[Capability]:
        """Council members eligible to be activated (non-archive)."""
        return [c for c in self.of_type(CapabilityType.RUNNABLE_AGENT)]

    @property
    def domain_specialists(self) -> list[Capability]:
        return list(self.of_type(CapabilityType.DOMAIN_SPECIALIST))

    @property
    def workers(self) -> list[Capability]:
        return list(self.of_type(CapabilityType.WORKER))

    @property
    def skills(self) -> list[Capability]:
        return list(self.of_type(CapabilityType.SKILL))

    @property
    def personas(self) -> list[Capability]:
        return list(self.of_type(CapabilityType.PERSONA))

    @property
    def product_roles(self) -> list[Capability]:
        return list(self.of_type(CapabilityType.PRODUCT_ROLE))

    @property
    def archive(self) -> list[Capability]:
        return list(self.of_type(CapabilityType.ARCHIVE))


__all__ = ["CapabilityGraph"]
