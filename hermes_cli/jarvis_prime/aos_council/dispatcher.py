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

Unification layer (gap analysis G03)
-------------------------------------
The repo historically carried *two* independent pre-dispatch planners that never
met:

* the **Navigator** (``hermes_cli.jarvis_prime.navigation.navigator``) answers
  *where* to edit — issue localization, ranked edit sites, tests to run — and
  emits a ``navigation_decision`` ledger record; and
* this **council Dispatcher**, which answers *who* engages — routing to council
  members — but is registry-specific and speaks no task-queue contract.

The gap analysis flags the navigator/planner as "not unified" and the
dispatcher/task queue as "not generalized". Rather than introduce a parallel
architecture, this module is **extended in place** with:

* a generalized :class:`TaskQueue` matching the ``queue.json`` contract
  (``pending`` / ``in_flight`` / ``completed`` / ``failed``) from
  ``docs/orchestration/hermes-orchestration-pipeline.md``, so the dispatcher is
  no longer registry-only — it emits dispatchable tasks any worker can consume;
* a unified :class:`DispatchPlan` that composes a :class:`CouncilSession`
  (who) with an optional :class:`~hermes_cli.jarvis_prime.navigation.navigator.NavigationResult`
  (where) and the task queue, recording one ledger decision instead of two; and
* :func:`unified_dispatch`, the single entry point that ties navigator +
  dispatcher together.

The original :func:`dispatch` / :class:`CouncilSession` surface is unchanged
(existing callers and tests are unaffected); ``unified_dispatch`` is the
additive, composable extension.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # avoid a runtime import cycle (navigation → jarvis_prime …)
    from hermes_cli.jarvis_prime.navigation.navigator import NavigationResult

__all__ = [
    "CouncilMember",
    "CouncilSession",
    "DispatchPlan",
    "Task",
    "TaskQueue",
    "dispatch",
    "load_registry",
    "registry_path",
    "roster",
    "unified_dispatch",
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


# Minimum council floor when the (default-off) effort cap is applied. The cap
# may never shrink an engaged council to zero members: at least this many of the
# highest-priority core members are always preserved so a capped session still
# carries essential decision coverage. Only in force when the flag is enabled.
_EFFORT_CAP_FLOOR = 1


def _effort_cap_enabled(registry: Optional[dict[str, Any]]) -> bool:
    """Whether the (default-OFF) effort-class council cap is enabled.

    Opt-in only, mirroring the merged effort-class stamping's additive pattern.
    Resolution order (first True wins), all defaulting to disabled:

    * env ``MUSE_EFFORT_CAP`` set to a truthy value (``1``/``true``/``yes``/``on``);
    * ``registry["policies"]["effort_cap"]["enabled"] is True`` — Mapping-guarded
      so a malformed / absent policy block can never raise.

    Any error while reading the flag resolves to ``False`` (fail-open toward the
    current, uncapped behavior).
    """
    try:
        env = os.getenv("MUSE_EFFORT_CAP")
        # A present-but-empty env value falls through here (empty string is not a
        # truthy token) and defers to the registry policy below — first True wins.
        if env is not None and env.strip().lower() in {"1", "true", "yes", "on"}:
            return True
        policies = (registry or {}).get("policies")
        if not isinstance(policies, dict):
            return False
        effort_cap = policies.get("effort_cap")
        if not isinstance(effort_cap, dict):
            return False
        return effort_cap.get("enabled") is True
    except Exception:
        return False


def _apply_effort_cap(
    council: list["CouncilMember"],
    specialists: list["CouncilMember"],
    effort_class: Optional[str],
) -> tuple[list["CouncilMember"], list["CouncilMember"]]:
    """Bound the assembled council to what ``effort_class`` permits.

    Deterministic, never-raise, and cap-only (never enlarges). The cap is a
    ceiling on the *total* engaged members (council + specialists). Drop order —
    most-marginal first — is:

    1. drop the lowest-relevance domain specialists (they are already sorted
       descending by relevance, so we trim from the tail);
    2. only if the council alone still exceeds the ceiling, trim the
       lowest-priority tail of the active council — but never below
       :data:`_EFFORT_CAP_FLOOR` (the highest-priority core members are always
       preserved).

    On any error, or when ``effort_class`` is unknown / imposes no ceiling
    (E4/E5), the inputs are returned unchanged (fail-open toward current
    behavior). ``cap_council_size`` itself is the merged, tested primitive — it
    is only *consulted* here, never modified.
    """
    try:
        if not effort_class:
            return council, specialists
        from hermes_cli.jarvis_prime.effort_class import EffortClass, cap_council_size

        try:
            cls = EffortClass(effort_class)
        except ValueError:
            return council, specialists

        requested = len(council) + len(specialists)
        ceiling = cap_council_size(cls, requested)
        # E4/E5 impose no ceiling → cap_council_size returns the request as-is.
        if ceiling >= requested:
            return council, specialists

        # Enforce a sane floor so essential core members are never all dropped.
        if council:
            ceiling = max(ceiling, _EFFORT_CAP_FLOOR)
        if ceiling >= requested:
            return council, specialists

        # Drop most-marginal specialists first (tail of the relevance-sorted list).
        keep_specialists = max(0, ceiling - len(council))
        capped_specialists = specialists[:keep_specialists]
        used = len(capped_specialists)

        # If the council alone still overflows, trim its lowest-priority tail,
        # never below the floor.
        keep_council = max(_EFFORT_CAP_FLOOR, ceiling - used) if council else 0
        capped_council = council[:keep_council]
        return capped_council, capped_specialists
    except Exception:
        # Fail-open: any failure computing the cap leaves the council uncapped.
        return council, specialists


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
    effort_class: Optional[str] = None,
) -> CouncilSession:
    """Route ``request`` to the active council + matching domain specialists.

    ``effort_class`` is the smallest-sufficient class already stamped on the
    :class:`~hermes_cli.jarvis_prime.router.RouteDecision` (e.g. ``"E2"``). It is
    consulted **only** when the default-OFF effort-cap flag is enabled
    (:func:`_effort_cap_enabled`). With the flag off — the default — this
    argument is ignored and the routing outcome is byte-for-byte identical to the
    prior behavior. When enabled, the assembled council is bounded to
    ``cap_council_size(effort_class)`` with a documented drop order and floor
    (see :func:`_apply_effort_cap`); the cap is never raised and fails open.
    """
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

    # Default-OFF effort cap. When disabled (the default), the council/specialist
    # sets above are returned untouched — no consultation of the effort primitive,
    # so the dispatch outcome is unchanged. Only when the opt-in flag is enabled
    # is the assembled council bounded to the classified effort class.
    if _effort_cap_enabled(reg):
        council, scored = _apply_effort_cap(council, scored, effort_class)

    return CouncilSession(
        request=request, council=council, specialists=scored, owner_gate_phrase=phrase
    )


# ----------------------------------------------------------------------
# Unified navigator + dispatcher (gap analysis G03)
# ----------------------------------------------------------------------
#
# This block is the *extension* that closes the two gap-analysis findings:
#
#   1. "navigator/planner is not unified"  — the Navigator (where to edit) and
#      the council Dispatcher (who engages) ran as two separate planners with
#      two separate ledger records. ``unified_dispatch`` composes them into one
#      :class:`DispatchPlan` carrying a single ``dispatch_decision`` record.
#
#   2. "dispatcher/task queue is not generalized" — ``dispatch`` only routed to
#      registry council members. The :class:`TaskQueue` below speaks the
#      ``queue.json`` contract (pending / in_flight / completed / failed) from
#      ``docs/orchestration/hermes-orchestration-pipeline.md`` so the same
#      dispatcher can emit tasks for *any* consumer (council member, navigation
#      edit-site, or a downstream worker adapter).
#
# Nothing above this block is altered; ``dispatch`` / ``CouncilSession`` remain
# the registry-routing primitive the unified layer is built on.

# Task statuses mirror the queue.json contract: pending → in_flight →
# {completed, failed}. They are plain strings (not an enum) so a serialized
# queue round-trips through JSON without a custom decoder.
_TASK_PENDING = "pending"
_TASK_IN_FLIGHT = "in_flight"
_TASK_COMPLETED = "completed"
_TASK_FAILED = "failed"


@dataclass
class Task:
    """One dispatchable unit in the unified task queue.

    A task generalizes "a piece of work the dispatcher routed": it may target a
    council member (``kind="council"`` / ``"specialist"``) or a navigation
    edit-site (``kind="edit_site"``). The ``assignee`` is whatever the consumer
    resolves against — a council-member id, a worker profile, a file path — so
    the queue is not coupled to the council registry.
    """

    id: str
    assignee: str
    kind: str  # "council" | "specialist" | "edit_site" | <caller-defined>
    status: str = _TASK_PENDING
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "assignee": self.assignee,
            "kind": self.kind,
            "status": self.status,
            "payload": dict(self.payload),
        }


@dataclass
class TaskQueue:
    """Generalized dispatch queue matching the ``queue.json`` contract.

    The pipeline doc (``hermes-orchestration-pipeline.md``) fixes the on-disk
    queue shape as ``pending`` / ``in_flight`` / ``completed`` / ``failed``.
    This class is the in-memory counterpart: the dispatcher populates it,
    callers (the orchestrator controller, a worker adapter) drain it. It is
    deliberately storage-agnostic — ``to_dict`` serializes to the contract
    shape and a caller persists it; nothing here touches the filesystem.
    """

    pending: list[Task] = field(default_factory=list)
    in_flight: list[Task] = field(default_factory=list)
    completed: list[Task] = field(default_factory=list)
    failed: list[Task] = field(default_factory=list)

    @classmethod
    def from_tasks(cls, tasks: list[Task]) -> "TaskQueue":
        """Build a queue with every task seeded as ``pending``."""
        q = cls()
        for t in tasks:
            t.status = _TASK_PENDING
            q.pending.append(t)
        return q

    def claim(self, task_id: str) -> Optional[Task]:
        """Move a pending task to ``in_flight`` and return it (None if absent)."""
        for i, t in enumerate(self.pending):
            if t.id == task_id:
                t.status = _TASK_IN_FLIGHT
                self.pending.pop(i)
                self.in_flight.append(t)
                return t
        return None

    def complete(self, task_id: str) -> bool:
        """Mark an in-flight task completed; return False if it wasn't in flight."""
        for i, t in enumerate(self.in_flight):
            if t.id == task_id:
                t.status = _TASK_COMPLETED
                self.in_flight.pop(i)
                self.completed.append(t)
                return True
        return False

    def fail(self, task_id: str) -> bool:
        """Mark an in-flight task failed; return False if it wasn't in flight."""
        for i, t in enumerate(self.in_flight):
            if t.id == task_id:
                t.status = _TASK_FAILED
                self.in_flight.pop(i)
                self.failed.append(t)
                return True
        return False

    @property
    def total(self) -> int:
        return len(self.pending) + len(self.in_flight) + len(self.completed) + len(self.failed)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Serialize to the ``queue.json`` contract shape."""
        return {
            "pending": [t.to_dict() for t in self.pending],
            "in_flight": [t.to_dict() for t in self.in_flight],
            "completed": [t.to_dict() for t in self.completed],
            "failed": [t.to_dict() for t in self.failed],
        }


@dataclass
class DispatchPlan:
    """The unified navigator + dispatcher decision for one request.

    Composes:

    * ``session`` — a :class:`CouncilSession` (who engages), the registry
      routing result; always present.
    * ``navigation`` — an optional :class:`NavigationResult` (where to edit),
      ``None`` when no navigator was supplied (non-code requests).
    * ``queue`` — a :class:`TaskQueue` of dispatchable tasks derived from the
      engaged members (and, when navigation is present, the ranked edit sites).

    This is the single record the orchestrator persists to the decision ledger
    (``kind: "dispatch_decision"``) instead of separate ``navigation_decision``
    + council entries, closing the "not unified" finding.
    """

    request: str
    session: CouncilSession
    navigation: Optional["NavigationResult"] = None
    queue: TaskQueue = field(default_factory=TaskQueue)

    @property
    def owner_gated(self) -> bool:
        return self.session.owner_gated

    def worker_packet(self) -> dict[str, Any]:
        """A worker-agnostic packet combining navigation + council routing.

        Mirrors :meth:`NavigationResult.worker_packet` but augments it with the
        engaged council members and the task queue, so a worker adapter receives
        *one* focused packet (where to edit, who reviewed, what to verify)
        rather than consulting two planners.
        """
        packet: dict[str, Any] = {
            "objective": self.request,
            "council": [m.to_dict() for m in self.session.engaged],
            "owner_gated": self.owner_gated,
            "queue": self.queue.to_dict(),
        }
        if self.navigation is not None:
            nav_packet = self.navigation.worker_packet()
            packet["candidate_files"] = nav_packet.get("candidate_files", [])
            packet["edit_sites"] = nav_packet.get("edit_sites", [])
            packet["verify_with"] = nav_packet.get("verify_with", [])
            packet["navigation_method"] = nav_packet.get("navigation_method", "")
        else:
            packet["candidate_files"] = []
            packet["edit_sites"] = []
            packet["verify_with"] = []
        return packet

    def to_ledger_record(self, *, job_id: str | None = None) -> dict[str, Any]:
        """A single decision-ledger record for the unified dispatch.

        Replaces the prior split into a ``navigation_decision`` record and an
        ad-hoc council entry with one ``dispatch_decision`` that the cockpit's
        ``navigation`` surface (see ``docs/android/cockpit-canonical-contract-plan.md``)
        and the orchestrator controller both read.
        """
        rec: dict[str, Any] = {
            "kind": "dispatch_decision",
            "job_id": job_id,
            "objective": self.request,
            "council": self.session.to_dict(),
            "queue": self.queue.to_dict(),
            "owner_gated": self.owner_gated,
        }
        if self.navigation is not None:
            rec["navigation"] = self.navigation.to_ledger_record(job_id=job_id)
        return rec

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "session": self.session.to_dict(),
            "navigation": self.navigation.to_dict() if self.navigation else None,
            "queue": self.queue.to_dict(),
            "owner_gated": self.owner_gated,
        }

    def render(self) -> str:
        lines = [f"# Unified dispatch plan — {self.request}", ""]
        lines.append(self.session.render())
        if self.navigation is not None:
            lines.append("")
            lines.append("## Navigation (where to edit)")
            for site in self.navigation.edit_sites:
                lines.append(f"  - {site.path} (rank {site.rank}, conf {site.confidence:.2f})")
        lines.append("")
        lines.append(
            f"## Task queue — {self.queue.total} task(s): "
            f"{len(self.queue.pending)} pending, "
            f"{len(self.queue.in_flight)} in_flight, "
            f"{len(self.queue.completed)} completed, "
            f"{len(self.queue.failed)} failed"
        )
        return "\n".join(lines)


def _build_tasks(session: CouncilSession, navigation: Optional["NavigationResult"]) -> list[Task]:
    """Derive the dispatchable task list from a council session + navigation.

    Each engaged council member becomes one task (kind matches the member's
    ``kind``). When navigation is present, each ranked edit site becomes an
    additional ``edit_site`` task carrying the worker packet for that site, so
    the queue generalizes beyond the registry to file-targeted work.
    """
    tasks: list[Task] = []
    for m in session.engaged:
        tasks.append(
            Task(
                id=f"council:{m.id}",
                assignee=m.id,
                kind=m.kind,
                payload={
                    "role": m.role,
                    "domain": m.domain,
                    "required_output": m.required_output,
                    "verification_method": m.verification_method,
                    "owner_gated": m.owner_gated,
                },
            )
        )
    if navigation is not None:
        for site in navigation.edit_sites:
            tasks.append(
                Task(
                    id=f"edit_site:{site.path}",
                    assignee=site.path,
                    kind="edit_site",
                    payload={
                        "path": site.path,
                        "rank": site.rank,
                        "confidence": round(site.confidence, 4),
                        "rationale": site.rationale,
                        "suggested_tests": list(site.suggested_tests),
                    },
                )
            )
    return tasks


def unified_dispatch(
    request: str,
    *,
    registry: Optional[dict[str, Any]] = None,
    navigator: Any = None,
    nav_root: Optional[str] = None,
    max_council: Optional[int] = None,
    nav_limit: int = 5,
    effort_class: Optional[str] = None,
) -> DispatchPlan:
    """Unify navigator (where) + council dispatcher (who) into one plan.

    Parameters
    ----------
    request:
        The user mission / prompt, routed to both planners.
    registry:
        Optional pre-loaded council registry (else loaded from disk).
    navigator:
        An optional :class:`~hermes_cli.jarvis_prime.navigation.navigator.Navigator`
        instance. When supplied, the plan carries a :class:`NavigationResult`
        (ranked edit sites + tests). When ``None`` and ``nav_root`` is given, a
        Navigator is built for that root. When both are ``None`` the plan is
        council-only (``navigation`` stays ``None``) — e.g. for non-code
        requests like "advise on pricing".
    nav_root:
        Convenience: build a Navigator for this repo root when ``navigator`` is
        not given. Ignored if ``navigator`` is supplied.
    max_council, nav_limit:
        Caps forwarded to :func:`dispatch` and :meth:`Navigator.navigate`.

    This is the composable extension over :func:`dispatch`: it never duplicates
    routing logic — it calls ``dispatch`` for the council half and the
    Navigator for the navigation half, then composes both into a single
    :class:`DispatchPlan` with a generalized :class:`TaskQueue`.
    """
    session = dispatch(
        request, registry=registry, max_council=max_council, effort_class=effort_class
    )

    navigation: Optional["NavigationResult"] = None
    if navigator is not None:
        navigation = navigator.navigate(request, limit=nav_limit)
    elif nav_root is not None:
        # Imported lazily so the dispatcher module has no hard dependency on
        # the navigation package (and no import cycle at module load).
        from hermes_cli.jarvis_prime.navigation.navigator import Navigator

        navigation = Navigator.for_repo(nav_root).navigate(request, limit=nav_limit)

    tasks = _build_tasks(session, navigation)
    queue = TaskQueue.from_tasks(tasks)
    return DispatchPlan(request=request, session=session, navigation=navigation, queue=queue)
