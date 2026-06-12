"""Post-run review that proposes prompt/policy improvements.

The Monitor SKILL.md is what actually reads + reasons over an audit
trail at session end. This module gives the SKILL a concrete place to
write the resulting proposals so the Hermes curator (or a human
reviewer) can pick them up.

Each proposal is a small JSON file under
``HERMES_HOME/enterprise/drafts/``. The shape is intentionally
lightweight — the curator's "drafts → published" promotion flow lives
in ``agent/curator.py`` and reads from its own directory; the bridge
between the two is left as an operator integration step, documented
in the Monitor SKILL.md.

Three improvement kinds are recognised here, matching the three
validation failure modes from `enterprise.judge`:

  * ``prompt_regression`` — leaf returned a malformed result repeatedly
    (schema_fail). Proposal: tighten the leaf's structured-output
    instruction.
  * ``planning_regression`` — orchestrator dispatched something with
    drifted risk (policy_fail). Proposal: add to the rules table or
    re-classify the action.
  * ``model_disagreement`` — judge & jury disagreed on a substantive
    field repeatedly (judge_disagree). Proposal: lower temperature on
    the leaf or add a deterministic comparator.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from enterprise.audit import AuditEvent, read_events


def _drafts_dir() -> Path:
    try:
        from muse_cli.config import get_hermes_home

        base = Path(get_hermes_home())
    except Exception:
        base = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    target = base / "enterprise" / "drafts"
    target.mkdir(parents=True, exist_ok=True)
    return target


@dataclass
class ImprovementProposal:
    """One write-once recommendation produced by the Monitor."""

    id: str
    ts: float
    session_id: str
    kind: str  # prompt_regression | planning_regression | model_disagreement
    target_agent: str
    summary: str
    evidence_event_count: int
    suggested_action: str
    extra: dict[str, Any] = field(default_factory=dict)


def _classify_failures(events: Iterable[AuditEvent]) -> dict[str, list[AuditEvent]]:
    buckets: dict[str, list[AuditEvent]] = {
        "schema_fail": [],
        "policy_fail": [],
        "judge_disagree": [],
        "escalated": [],
    }
    for ev in events:
        if ev.event == "judge" and ev.validation in buckets:
            buckets[ev.validation].append(ev)
        elif ev.event == "escalate":
            buckets["escalated"].append(ev)
    return buckets


def _proposal_for_schema_fails(
    session_id: str, fails: list[AuditEvent], min_repeat: int
) -> Optional[ImprovementProposal]:
    if len(fails) < min_repeat:
        return None
    # Group by tool to identify which leaf is misbehaving.
    by_tool: dict[str, int] = {}
    for ev in fails:
        by_tool[ev.tool or "<unknown>"] = by_tool.get(ev.tool or "<unknown>", 0) + 1
    worst_tool, worst_count = max(by_tool.items(), key=lambda kv: kv[1])
    return ImprovementProposal(
        id=f"prop-{uuid.uuid4().hex[:8]}",
        ts=time.time(),
        session_id=session_id,
        kind="prompt_regression",
        target_agent=worst_tool.split(".")[0] if "." in worst_tool else "unknown",
        summary=(
            f"Tool {worst_tool!r} returned a malformed result {worst_count} times. "
            "Tighten the structured-output contract in the leaf's SKILL.md."
        ),
        evidence_event_count=len(fails),
        suggested_action="update_skill_prompt",
        extra={"worst_tool": worst_tool, "by_tool": by_tool},
    )


def _proposal_for_policy_fails(
    session_id: str, fails: list[AuditEvent], min_repeat: int
) -> Optional[ImprovementProposal]:
    if len(fails) < min_repeat:
        return None
    return ImprovementProposal(
        id=f"prop-{uuid.uuid4().hex[:8]}",
        ts=time.time(),
        session_id=session_id,
        kind="planning_regression",
        target_agent="orchestrator",
        summary=(
            f"Orchestrator dispatched {len(fails)} task(s) the judge flagged as policy_fail. "
            "Review the (domain, action) entries in enterprise.policy._BASE_RULES."
        ),
        evidence_event_count=len(fails),
        suggested_action="update_policy_rules",
    )


def _proposal_for_disagreements(
    session_id: str, fails: list[AuditEvent], min_repeat: int
) -> Optional[ImprovementProposal]:
    if len(fails) < min_repeat:
        return None
    return ImprovementProposal(
        id=f"prop-{uuid.uuid4().hex[:8]}",
        ts=time.time(),
        session_id=session_id,
        kind="model_disagreement",
        target_agent="judge",
        summary=(
            f"Judge & jury disagreed on {len(fails)} task(s). "
            "Lower leaf temperature, or add a deterministic comparator for the divergent field."
        ),
        evidence_event_count=len(fails),
        suggested_action="tune_leaf_or_add_comparator",
    )


def review_session(
    session_id: str,
    *,
    min_repeat: int = 1,
) -> list[ImprovementProposal]:
    """Walk the session's audit trail and emit proposals to drafts/.

    ``min_repeat`` controls how many of each failure kind must be
    present before a proposal is written. Defaults to 1 so a single
    failure still surfaces an actionable hint; the SKILL.md raises
    this for noisy environments.
    """
    events = read_events(session_id)
    if not events:
        return []
    buckets = _classify_failures(events)
    proposals: list[ImprovementProposal] = []
    p = _proposal_for_schema_fails(session_id, buckets["schema_fail"], min_repeat)
    if p:
        proposals.append(p)
    p = _proposal_for_policy_fails(session_id, buckets["policy_fail"], min_repeat)
    if p:
        proposals.append(p)
    p = _proposal_for_disagreements(session_id, buckets["judge_disagree"], min_repeat)
    if p:
        proposals.append(p)

    drafts_dir = _drafts_dir()
    for prop in proposals:
        (drafts_dir / f"{prop.id}.json").write_text(
            json.dumps(asdict(prop), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return proposals
