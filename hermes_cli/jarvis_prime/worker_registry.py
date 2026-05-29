"""Subscription-aware worker lanes for JARVIS Prime.

Claude Code and Codex are **official local tools**, used through their
own installed CLIs and the owner's existing subscription/session. They
are *worker lanes*, not generic model APIs: JARVIS detects them with
``shutil.which`` (delegated to the existing ``hermes_cli.workers``
adapters), hands them a bounded :class:`HandoffPacket`, and brokers a
single-editor-per-branch policy via ``worker_locks``.

This module is **policy + detection only**:

* It never scrapes credentials, reads session tokens, or asks for API
  keys. Detection is "is the official CLI on PATH?" and nothing more.
* It never bypasses or abuses subscription boundaries — execution goes
  through the official tool's own CLI/session, which the existing
  ``workers/`` adapters own.
* The reviewer lane (Codex) consumes the builder lane's (Claude Code)
  output as patch/review context. It does not edit the same branch in
  parallel — :func:`acquire_branch_for_lane` enforces that with a lease.

The three canonical lanes:

| id                     | tool        | role        | edits branch? |
|------------------------|-------------|-------------|---------------|
| ``claude_code_builder``| claude-code | builder     | yes           |
| ``codex_reviewer``     | codex       | reviewer    | no (read)     |
| ``codex_bounded_fix``  | codex       | bounded fix | yes           |
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


# ---------------------------------------------------------------------------
# Lane definitions (static policy)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkerLane:
    """One external worker lane definition (static policy, no IO)."""

    id: str
    display_name: str
    tool: str  # CLI binary detected via shutil.which
    role: str  # "builder" | "reviewer" | "bounded_fix"
    edits_branch: bool
    description: str
    consumes_from: Optional[str] = None  # lane id whose output this lane reviews
    install_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# The canonical lanes. Claude Code builds; Codex reviews that build, and
# Codex can also run a bounded fix. The reviewer never edits the branch —
# it reads the builder's patch as context (consumes_from).
LANES: tuple[WorkerLane, ...] = (
    WorkerLane(
        id="claude_code_builder",
        display_name="Claude Code Builder",
        tool="claude",
        role="builder",
        edits_branch=True,
        description=(
            "Official Claude Code CLI used as the primary implementation "
            "lane. Builds the change on its assigned branch through the "
            "owner's own Claude Code session."
        ),
        install_hint="https://docs.claude.com/claude-code",
    ),
    WorkerLane(
        id="codex_reviewer",
        display_name="Codex Reviewer",
        tool="codex",
        role="reviewer",
        edits_branch=False,
        description=(
            "Official Codex CLI used as an independent reviewer. Consumes "
            "the Claude Code builder's patch/diff as review context; does "
            "NOT edit the branch in parallel."
        ),
        consumes_from="claude_code_builder",
        install_hint="https://developers.openai.com/codex/cli",
    ),
    WorkerLane(
        id="codex_bounded_fix",
        display_name="Codex Bounded Fix Worker",
        tool="codex",
        role="bounded_fix",
        edits_branch=True,
        description=(
            "Official Codex CLI used for a narrow, bounded fix on a branch "
            "(e.g. address review findings). Holds the branch lease while "
            "it edits so it never collides with the builder lane."
        ),
        install_hint="https://developers.openai.com/codex/cli",
    ),
)

_LANES_BY_ID = {lane.id: lane for lane in LANES}


def lane(lane_id: str) -> WorkerLane:
    """Return the :class:`WorkerLane` for ``lane_id`` or raise KeyError."""
    try:
        return _LANES_BY_ID[lane_id]
    except KeyError as exc:
        raise KeyError(
            f"unknown worker lane {lane_id!r}; known: {sorted(_LANES_BY_ID)}"
        ) from exc


def lane_ids() -> list[str]:
    return list(_LANES_BY_ID)


# ---------------------------------------------------------------------------
# Detection (delegates to the official-tool adapters; no credentials)
# ---------------------------------------------------------------------------


@dataclass
class LaneStatus:
    """Runtime detection result for a lane. Policy/detection only."""

    lane: WorkerLane
    available: bool
    version: Optional[str] = None
    path: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.lane.id,
            "display_name": self.lane.display_name,
            "tool": self.lane.tool,
            "role": self.lane.role,
            "edits_branch": self.lane.edits_branch,
            "consumes_from": self.lane.consumes_from,
            "available": self.available,
            "version": self.version,
            "path": self.path,
            "detail": self.detail,
        }


def _detect_claude() -> tuple[bool, Optional[str], Optional[str], str]:
    """(available, version, path, detail) for the Claude Code CLI."""
    try:
        from hermes_cli.workers import claude_code as _cc

        det = _cc.detect(probe_version=True)
        detail = "; ".join(det.notes) if getattr(det, "notes", None) else ""
        return (
            bool(det.available),
            getattr(det, "version", None),
            getattr(det, "path", None),
            detail,
        )
    except Exception as exc:  # pragma: no cover - defensive
        import shutil

        path = shutil.which("claude")
        return (path is not None), None, path, f"adapter unavailable ({exc})"


def _detect_codex() -> tuple[bool, Optional[str], Optional[str], str]:
    """(available, version, path, detail) for the Codex CLI."""
    try:
        from hermes_cli.workers import codex as _cx

        det = _cx.detect_codex()
        return (
            bool(det.available),
            getattr(det, "version", None),
            getattr(det, "path", None),
            getattr(det, "error", "") or "",
        )
    except Exception as exc:  # pragma: no cover - defensive
        import shutil

        path = shutil.which("codex")
        return (path is not None), None, path, f"adapter unavailable ({exc})"


def detect_lane(
    lane_id: str,
    *,
    claude_detector: Optional[Callable[[], tuple]] = None,
    codex_detector: Optional[Callable[[], tuple]] = None,
) -> LaneStatus:
    """Detect a single lane. Detectors are injectable for tests."""
    the_lane = lane(lane_id)
    if the_lane.tool == "claude":
        avail, version, path, detail = (claude_detector or _detect_claude)()
    elif the_lane.tool == "codex":
        avail, version, path, detail = (codex_detector or _detect_codex)()
    else:  # pragma: no cover - no other tools today
        import shutil

        path = shutil.which(the_lane.tool)
        avail, version, detail = (path is not None), None, ""
    if not avail and not detail:
        detail = f"{the_lane.tool!r} not detected — {the_lane.install_hint}"
    return LaneStatus(
        lane=the_lane, available=avail, version=version, path=path, detail=detail
    )


def detect_lanes(
    *,
    claude_detector: Optional[Callable[[], tuple]] = None,
    codex_detector: Optional[Callable[[], tuple]] = None,
) -> list[LaneStatus]:
    """Detect every canonical lane. Detection-only — no credentials read."""
    return [
        detect_lane(
            lane_id,
            claude_detector=claude_detector,
            codex_detector=codex_detector,
        )
        for lane_id in lane_ids()
    ]


# ---------------------------------------------------------------------------
# Handoff packet format
# ---------------------------------------------------------------------------


@dataclass
class HandoffPacket:
    """The structured packet JARVIS hands to a worker lane.

    Data only — building one performs no IO and executes nothing. Owner-
    gated actions are recorded verbatim and require the canonical
    :data:`AUTHORIZATION_PHRASE` before any downstream executor acts.
    """

    mission: str
    repo_root: str
    branch: str
    risk_class: str
    lane_id: str = ""
    allowed_files: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    owner_gated_actions: list[str] = field(default_factory=list)
    owner_authorization_phrase: str = AUTHORIZATION_PHRASE
    review_context: str = ""  # for reviewer lanes: the builder's patch/diff

    # Default forbidden actions every lane inherits — never override the
    # owner gate, never touch secrets, never push to main.
    _BASE_FORBIDDEN = (
        "do not commit secrets, tokens, or credentials",
        "do not push to or merge the default branch without owner authorization",
        "do not run owner-gated actions without the exact authorization phrase",
        "do not edit files outside allowed_files",
    )

    def __post_init__(self) -> None:
        merged: list[str] = list(self._BASE_FORBIDDEN)
        for item in self.forbidden_actions:
            if item not in merged:
                merged.append(item)
        self.forbidden_actions = merged

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("_BASE_FORBIDDEN", None)
        return data

    def render(self) -> str:
        """Human/agent-readable handoff block."""

        def _bullets(items: list[str]) -> str:
            return "\n".join(f"  - {i}" for i in items) if items else "  (none)"

        lines = [
            f"HANDOFF PACKET → {self.lane_id or '(unassigned lane)'}",
            f"Mission: {self.mission}",
            f"Repo root: {self.repo_root}",
            f"Branch: {self.branch}",
            f"Risk class: {self.risk_class}",
            "Allowed files:",
            _bullets(self.allowed_files),
            "Forbidden actions:",
            _bullets(self.forbidden_actions),
            "Acceptance criteria:",
            _bullets(self.acceptance_criteria),
            "Verification commands:",
            _bullets(self.verification_commands),
            f"Rollback plan: {self.rollback_plan or '(none provided)'}",
            "Owner-gated actions:",
            _bullets(self.owner_gated_actions),
        ]
        if self.owner_gated_actions:
            lines.append(
                f"Owner authorization phrase required: {self.owner_authorization_phrase!r}"
            )
        if self.review_context:
            lines.append("Review context (builder output):")
            lines.append(self.review_context)
        return "\n".join(lines)


def build_handoff_packet(
    *,
    mission: str,
    repo_root: str,
    branch: str,
    risk_class: str = "RC1",
    lane_id: str = "claude_code_builder",
    allowed_files: Optional[list[str]] = None,
    forbidden_actions: Optional[list[str]] = None,
    acceptance_criteria: Optional[list[str]] = None,
    verification_commands: Optional[list[str]] = None,
    rollback_plan: str = "",
    owner_gated_actions: Optional[list[str]] = None,
    review_context: str = "",
) -> HandoffPacket:
    """Construct a :class:`HandoffPacket` with the lane validated."""
    if lane_id:
        lane(lane_id)  # validate; raises KeyError on unknown lane
    return HandoffPacket(
        mission=mission,
        repo_root=repo_root,
        branch=branch,
        risk_class=risk_class,
        lane_id=lane_id,
        allowed_files=list(allowed_files or []),
        forbidden_actions=list(forbidden_actions or []),
        acceptance_criteria=list(acceptance_criteria or []),
        verification_commands=list(verification_commands or []),
        rollback_plan=rollback_plan,
        owner_gated_actions=list(owner_gated_actions or []),
        review_context=review_context,
    )


# ---------------------------------------------------------------------------
# Branch brokering — enforce single-editor-per-branch across lanes
# ---------------------------------------------------------------------------


def acquire_branch_for_lane(
    lane_id: str,
    branch: str,
    *,
    locks_dir=None,
    ttl_seconds: Optional[int] = None,
    now=None,
):
    """Acquire the branch edit-lease for an editing lane.

    Reviewer lanes (``edits_branch=False``) never take an edit lease —
    they consume the builder's output read-only — so this returns
    ``None`` for them. Editing lanes acquire a lease under the lane's
    tool; a different tool holding a live lease raises
    :class:`worker_locks.BranchLockedError`, which is exactly the
    "Claude Code and Codex must not edit the same branch at once" rule.
    """
    from hermes_cli.jarvis_prime import worker_locks as _wl

    the_lane = lane(lane_id)
    if not the_lane.edits_branch:
        return None
    kwargs: dict[str, Any] = {"locks_dir": locks_dir, "now": now, "note": lane_id}
    if ttl_seconds is not None:
        kwargs["ttl_seconds"] = ttl_seconds
    # The lease is keyed on the tool, not the lane, so the builder lane
    # (claude) and a codex fix lane are recognised as different editors.
    return _wl.acquire_branch_lease(branch, the_lane.tool, **kwargs)


def release_branch_for_lane(lane_id: str, branch: str, *, locks_dir=None) -> bool:
    """Release an editing lane's branch lease."""
    from hermes_cli.jarvis_prime import worker_locks as _wl

    the_lane = lane(lane_id)
    if not the_lane.edits_branch:
        return False
    return _wl.release_branch_lease(branch, the_lane.tool, locks_dir=locks_dir)


__all__ = [
    "LANES",
    "HandoffPacket",
    "LaneStatus",
    "WorkerLane",
    "acquire_branch_for_lane",
    "build_handoff_packet",
    "detect_lane",
    "detect_lanes",
    "lane",
    "lane_ids",
    "release_branch_for_lane",
]
