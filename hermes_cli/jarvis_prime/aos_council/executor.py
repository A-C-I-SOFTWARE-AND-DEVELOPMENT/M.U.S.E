"""Council execution — run each engaged member through the model layer.

The dispatcher (:mod:`.dispatcher`) *routes* a request to council members; this
module *executes* them: it builds a per-member prompt from the member's persona
(``path``) + the request + the member's required output, runs it through an
injected ``Runner`` (``prompt -> completion``), and has the director synthesize a
final summary. The runner is injected so this is fully testable; the default
runner reuses the local Gemma runner (:func:`build_gemma_runner`) and returns
``None`` when no local model is available — in which case execution degrades to a
deterministic, registry-templated deliberation rather than failing.

This is the opt-in "next layer" over routing: ``council dispatch --execute``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .dispatcher import CouncilMember, CouncilSession, registry_path

Runner = Callable[[str], str]

# Persona files (``path``) are relative to the council skill root, which is the
# registry file's grandparent (operating-registry/registry.json → skill root).
_SKILL_ROOT_ENV = "AOS_COUNCIL_ROOT"


def _skill_root() -> Path:
    override = os.getenv(_SKILL_ROOT_ENV)
    if override:
        return Path(override)
    return registry_path().resolve().parents[1]


def _load_persona(member: CouncilMember) -> str:
    if not member.path:
        return ""
    try:
        return (_skill_root() / member.path).read_text(encoding="utf-8")
    except OSError:
        return ""


@dataclass
class MemberResult:
    id: str
    kind: str
    role: str
    domain: str
    owner_gated: bool
    output: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "role": self.role,
            "domain": self.domain,
            "owner_gated": self.owner_gated,
            "output": self.output,
        }


@dataclass
class CouncilDeliberation:
    request: str
    results: list[MemberResult] = field(default_factory=list)
    summary: str = ""
    owner_gated: bool = False
    executed: bool = False  # True ⇒ a real model runner produced the outputs

    def to_dict(self) -> dict:
        return {
            "request": self.request,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "owner_gated": self.owner_gated,
            "executed": self.executed,
        }

    def render(self) -> str:
        lines = [f"# AOS council deliberation — {self.request}", ""]
        if not self.executed:
            lines.append("_(no model configured — deterministic outline; set up a "
                         "local Gemma runner or pass a runner to execute for real)_")
            lines.append("")
        for r in self.results:
            gate = " ⚠ owner-gated" if r.owner_gated else ""
            head = r.domain or r.role or r.kind
            lines.append(f"## {r.id} [{head}]{gate}")
            lines.append(r.output)
            lines.append("")
        lines.append("## synthesis (council-director)")
        lines.append(self.summary)
        return "\n".join(lines)


def default_runner() -> Optional[Runner]:
    """The default member runner: a local Gemma model when available, else None."""
    try:
        from hermes_cli.jarvis_prime.gemma_runner import build_gemma_runner

        return build_gemma_runner()
    except Exception:  # pragma: no cover - defensive (stripped install)
        return None


def _member_prompt(member: CouncilMember, request: str, persona: str) -> str:
    parts = [
        f"You are the {member.id} on the AOS Enterprise Council.",
        f"Role/domain: {member.domain or member.role}.",
    ]
    if persona:
        parts.append("Persona / operating spec:\n" + persona.strip()[:4000])
    if member.required_output:
        parts.append(f"Required output: {member.required_output}")
    if member.verification_method:
        parts.append(f"Verification: {member.verification_method}")
    parts.append(f"\nRequest:\n{request}\n\nRespond with your council contribution.")
    return "\n\n".join(parts)


def _deterministic_output(member: CouncilMember) -> str:
    target = member.required_output or member.role or "a council contribution"
    return f"(would produce: {target})"


def _synthesize(
    request: str, results: list[MemberResult], runner: Optional[Runner]
) -> str:
    if runner is None:
        engaged = ", ".join(r.id for r in results)
        gated = [r.id for r in results if r.owner_gated]
        tail = f" Owner-gated members: {', '.join(gated)}." if gated else ""
        return f"Routed {len(results)} members ({engaged}).{tail}"
    body = "\n\n".join(f"[{r.id}] {r.output}" for r in results)
    prompt = (
        "You are the council-director. Synthesize the members' contributions below "
        f"into a single decision/answer for the request: {request}\n\n{body}\n\n"
        "Give the final synthesis."
    )
    try:
        return runner(prompt).strip()
    except Exception as exc:  # pragma: no cover - defensive
        return f"(synthesis failed: {exc})"


def execute(
    session: CouncilSession,
    *,
    runner: Optional[Runner] = None,
    persona_loader: Optional[Callable[[CouncilMember], str]] = None,
) -> CouncilDeliberation:
    """Run each engaged member through ``runner`` and synthesize a deliberation.

    ``runner`` defaults to the local Gemma runner; when no runner is available the
    deliberation is a deterministic outline (``executed=False``) — never an error.
    """
    run = runner if runner is not None else default_runner()
    load = persona_loader or _load_persona
    results: list[MemberResult] = []
    for m in session.engaged:
        if run is not None:
            persona = load(m)
            try:
                output = run(_member_prompt(m, session.request, persona)).strip()
            except Exception as exc:  # pragma: no cover - defensive
                output = f"(member run failed: {exc})"
        else:
            output = _deterministic_output(m)
        results.append(
            MemberResult(
                id=m.id,
                kind=m.kind,
                role=m.role,
                domain=m.domain,
                owner_gated=m.owner_gated,
                output=output,
            )
        )
    summary = _synthesize(session.request, results, run)
    return CouncilDeliberation(
        request=session.request,
        results=results,
        summary=summary,
        owner_gated=session.owner_gated,
        executed=run is not None,
    )
