"""Plane 3 — the champion/challenger diversity archive (scaffold).

The Darwin-Gödel-Machine lesson (arXiv:2505.22954): progress comes from a
*diverse archive* of agent versions with full lineage, where parents are sampled
by score AND editability (stepping stones), not greedy hill-climbing. A
challenger is promoted to champion only through Plane 0's ratchet + 0.55
evaluator gate + charter, and everything stays reversible to any prior member.

This module defines the archive data model; promotion always routes through
:class:`~research_fabric.controller.AutonomyController`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ArchiveMember:
    member_id: str
    parent_id: Optional[str]
    config: dict[str, Any]          # prompt/skill/tool/model knobs
    composite: float
    domain_scores: dict[str, float]
    rollback_handle: str
    created_at: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "parent_id": self.parent_id,
            "config": dict(self.config),
            "composite": self.composite,
            "domain_scores": dict(self.domain_scores),
            "rollback_handle": self.rollback_handle,
            "created_at": self.created_at,
            "note": self.note,
        }


@dataclass
class Archive:
    members: list[ArchiveMember] = field(default_factory=list)

    def add(self, member: ArchiveMember) -> ArchiveMember:
        self.members.append(member)
        return member

    def sample_parent(self, *, rng: Optional[random.Random] = None) -> Optional[ArchiveMember]:
        """Sample a parent weighted by score AND editability (stepping stones).

        Editability is approximated as inverse depth of lineage — shallower
        members are more 'open' to further edits — so we don't collapse onto a
        single greedy peak. Deterministic when ``rng`` is provided.
        """

        if not self.members:
            return None
        r = rng or random.Random()
        depths = {m.member_id: self._depth(m) for m in self.members}
        max_depth = max(depths.values()) or 1
        weights = [
            (m.composite + 0.01) * (1.0 + (max_depth - depths[m.member_id]) / max_depth)
            for m in self.members
        ]
        return r.choices(self.members, weights=weights, k=1)[0]

    def _depth(self, member: ArchiveMember) -> int:
        by_id = {m.member_id: m for m in self.members}
        depth = 0
        cur: Optional[ArchiveMember] = member
        seen: set[str] = set()
        while cur is not None and cur.parent_id and cur.parent_id not in seen:
            seen.add(cur.member_id)
            cur = by_id.get(cur.parent_id)
            depth += 1
        return depth


__all__ = ["ArchiveMember", "Archive"]
