"""Council dispatcher — route a request to the real AOS council registry.

Loads ``skills/aos-enterprise-council/operating-registry/registry.json`` and
selects the members to engage:

* the **active council** (always engaged, capped by the registry's
  ``default_slack_council_max``), and
* the **domain specialists** whose ``when_to_use`` overlaps the request more than
  their ``when_not_to_use`` (deterministic keyword routing).

The result is a :class:`CouncilSession` carrying each engaged member's role,
required inputs/output, verification method, and owner gate — ready to render or
to hand to the model layer member-by-member. No network, no model calls.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "CouncilMember",
    "CouncilSession",
    "dispatch",
    "load_registry",
    "registry_path",
    "roster",
]

_DEFAULT_REL = Path("skills/aos-enterprise-council/operating-registry/registry.json")
_OWNER_PHRASE = "Yes, with authorization."
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "that", "this", "from", "into", "over",
        "are", "use", "used", "when", "not", "any", "all", "via", "per",
        "changes", "change", "tasks", "task", "only",
    }
)


def registry_path() -> Path:
    """Resolve the council registry path (``AOS_REGISTRY_PATH`` overrides)."""
    override = os.getenv("AOS_REGISTRY_PATH")
    if override:
        return Path(override)
    # repo root is parents[3] of this file: aos_council/dispatcher.py →
    # jarvis_prime → hermes_cli → <repo>.
    return Path(__file__).resolve().parents[3] / _DEFAULT_REL


def load_registry(path: Optional[Path] = None) -> dict[str, Any]:
    """Load and parse the council registry JSON (raises on missing/invalid)."""
    p = path or registry_path()
    return json.loads(p.read_text(encoding="utf-8"))


@dataclass
class CouncilMember:
    """One engaged council member, normalized across registry sections."""

    id: str
    kind: str  # "council" | "specialist"
    role: str = ""
    domain: str = ""
    path: str = ""
    when_to_use: str = ""
    required_inputs: list[str] = field(default_factory=list)
    required_output: str = ""
    verification_method: str = ""
    owner_gated: bool = False
    relevance: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "role": self.role,
            "domain": self.domain,
            "path": self.path,
            "when_to_use": self.when_to_use,
            "required_inputs": list(self.required_inputs),
            "required_output": self.required_output,
            "verification_method": self.verification_method,
            "owner_gated": self.owner_gated,
            "relevance": self.relevance,
        }


@dataclass
class CouncilSession:
    """A routed council session for one request."""

    request: str
    council: list[CouncilMember]
    specialists: list[CouncilMember]
    owner_gate_phrase: str = _OWNER_PHRASE

    @property
    def engaged(self) -> list[CouncilMember]:
        return [*self.council, *self.specialists]

    @property
    def owner_gated(self) -> bool:
        return any(m.owner_gated for m in self.engaged)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "council": [m.to_dict() for m in self.council],
            "specialists": [m.to_dict() for m in self.specialists],
            "engaged_count": len(self.engaged),
            "owner_gated": self.owner_gated,
            "owner_gate_phrase": self.owner_gate_phrase,
        }

    def render(self) -> str:
        lines = [f"# AOS council session — {self.request}", ""]
        lines.append(f"**Active council ({len(self.council)}):**")
        lines.extend(f"  - {m.id} — {m.role}" for m in self.council)
        if self.specialists:
            lines.append("")
            lines.append(f"**Domain specialists engaged ({len(self.specialists)}):**")
            for m in self.specialists:
                gate = " ⚠ owner-gated" if m.owner_gated else ""
                lines.append(f"  - {m.id} [{m.domain}]{gate} — {m.required_output}")
        else:
            lines.append("")
            lines.append("**Domain specialists engaged (0):** none matched the request.")
        if self.owner_gated:
            lines.append("")
            lines.append(
                f"⚠ This session engages owner-gated specialists. Execution of their "
                f"gated outputs requires the owner phrase: {self.owner_gate_phrase!r}."
            )
        return "\n".join(lines)


def _keywords(text: str) -> set[str]:
    return {
        w for w in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(w) >= 4 and w not in _STOPWORDS
    }


def _overlap(request_words: set[str], phrase: str) -> int:
    return len(request_words & _keywords(phrase))


def roster(registry: Optional[dict[str, Any]] = None) -> dict[str, list[CouncilMember]]:
    """The full council roster, normalized by section (no request routing)."""
    reg = registry or load_registry()
    return {
        "active_council": [_council_member(m) for m in reg.get("active_council", [])],
        "domain_specialists": [_specialist_member(s) for s in reg.get("domain_specialists", [])],
    }


def _council_member(m: dict[str, Any]) -> CouncilMember:
    return CouncilMember(
        id=str(m.get("id", "")),
        kind="council",
        role=str(m.get("role", "")),
        path=str(m.get("path", "")),
    )


def _specialist_member(s: dict[str, Any], *, relevance: int = 0) -> CouncilMember:
    return CouncilMember(
        id=str(s.get("id", "")),
        kind="specialist",
        domain=str(s.get("domain", "")),
        when_to_use=str(s.get("when_to_use", "")),
        required_inputs=[str(x) for x in s.get("required_inputs", [])],
        required_output=str(s.get("required_output", "")),
        verification_method=str(s.get("verification_method", "")),
        owner_gated=bool(s.get("owner_gate")),
        relevance=relevance,
    )


def dispatch(
    request: str,
    *,
    registry: Optional[dict[str, Any]] = None,
    max_council: Optional[int] = None,
) -> CouncilSession:
    """Route ``request`` to the active council + matching domain specialists."""
    reg = registry or load_registry()
    policies = reg.get("policies", {})
    cap = max_council or int(policies.get("default_slack_council_max", 6))
    phrase = str(policies.get("owner_gate_phrase", _OWNER_PHRASE))

    council = [_council_member(m) for m in reg.get("active_council", [])][:cap]

    req_words = _keywords(request)
    scored: list[CouncilMember] = []
    for s in reg.get("domain_specialists", []):
        use = _overlap(req_words, s.get("when_to_use", ""))
        avoid = _overlap(req_words, s.get("when_not_to_use", ""))
        if use > 0 and use >= avoid:
            scored.append(_specialist_member(s, relevance=use))
    scored.sort(key=lambda m: m.relevance, reverse=True)

    return CouncilSession(
        request=request, council=council, specialists=scored, owner_gate_phrase=phrase
    )
