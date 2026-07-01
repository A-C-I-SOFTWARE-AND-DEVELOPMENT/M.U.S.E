"""ToolBroker — MUSE's capability firewall for tool access (opt-in, inert).

MUSE runs on a self-improving agent loop with broad tool access — terminal,
file writes, browser automation, code execution, native GitHub, and more (see
``toolsets.py`` and the live dispatcher ``model_tools.handle_function_call`` →
``registry.dispatch``). Today every enabled tool is callable directly once the
model emits a function call; the only gates on the hot path are the plugin
``pre_tool_call`` block hook and the ACP edit-approval guard. There is no
identity-scoped, per-agent capability wall in front of tool dispatch.

This module lands that wall as **additive, opt-in, and currently-inert
infrastructure**. It mirrors the merged pattern of
``hermes_cli/jarvis_prime/response_style.py``,
``hermes_cli/jarvis_prime/self_audit/footer.py``, and
``hermes_cli/jarvis_prime/challenge_contract.py``: a pure, deterministic,
offline evaluator plus a default-OFF opt-in gate. It is wired **nowhere** on
the live tool-call path by default, so default runtime tool dispatch is
byte-for-byte unchanged. A future, owner-gated follow-up would route
``model_tools`` / ``toolsets`` calls through :meth:`ToolBroker.evaluate`; that
wiring is intentionally *not* done here.

What the broker does when a caller opts in
------------------------------------------

Given a :class:`ToolCallRequest` (tool name, args, calling agent identity,
effort/risk context, and a source-trust label), :meth:`ToolBroker.evaluate`
returns a structured :class:`BrokerDecision` — one of :class:`BrokerVerdict`
``ALLOW`` / ``DENY`` / ``REQUIRES_OWNER_APPROVAL`` / ``DRY_RUN`` — carrying a
structured audit record and, on failure, a structured :class:`StructuredError`.
No agent gets raw tool access when the broker is enabled; every call passes
through with identity + scope + budget + audit metadata.

Components (all deterministic / offline — stdlib + intra-package only, **no**
model call, **no** network, **no** socket):

- **Per-identity ALLOWLISTS.** A tool not on the calling identity's allowlist
  → ``DENY`` with a structured reason. An identity with no configured
  allowlist is treated as "no capabilities" (fail-closed) unless it is the
  explicit wildcard.
- **Budget caps.** A per-identity call budget; when exhausted, subsequent
  calls return a structured ``DENY`` ("budget exceeded") — never a raised
  exception. Budgets are counted in-memory on the broker instance.
- **Dry-run mode.** When enabled, an otherwise-``ALLOW`` decision is downgraded
  to ``DRY_RUN`` so a caller can preview intent without side effects. A
  previewed (``DRY_RUN``) call still consumes budget — a preview counts against
  the per-identity cap exactly like an ``ALLOW``.
- **Prompt-injection scanning hook.** A pluggable :class:`InjectionScanner`
  protocol plus a conservative built-in heuristic
  (:class:`HeuristicInjectionScanner`) that flags obvious markers ("ignore
  previous instructions", tool-description poisoning, etc.). A flagged request
  becomes ``REQUIRES_OWNER_APPROVAL`` or ``DENY`` per policy. The built-in
  heuristic is explicitly a *hook*, not a complete solution.
- **Source trust labels.** Each request carries a :class:`SourceTrust` label
  (``TRUSTED`` / ``UNTRUSTED`` / ``EXTERNAL``). Untrusted / external sources get
  genuinely stricter treatment on a risk signal: injection scanning is
  mandatory, and when the scanner *flags* a request an untrusted/external
  source is ``DENY`` outright whereas a trusted source is only downgraded to
  ``REQUIRES_OWNER_APPROVAL`` (so the identical flagged request yields a
  stricter verdict for untrusted). Owner-gated / side-effecting tools require
  owner approval at every trust level. Broadening untrusted enforcement to
  *clean* read-only tools (denying/gating them purely on trust, absent any risk
  signal) is deliberately left to the owner-gated live-dispatch wiring
  follow-up; this inert evaluator does not do that.
- **Owner-approval hook.** Side-effecting / owner-gated tools →
  ``REQUIRES_OWNER_APPROVAL``, reusing the existing owner-gate concept from
  ``hermes_cli/approval_policy.py`` (the ``_ALWAYS_CONFIRM`` confirm-set) rather
  than inventing a competing gate.
- **Structured errors.** :class:`StructuredError` and :class:`BrokerDecision`
  dataclasses; :meth:`ToolBroker.evaluate` never lets a raw exception escape —
  malformed input yields a structured ``DENY`` with an ``internal_error``
  code.

Opt-in gate
-----------

:func:`tool_broker_enabled` gates the *whole broker* and defaults to ``False``.
It resolves ``security.tool_broker.enabled`` in the user config, then the
``MUSE_TOOL_BROKER`` environment variable (later wins), exactly like the merged
gate helpers. With no config and no env var it returns ``False`` and no broker
runs. Evaluating a :class:`ToolBroker` directly is always safe (pure), but the
gate is what a future dispatcher would consult before routing through it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Protocol, runtime_checkable

# Environment override for the opt-in gate (mirrors the MUSE_* flags on the
# other merged opt-in features).
_ENV_FLAG = "MUSE_TOOL_BROKER"

# Wildcard allowlist entry: an identity mapped to a set containing this token
# may call any tool (subject to every other check — trust, injection, owner
# gates, budget). Kept explicit so "no allowlist" can safely mean "nothing".
ALLOW_ALL = "*"


class BrokerVerdict(Enum):
    """The four possible outcomes of a broker evaluation.

    - ``ALLOW`` — the call may proceed as-is.
    - ``DENY`` — the call is refused (not on allowlist, budget exhausted,
      injection flagged under a deny policy, or a structured internal error).
    - ``REQUIRES_OWNER_APPROVAL`` — the call is side-effecting / owner-gated, or
      the injection scanner flagged it from a *trusted* source, and it needs the
      owner's explicit authorization before it may run. (A flagged request from
      an untrusted/external source is ``DENY``, not this.)
    - ``DRY_RUN`` — the call *would* be allowed, but dry-run mode is on, so the
      caller should preview rather than execute (no side effect intended).
    """

    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_OWNER_APPROVAL = "requires_owner_approval"
    DRY_RUN = "dry_run"


class SourceTrust(Enum):
    """How much the *origin* of a tool-call request is trusted.

    - ``TRUSTED`` — the request originates from the owner / a first-party,
      audited path.
    - ``UNTRUSTED`` — the request derives from lower-trust content (e.g. an
      untrusted document the model summarized). Injection scanning is mandatory,
      and a *flagged* request is ``DENY`` outright (stricter than the trusted
      path, which is only downgraded to ``REQUIRES_OWNER_APPROVAL``).
    - ``EXTERNAL`` — the request derives from fully external / third-party input
      (web content, inbound message from an unknown party). Treated at least as
      strictly as ``UNTRUSTED`` (identical stricter injection handling).
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    EXTERNAL = "external"


class InjectionPolicy(Enum):
    """What to do when the injection scanner flags a request.

    - ``OWNER_APPROVAL`` — downgrade to ``REQUIRES_OWNER_APPROVAL`` for a
      *trusted* source (default; conservative but not fully blocking). An
      untrusted/external source is still ``DENY`` outright even under this
      policy — trust makes the flagged path stricter.
    - ``DENY`` — refuse outright at every trust level.
    """

    OWNER_APPROVAL = "owner_approval"
    DENY = "deny"


@runtime_checkable
class InjectionScanner(Protocol):
    """Pluggable prompt-injection scanner interface.

    Implementations inspect a request and return an :class:`InjectionFinding`.
    The broker treats scanning as a *hook*: swap in a stronger scanner (model-
    or service-backed) at the wiring layer without changing the broker. The
    built-in :class:`HeuristicInjectionScanner` is deliberately simple.
    """

    def scan(self, request: "ToolCallRequest") -> "InjectionFinding":
        """Inspect ``request`` and return a structured :class:`InjectionFinding`."""


@dataclass(frozen=True)
class InjectionFinding:
    """The structured result of an injection scan.

    ``flagged`` is True when the scanner considers the request suspicious.
    ``markers`` lists the specific signals that fired (for the audit record).
    """

    flagged: bool
    markers: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {"flagged": self.flagged, "markers": list(self.markers)}


# Conservative, high-precision injection markers. These are obvious
# instruction-override / tool-poisoning phrases. This is a *hook demo*, not a
# complete defense — a real deployment plugs in a stronger scanner. Matching is
# a simple case-insensitive substring test over the joined request text.
_INJECTION_MARKERS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore the above instructions",
    "disregard previous instructions",
    "disregard all prior instructions",
    "forget your instructions",
    "forget all previous instructions",
    "override your instructions",
    "you are now",
    "system prompt:",
    "new instructions:",
    "reveal your system prompt",
    "print your system prompt",
    "exfiltrate",
    "send your api key",
    "leak the secret",
    "<|im_start|>",
    "tool description says to",
    "as the tool, you must",
)


class HeuristicInjectionScanner:
    """A conservative, offline, built-in injection scanner (a hook, not a wall).

    Flags a request when any obvious instruction-override / tool-poisoning
    marker appears in its combined text (tool name + stringified args). Kept
    intentionally simple and documented as a hook: it catches the blatant cases
    and hands off to owner approval, but it is **not** a substitute for a real
    injection defense. Deterministic and offline — no model, no network.
    """

    def __init__(self, markers: Iterable[str] = _INJECTION_MARKERS) -> None:
        self._markers = tuple(m.lower() for m in markers if m)

    def scan(self, request: "ToolCallRequest") -> InjectionFinding:
        haystack = request.scan_text().lower()
        hits = tuple(m for m in self._markers if m in haystack)
        return InjectionFinding(flagged=bool(hits), markers=hits)


@dataclass(frozen=True)
class ToolCallRequest:
    """A single proposed tool call, fully described for brokering.

    Fields are typed loosely so the same shape works across CLI, gateway, MCP,
    and orchestrator call sites — the broker reads only what it needs.

    - ``tool_name`` — the registered tool name (e.g. ``"terminal"``).
    - ``args`` — the tool arguments mapping.
    - ``identity`` — the calling agent / worker identity (allowlist + budget key).
    - ``source_trust`` — where the request ultimately came from.
    - ``effort_class`` — optional effort/risk hint (an ``EffortClass`` or
      ``"E<n>"`` string); reserved for future risk-tiering, recorded in audit.
    - ``owner_gated`` — an explicit caller override marking this call as
      owner-gated regardless of the tool's default classification.
    - ``call_id`` — optional stable id for the audit record.
    """

    tool_name: str
    args: Mapping[str, Any] = field(default_factory=dict)
    identity: str = ""
    source_trust: SourceTrust = SourceTrust.TRUSTED
    effort_class: Any = None
    owner_gated: bool = False
    call_id: str = ""

    def scan_text(self) -> str:
        """Return the combined text an injection scanner inspects."""
        parts: list[str] = [str(self.tool_name)]
        try:
            for key, value in dict(self.args).items():
                parts.append(str(key))
                parts.append(str(value))
        except Exception:
            # Malformed args must never break scanning — fall back to repr.
            parts.append(repr(self.args))
        return "\n".join(parts)


@dataclass(frozen=True)
class StructuredError:
    """A structured error emitted instead of raising.

    ``code`` is a stable machine identifier; ``message`` is a human one-liner.
    """

    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class BrokerDecision:
    """The structured outcome of :meth:`ToolBroker.evaluate`.

    - ``verdict`` — the :class:`BrokerVerdict`.
    - ``reason`` — a human-readable one-liner (safe to render verbatim).
    - ``tool_name`` / ``identity`` — echoed for the audit trail.
    - ``source_trust`` — the request's trust label (value string).
    - ``injection`` — the injection finding (``None`` when scanning did not run).
    - ``error`` — a :class:`StructuredError` when the verdict is a structured
      failure (never a raw exception).
    - ``audit`` — a flat, JSON-serializable audit record.
    """

    verdict: BrokerVerdict
    reason: str
    tool_name: str = ""
    identity: str = ""
    source_trust: str = SourceTrust.TRUSTED.value
    injection: Optional[InjectionFinding] = None
    error: Optional[StructuredError] = None
    audit: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        """True only for a plain ``ALLOW`` (dry-run is *not* an execute grant)."""
        return self.verdict is BrokerVerdict.ALLOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "tool_name": self.tool_name,
            "identity": self.identity,
            "source_trust": self.source_trust,
            "injection": self.injection.to_dict() if self.injection else None,
            "error": self.error.to_dict() if self.error else None,
            "audit": dict(self.audit),
        }


def _default_side_effecting_tools() -> frozenset[str]:
    """Return the default set of side-effecting / owner-gated tool names.

    Reuses the owner-gate *concept* from ``hermes_cli/approval_policy.py`` — the
    ``_ALWAYS_CONFIRM`` confirm-set — rather than inventing a competing gate.
    The confirm-set is expressed in :class:`approval_policy.Action` categories;
    here we map the relevant categories onto the concrete tool names MUSE
    dispatches. Import is best-effort so this module never hard-depends on the
    approval layer at import time; the tool-name mapping is the stable surface.

    .. note::
       This is a *hardcoded* set, not a live view of the tool registry. The
       future owner-gated live-dispatch wiring step MUST cross-check this set
       against the actual registered tools (``toolsets`` / ``model_tools``) so a
       newly added side-effecting tool that is missing here cannot be silently
       treated as safe (read-only) and slip past the owner gate.
    """
    # Concrete MUSE tool names that mutate state, spend, publish, or reach out.
    tools = {
        "terminal",  # arbitrary shell — destructive/remote commands live here
        "process",  # long-running/background process control
        "write_file",  # local write
        "patch",  # local write
        "execute_code",  # arbitrary code execution
        "image_generate",  # potential paid generation
        "delegate_task",  # spawns another worker
        "cronjob",  # schedules future autonomous work
        "browser_navigate",  # reaches external network
        "text_to_speech",  # potential paid generation
    }
    try:  # Best-effort: confirm the approval layer still exists (concept reuse).
        from hermes_cli import approval_policy  # noqa: F401
    except Exception:
        # Intentionally ignored: this import is only a concept-presence check
        # (the owner-gate idea lives in approval_policy). The concrete tool-name
        # defaults above are used regardless of whether the import succeeds, so
        # a failure here must not change the returned set.
        pass
    return frozenset(tools)


DEFAULT_SIDE_EFFECTING_TOOLS: frozenset[str] = _default_side_effecting_tools()


class ToolBroker:
    """Mediates tool access with identity, scope, budget, trust, and audit.

    Pure and deterministic given its configuration and call history: no model
    call, no network, no socket. Budgets are the only mutable state — an
    in-memory per-identity counter on the instance. :meth:`evaluate` never
    raises; malformed input yields a structured ``DENY``.

    Construction:

    - ``allowlists`` — ``{identity: {tool_name, ...}}``. An identity mapped to a
      set containing :data:`ALLOW_ALL` (``"*"``) may call any tool. An identity
      absent from the map (or mapped to an empty set) can call nothing
      (fail-closed).
    - ``budgets`` — ``{identity: max_calls}``. Absent ⇒ unlimited. A call that
      would exceed the cap returns a structured budget-exceeded ``DENY``.
    - ``dry_run`` — when True, ``ALLOW`` outcomes are downgraded to ``DRY_RUN``.
    - ``scanner`` — an :class:`InjectionScanner`; defaults to the built-in
      :class:`HeuristicInjectionScanner`.
    - ``injection_policy`` — what a flagged request becomes
      (:class:`InjectionPolicy`).
    - ``side_effecting_tools`` — the owner-gated tool set
      (defaults to :data:`DEFAULT_SIDE_EFFECTING_TOOLS`).
    """

    def __init__(
        self,
        *,
        allowlists: Optional[Mapping[str, Iterable[str]]] = None,
        budgets: Optional[Mapping[str, int]] = None,
        dry_run: bool = False,
        scanner: Optional[InjectionScanner] = None,
        injection_policy: InjectionPolicy = InjectionPolicy.OWNER_APPROVAL,
        side_effecting_tools: Optional[Iterable[str]] = None,
    ) -> None:
        self._allowlists: dict[str, frozenset[str]] = {
            str(identity): frozenset(str(t) for t in tools)
            for identity, tools in (allowlists or {}).items()
        }
        self._budgets: dict[str, int] = {
            str(identity): int(cap) for identity, cap in (budgets or {}).items()
        }
        self._dry_run = bool(dry_run)
        self._scanner: InjectionScanner = scanner or HeuristicInjectionScanner()
        self._injection_policy = injection_policy
        self._side_effecting: frozenset[str] = frozenset(
            str(t) for t in (
                side_effecting_tools
                if side_effecting_tools is not None
                else DEFAULT_SIDE_EFFECTING_TOOLS
            )
        )
        # Per-identity consumed-call counter (in-memory).
        self._consumed: dict[str, int] = {}

    # -- introspection -----------------------------------------------------

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def consumed(self, identity: str) -> int:
        """Return how many budgeted calls ``identity`` has consumed so far."""
        return self._consumed.get(str(identity), 0)

    def remaining_budget(self, identity: str) -> Optional[int]:
        """Return remaining budget for ``identity`` (``None`` = unlimited)."""
        cap = self._budgets.get(str(identity))
        if cap is None:
            return None
        return max(0, cap - self._consumed.get(str(identity), 0))

    # -- core --------------------------------------------------------------

    def evaluate(self, request: Any) -> BrokerDecision:
        """Return a structured :class:`BrokerDecision` for ``request``.

        Never raises. Order of checks (all fail-closed):

        1. Malformed request → structured ``DENY`` (``internal_error``).
        2. Identity allowlist → ``DENY`` if the tool is not permitted.
        3. Injection scan (mandatory for untrusted/external; best-effort for
           trusted) → when flagged, the trust label decides the outcome: a
           TRUSTED source becomes ``REQUIRES_OWNER_APPROVAL``, while an
           UNTRUSTED/EXTERNAL source is ``DENY`` (genuinely stricter — the same
           flagged request is denied for untrusted but only owner-gated for
           trusted). Under the ``DENY`` injection policy, every trust level is
           denied.
        4. Owner gate — a side-effecting tool or an explicit ``owner_gated``
           flag → ``REQUIRES_OWNER_APPROVAL`` (same for every trust level).
        5. Budget — if consuming a call would exceed the cap → ``DENY``.
           Budget is only consumed for an actual ``ALLOW`` / ``DRY_RUN`` grant.
           Note: a ``DRY_RUN`` (previewed) call still counts against the cap.
        6. Dry-run downgrade — an ``ALLOW`` becomes ``DRY_RUN`` when enabled.
        """
        try:
            return self._evaluate(request)
        except Exception as exc:  # never leak a raw exception
            return BrokerDecision(
                verdict=BrokerVerdict.DENY,
                reason="tool broker internal error — denied fail-closed",
                error=StructuredError(
                    code="internal_error",
                    message=f"{type(exc).__name__}: {exc}"[:200],
                ),
                audit={"stage": "internal_error"},
            )

    def _evaluate(self, request: Any) -> BrokerDecision:
        # 1. Validate request shape (structured, not raised).
        if not isinstance(request, ToolCallRequest):
            return BrokerDecision(
                verdict=BrokerVerdict.DENY,
                reason="malformed request: expected a ToolCallRequest",
                error=StructuredError(
                    code="malformed_request",
                    message="request must be a ToolCallRequest instance",
                ),
                audit={"stage": "validate"},
            )

        tool_name = str(request.tool_name or "").strip()
        identity = str(request.identity or "").strip()
        trust = (
            request.source_trust
            if isinstance(request.source_trust, SourceTrust)
            else SourceTrust.TRUSTED
        )
        audit: dict[str, Any] = {
            "tool_name": tool_name,
            "identity": identity,
            "source_trust": trust.value,
            "effort_class": _effort_str(request.effort_class),
            "call_id": str(request.call_id or ""),
            "dry_run_mode": self._dry_run,
        }

        if not tool_name:
            return BrokerDecision(
                verdict=BrokerVerdict.DENY,
                reason="malformed request: empty tool name",
                tool_name=tool_name,
                identity=identity,
                source_trust=trust.value,
                error=StructuredError(
                    code="malformed_request", message="tool_name is required"
                ),
                audit={**audit, "stage": "validate"},
            )

        # 2. Identity allowlist (fail-closed).
        if not self._identity_allows(identity, tool_name):
            return BrokerDecision(
                verdict=BrokerVerdict.DENY,
                reason=(
                    f"identity {identity or '<anonymous>'!r} is not permitted "
                    f"to call tool {tool_name!r}"
                ),
                tool_name=tool_name,
                identity=identity,
                source_trust=trust.value,
                error=StructuredError(
                    code="not_on_allowlist",
                    message="tool is not on this identity's allowlist",
                ),
                audit={**audit, "stage": "allowlist"},
            )

        # 3. Injection scan. Mandatory for untrusted/external; best-effort for
        # trusted. When a request is flagged, the trust label changes the
        # outcome: a TRUSTED source is downgraded to REQUIRES_OWNER_APPROVAL
        # (the owner can vet and authorize), but an UNTRUSTED/EXTERNAL source is
        # DENIED outright — a risk signal on lower-trust content is not
        # something the owner should be nudged to wave through. Under the
        # explicit DENY injection policy, every trust level is denied.
        finding: Optional[InjectionFinding] = None
        untrusted = trust in (SourceTrust.UNTRUSTED, SourceTrust.EXTERNAL)
        must_scan = untrusted
        finding = self._scanner.scan(request)
        audit["injection"] = finding.to_dict()
        if finding.flagged:
            if self._injection_policy is InjectionPolicy.DENY or untrusted:
                deny_reason = (
                    "prompt-injection markers detected from an untrusted/external "
                    "source — denied (stricter than trusted, which would require "
                    "owner approval)"
                    if untrusted and self._injection_policy is not InjectionPolicy.DENY
                    else "prompt-injection markers detected — denied by policy"
                )
                return BrokerDecision(
                    verdict=BrokerVerdict.DENY,
                    reason=deny_reason,
                    tool_name=tool_name,
                    identity=identity,
                    source_trust=trust.value,
                    injection=finding,
                    error=StructuredError(
                        code="injection_flagged",
                        message="injection scanner flagged the request",
                    ),
                    audit={
                        **audit,
                        "stage": "injection",
                        "mandatory_scan": must_scan,
                        "untrusted_denied": untrusted
                        and self._injection_policy is not InjectionPolicy.DENY,
                    },
                )
            return BrokerDecision(
                verdict=BrokerVerdict.REQUIRES_OWNER_APPROVAL,
                reason=(
                    "prompt-injection markers detected — owner approval required "
                    "before this tool call may run"
                ),
                tool_name=tool_name,
                identity=identity,
                source_trust=trust.value,
                injection=finding,
                audit={**audit, "stage": "injection", "mandatory_scan": must_scan},
            )

        # 4. Owner gate. A side-effecting/owner-gated tool or an explicit
        # owner_gated flag requires owner approval, at every trust level. (The
        # trust-based stricter behavior lives in the injection stage above; a
        # clean, read-only, non-owner-gated call is still ALLOWed regardless of
        # trust here — broadening untrusted enforcement to clean read-only tools
        # is part of the owner-gated live-dispatch wiring follow-up, not this
        # inert evaluator.)
        is_side_effecting = tool_name in self._side_effecting
        if bool(request.owner_gated) or is_side_effecting:
            return BrokerDecision(
                verdict=BrokerVerdict.REQUIRES_OWNER_APPROVAL,
                reason=(
                    f"tool {tool_name!r} is side-effecting / owner-gated — owner "
                    f"approval required (source={trust.value})"
                ),
                tool_name=tool_name,
                identity=identity,
                source_trust=trust.value,
                injection=finding,
                audit={
                    **audit,
                    "stage": "owner_gate",
                    "side_effecting": is_side_effecting,
                    "explicit_owner_gated": bool(request.owner_gated),
                },
            )

        # 5. Budget. Would consuming a call exceed the cap?
        cap = self._budgets.get(identity)
        if cap is not None and self._consumed.get(identity, 0) >= cap:
            return BrokerDecision(
                verdict=BrokerVerdict.DENY,
                reason=(
                    f"budget exceeded for identity {identity or '<anonymous>'!r} "
                    f"({cap} call(s) used)"
                ),
                tool_name=tool_name,
                identity=identity,
                source_trust=trust.value,
                injection=finding,
                error=StructuredError(
                    code="budget_exceeded",
                    message=f"per-identity call budget of {cap} exhausted",
                ),
                audit={**audit, "stage": "budget", "budget": cap},
            )

        # Grant path — consume budget, then apply dry-run downgrade.
        if cap is not None:
            self._consumed[identity] = self._consumed.get(identity, 0) + 1
            audit["budget"] = cap
            audit["budget_consumed"] = self._consumed[identity]

        if self._dry_run:
            return BrokerDecision(
                verdict=BrokerVerdict.DRY_RUN,
                reason=f"dry-run mode: tool {tool_name!r} would be allowed (no side effect)",
                tool_name=tool_name,
                identity=identity,
                source_trust=trust.value,
                injection=finding,
                audit={**audit, "stage": "grant", "grant": "dry_run"},
            )

        return BrokerDecision(
            verdict=BrokerVerdict.ALLOW,
            reason=f"tool {tool_name!r} allowed for identity {identity or '<anonymous>'!r}",
            tool_name=tool_name,
            identity=identity,
            source_trust=trust.value,
            injection=finding,
            audit={**audit, "stage": "grant", "grant": "allow"},
        )

    def _identity_allows(self, identity: str, tool_name: str) -> bool:
        allowed = self._allowlists.get(identity)
        if allowed is None:
            return False  # fail-closed: unknown identity has no capabilities
        return ALLOW_ALL in allowed or tool_name in allowed


def _effort_str(effort: Any) -> Optional[str]:
    """Best-effort stringify of an effort hint for the audit record."""
    if effort is None:
        return None
    value = getattr(effort, "value", None)
    if isinstance(value, str):
        return value
    return str(effort)


def tool_broker_enabled(user_config: Mapping[str, Any] | None = None) -> bool:
    """Return whether the ToolBroker capability firewall is enabled (default OFF).

    Resolution (later wins):

    1. Built-in default — ``False`` (the broker is inert; default tool dispatch
       is unchanged).
    2. ``security.tool_broker.enabled`` in the user config.
    3. The ``MUSE_TOOL_BROKER`` environment variable, when set to a truthy value
       (``1``/``true``/``yes``/``on``) or a falsy one.

    The default is OFF, so with no config and no env var this returns ``False``
    and no broker runs — the default runtime tool-call path is byte-for-byte
    unchanged. Mirrors the opt-in gate helpers on the merged features
    (``challenge_contract_enabled`` / ``self_audit_footer_enabled`` /
    ``response_style`` gate). This gates *wiring the broker into dispatch*;
    constructing and calling a :class:`ToolBroker` directly is always safe
    (it is pure inspection that changes nothing on its own).
    """
    enabled = False

    security = (user_config or {}).get("security") if user_config else None
    if isinstance(security, Mapping):
        section = security.get("tool_broker")
        if isinstance(section, Mapping) and "enabled" in section:
            enabled = bool(section.get("enabled"))

    raw = os.environ.get(_ENV_FLAG)
    if raw is not None:
        enabled = raw.strip().lower() in {"1", "true", "yes", "on"}

    return enabled


__all__ = [
    "ALLOW_ALL",
    "BrokerVerdict",
    "SourceTrust",
    "InjectionPolicy",
    "InjectionScanner",
    "InjectionFinding",
    "HeuristicInjectionScanner",
    "ToolCallRequest",
    "StructuredError",
    "BrokerDecision",
    "DEFAULT_SIDE_EFFECTING_TOOLS",
    "ToolBroker",
    "tool_broker_enabled",
]
