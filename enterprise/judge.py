"""Validator / Judge for enterprise council outputs.

The Judge runs *after* a leaf agent returns its structured result. It
does three layered checks:

  1. **Schema check.** Required keys are present, types match. Catches
     leaves that returned a partial structure or a free-form string
     where structured data was expected.
  2. **Policy check.** The action's risk level and any policy tags
     match what the orchestrator declared up front. Catches leaves
     that drifted into a higher-risk action than they were dispatched
     for (e.g. "send a refund" when only "draft" was authorised).
  3. **Judge & jury.** A second, independently-computed "jury" result
     for the same task is compared against the leaf's. Disagreement
     triggers a retry. The jury is computed by the caller (so we can
     swap LLM-backed runs in production and deterministic comparators
     in tests).

The Judge is intentionally a pure function — no LLM call here. The
caller is responsible for producing the jury result. That keeps this
module unit-testable and lets the orchestrator decide whether to spend
the tokens on a parallel pass or to use a cheaper deterministic
comparator (e.g. recomputing a sum, re-hashing a payload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from enterprise.policy import Risk, Task


@dataclass(frozen=True)
class JudgeVerdict:
    """Outcome of a Judge run.

    Attributes:
        ok: Whether the result passed all checks.
        validation: A short categorical label used by audit.
            One of: "ok" | "schema_fail" | "policy_fail" | "judge_disagree".
        reasons: Human-readable list of what failed; empty on success.
        diff: When ``validation == "judge_disagree"``, the structural
            diff of (leaf_result vs jury_result) keyed by field name.
    """

    ok: bool
    validation: str
    reasons: tuple[str, ...] = ()
    diff: Mapping[str, tuple[Any, Any]] = ()


def _schema_check(
    result: Mapping[str, Any],
    required_keys: Iterable[str],
    optional_types: Optional[Mapping[str, type]] = None,
) -> list[str]:
    fails: list[str] = []
    if not isinstance(result, Mapping):
        return [f"result is {type(result).__name__}, expected mapping"]
    for k in required_keys:
        if k not in result:
            fails.append(f"missing required key: {k!r}")
    for k, t in (optional_types or {}).items():
        if k in result and not isinstance(result[k], t):
            fails.append(
                f"key {k!r} has type {type(result[k]).__name__}, expected {t.__name__}"
            )
    return fails


def _policy_check(
    task: Task,
    declared_risk: Risk,
    result_tags: tuple[str, ...],
) -> list[str]:
    fails: list[str] = []
    # If the leaf annotated its result with a stricter action than the
    # orchestrator declared, that's a drift — flag it.
    if "executed-higher-risk" in result_tags:
        fails.append(
            f"leaf reported it executed a higher-risk action than {task.action!r} was authorised for"
        )
    if "irreversible" in result_tags and declared_risk != Risk.HIGH:
        fails.append(
            "leaf claims action was irreversible but orchestrator did not mark it HIGH"
        )
    return fails


def _result_diff(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    ignore: Iterable[str] = (),
) -> dict[str, tuple[Any, Any]]:
    skip = set(ignore)
    diff: dict[str, tuple[Any, Any]] = {}
    keys = (set(a) | set(b)) - skip
    for k in sorted(keys):
        av, bv = a.get(k), b.get(k)
        if av != bv:
            diff[k] = (av, bv)
    return diff


def cross_check(
    *,
    task: Task,
    declared_risk: Risk,
    leaf_result: Mapping[str, Any],
    jury_result: Optional[Mapping[str, Any]] = None,
    required_keys: Iterable[str] = ("status",),
    optional_types: Optional[Mapping[str, type]] = None,
    result_tags: tuple[str, ...] = (),
    ignore_fields: Iterable[str] = (),
) -> JudgeVerdict:
    """Run schema, policy, and jury checks. Stop at first failure category.

    Failure ordering matters for the Monitor: schema failures usually
    indicate a prompt regression in the leaf; policy failures usually
    indicate a planning regression in the orchestrator; jury
    disagreements usually indicate a model-quality issue. The Monitor
    uses ``validation`` to route its proposed improvements.
    """
    schema_fails = _schema_check(leaf_result, required_keys, optional_types)
    if schema_fails:
        return JudgeVerdict(
            ok=False, validation="schema_fail", reasons=tuple(schema_fails)
        )

    policy_fails = _policy_check(task, declared_risk, result_tags)
    if policy_fails:
        return JudgeVerdict(
            ok=False, validation="policy_fail", reasons=tuple(policy_fails)
        )

    # "ok" results often include nondeterministic identifiers (e.g. uuid).
    # We always ignore those by default — the orchestrator can pass extra
    # field names through ``ignore_fields`` if it knows about them.
    auto_ignore = {
        "invoice_id",
        "candidate_id",
        "offer_id",
        "ticket_id",
        "shipment_id",
        "compliance_id",
        "proposal_id",
        "lead_id",
        "envelope_id",
        "termination_id",
        "incident_id",
        "confirmation",
    }
    all_ignore = auto_ignore | set(ignore_fields)

    if jury_result is not None:
        diff = _result_diff(leaf_result, jury_result, ignore=all_ignore)
        if diff:
            return JudgeVerdict(
                ok=False,
                validation="judge_disagree",
                reasons=(f"jury disagrees on {len(diff)} field(s)",),
                diff=diff,
            )

    return JudgeVerdict(ok=True, validation="ok")
