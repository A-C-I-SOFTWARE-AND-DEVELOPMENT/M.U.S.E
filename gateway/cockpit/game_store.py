"""SYNAPSE game save slots — the ``/v1/game/*`` persistence layer.

Versioned save documents (``v: 1``) live under
``${HERMES_HOME}/jarvis_prime/game/`` as one JSON file per slot, written
atomically (tmp + ``os.replace`` — the ``gateway.cockpit.auth`` pattern;
``room_store``'s plain ``write_text`` predates that hardening).

Design authority (every constant below cites its source — the gateway
persists and validates, it invents nothing):

* ``docs/plans/2026-06-10-project-synapse-master-plan.md`` §4 — the game,
  §1 coupling rule (additive route families, nothing ported to C++).
* ``docs/synapse/design/07-progression-neural-network.md`` — the 21-slot
  hex lattice (3 Core / 6 Inner / 12 Outer + Periphery dock), edge Thread
  costs 30/20/10 by tier pairing (§2), Resonance levels 1–50 (§3),
  promotions (§5), Den buff caps (§7).
* ``docs/synapse/design/04-roster-24-agents.md`` — the 24 agent ids, the
  8-domain ring. Persisted **by id only**; the full cards stay in the doc.
* ``docs/synapse/design/08-avatar-den-onboarding.md`` — the muse creator
  axes (§3.1), the five questions (§4), Den stages 1–3 (§7).

Write semantics (binding, documented for the route handlers): a write is a
**section-level merge** — the body may carry any subset of the top-level
sections (``muse`` / ``network`` / ``roster`` / ``den`` / ``progress`` /
``settings``); each provided section replaces that section wholesale and
omitted sections are left untouched. Unknown sections are rejected.

Every constraint violation raises :class:`GameValidationError` with a
specific, player-debuggable message; the handlers map it to HTTP 400.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SAVE_VERSION = 1

#: Number of save slots (1..MAX_SLOTS), master plan §4 save system.
MAX_SLOTS = 3


class GameValidationError(ValueError):
    """A save write violated a locked design constraint (-> HTTP 400)."""


# ---------------------------------------------------------------------------
# Design constants (sources cited per block — see module docstring)
# ---------------------------------------------------------------------------

# The 8-domain ring, in ring order. Each domain is strong vs. the next,
# weak vs. the previous (04-roster-24-agents.md §2). Ring order matters:
# synergy classification below derives Depth / Pipeline / Tension from
# ring distance (07-progression-neural-network.md §2.1).
DOMAIN_RING: tuple[str, ...] = (
    "architecture",
    "qa_test",
    "build_ops",
    "compliance",
    "behavior_psych",
    "research",
    "security",
    "release",
)

# The 24 launch agents by id -> domain (04-roster-24-agents.md §4, the
# roster-at-a-glance table). Ids only; the cards live in the design doc.
AGENT_DOMAINS: dict[str, str] = {
    "axiom": "architecture",
    "lattice": "architecture",
    "forgemind": "architecture",
    "warden": "security",
    "cipher": "security",
    "breach": "security",
    "contrarian": "qa_test",
    "nitpick": "qa_test",
    "redflag": "qa_test",
    "oracle": "research",
    "archivist": "research",
    "radar": "research",
    "foreman": "build_ops",
    "pipeline": "build_ops",
    "patch": "build_ops",
    "empath": "behavior_psych",
    "mirror": "behavior_psych",
    "neuron": "behavior_psych",
    "hazmat": "compliance",
    "clause": "compliance",
    "auditrix": "compliance",
    "commander": "release",
    "verdict": "release",
    "postmortem": "release",
}

#: Foundry-forged rares are outside the 24-roster but wire into the network
#: like any agent (09-foundry-spec.md §6); their ids carry this prefix.
FORGED_PREFIX = "forged-"

# The 21 wireable lattice slots (07-progression-neural-network.md §1.1):
# Core ring 3, Inner ring 6, Outer ring 12. The Nucleus is the muse (not an
# agent slot); the Periphery is an unlimited no-edge dock, stored separately.
LATTICE_SLOTS: tuple[str, ...] = (
    tuple(f"core-{i}" for i in range(1, 4))
    + tuple(f"inner-{i}" for i in range(1, 7))
    + tuple(f"outer-{i}" for i in range(1, 13))
)

#: Edge Thread cost by tier pairing (07 §2): 30 Core–Core / Core–Inner,
#: 20 Inner–Inner / Inner–Outer, 10 Outer–Outer. Core–Outer is not adjacent.
EDGE_COSTS: dict[frozenset[str], int] = {
    frozenset({"core"}): 30,
    frozenset({"core", "inner"}): 30,
    frozenset({"inner"}): 20,
    frozenset({"inner", "outer"}): 20,
    frozenset({"outer"}): 10,
}

THREAD_COSTS: tuple[int, ...] = (10, 20, 30)

RESONANCE_MIN, RESONANCE_MAX = 1, 50  # 07 §3: levels 1–50

DEN_STAGES: tuple[int, ...] = (1, 2, 3)  # 08 §7: Socket / Annex / Commons

# The 8 canonical Gauntlets — one per verification gate (master plan §4.9).
GAUNTLETS: tuple[str, ...] = (
    "planning",
    "build",
    "review",
    "test",
    "security",
    "release",
    "owner_approval",
    "rollback",
)

# The 5 zones (master plan §4.9 — fixed, do not grow).
ZONES: tuple[str, ...] = (
    "the_stacks",
    "the_foundry",
    "the_vault",
    "gardens_of_memory",
    "the_gate_spire",
)

# muse creator axes (08-avatar-den-onboarding.md §3.1).
MUSE_FRAMES: tuple[str, ...] = ("slight", "standard", "sturdy", "tall", "drifting")
MUSE_MATERIALS: tuple[str, ...] = (
    "brushed_alloy",
    "porcelain",
    "smoked_glass",
    "woven_thread",
    "basalt",
    "mother_of_pearl",
    "oxidized_copper",
    "soft_matte_polymer",
)
MUSE_FINISHES: tuple[str, ...] = ("matte", "satin", "polished", "weathered")
MUSE_FACE_PLATES: tuple[str, ...] = (
    "open",
    "visor",
    "twin_lens",
    "crescent",
    "lattice",
    "blank_warm",
    "asymmetric",
)
MUSE_VOICES: tuple[str, ...] = (
    "warm_low",
    "bright_quick",
    "measured_deep",
    "soft_static",
    "clipped_formal",
    "husky_worn",
)
MUSE_NAME_MIN, MUSE_NAME_MAX = 2, 16  # 08 §3.1: free text, 2–16 chars
MUSE_QUESTION_COUNT = 5  # 08 §4: the five questions

SECTIONS: tuple[str, ...] = ("muse", "network", "roster", "den", "progress", "settings")

#: Static design constants the UE/web client needs, served verbatim by
#: ``GET /v1/game/design``. One dict, every block citing its design doc.
DESIGN: dict[str, Any] = {
    "v": SAVE_VERSION,
    "sources": {
        "master_plan": "docs/plans/2026-06-10-project-synapse-master-plan.md",
        "lattice": "docs/synapse/design/07-progression-neural-network.md",
        "roster": "docs/synapse/design/04-roster-24-agents.md",
        "den": "docs/synapse/design/08-avatar-den-onboarding.md",
        "foundry": "docs/synapse/design/09-foundry-spec.md",
    },
    "lattice": {
        "slots": list(LATTICE_SLOTS),
        "tiers": {"core": 3, "inner": 6, "outer": 12},
        "thread_costs": {
            "core-core": 30,
            "core-inner": 30,
            "inner-inner": 20,
            "inner-outer": 20,
            "outer-outer": 10,
        },
    },
    "domains": list(DOMAIN_RING),
    "agents": {agent: domain for agent, domain in sorted(AGENT_DOMAINS.items())},
    "gauntlets": list(GAUNTLETS),
    "zones": list(ZONES),
    "resonance": {"min": RESONANCE_MIN, "max": RESONANCE_MAX},
    "den": {"stages": list(DEN_STAGES), "buff_pct_cap": 5, "max_buff_items": 6},
    "muse": {
        "frames": list(MUSE_FRAMES),
        "materials": list(MUSE_MATERIALS),
        "finishes": list(MUSE_FINISHES),
        "face_plates": list(MUSE_FACE_PLATES),
        "voices": list(MUSE_VOICES),
        "name_length": [MUSE_NAME_MIN, MUSE_NAME_MAX],
        "question_count": MUSE_QUESTION_COUNT,
    },
    "max_save_slots": MAX_SLOTS,
}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def game_dir() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    d = Path(base) / "jarvis_prime" / "game"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slot_path(slot: int) -> Path:
    return game_dir() / f"save-{slot}.json"


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Atomic JSON write (tmp + os.replace — the auth.py pattern)."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_slot(raw: Any) -> int:
    """Parse + range-check a slot number (1..MAX_SLOTS) or raise."""
    try:
        slot = int(str(raw))
    except (TypeError, ValueError):
        raise GameValidationError(
            f"slot: must be an integer 1..{MAX_SLOTS} (got {raw!r})"
        ) from None
    if not 1 <= slot <= MAX_SLOTS:
        raise GameValidationError(
            f"slot: must be 1..{MAX_SLOTS} (got {slot})"
        )
    return slot


# ---------------------------------------------------------------------------
# Validation (one function per section; specific messages, design-doc cited)
# ---------------------------------------------------------------------------


def _require_dict(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise GameValidationError(f"{name}: must be an object (got {type(value).__name__})")
    return value


def _known_agent(agent_id: Any, where: str) -> str:
    if not isinstance(agent_id, str) or not agent_id:
        raise GameValidationError(f"{where}: agent id must be a non-empty string")
    if agent_id in AGENT_DOMAINS or agent_id.startswith(FORGED_PREFIX):
        return agent_id
    raise GameValidationError(
        f"{where}: unknown agent id {agent_id!r} — must be one of the 24 roster ids "
        f"(04-roster-24-agents.md §4) or a Foundry rare ({FORGED_PREFIX}*)"
    )


def _tier(slot_id: str) -> str:
    return slot_id.split("-", 1)[0]


def _validate_muse(muse: Any) -> dict:
    muse = _require_dict(muse, "muse")
    checks: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("frame", MUSE_FRAMES),
        ("material", MUSE_MATERIALS),
        ("finish", MUSE_FINISHES),
        ("face", MUSE_FACE_PLATES),
        ("voice", MUSE_VOICES),
    )
    for key, allowed in checks:
        if key in muse and muse[key] not in allowed:
            raise GameValidationError(
                f"muse.{key}: {muse[key]!r} is not one of {', '.join(allowed)} "
                "(08-avatar-den-onboarding.md §3.1)"
            )
    if "name" in muse:
        name = muse["name"]
        if not isinstance(name, str) or not (MUSE_NAME_MIN <= len(name) <= MUSE_NAME_MAX):
            raise GameValidationError(
                f"muse.name: must be a string of {MUSE_NAME_MIN}-{MUSE_NAME_MAX} "
                f"characters (08 §3.1; got {name!r})"
            )
    if "answers" in muse:
        answers = muse["answers"]
        if not isinstance(answers, list) or len(answers) > MUSE_QUESTION_COUNT:
            raise GameValidationError(
                f"muse.answers: at most {MUSE_QUESTION_COUNT} personality answers "
                "(08 §4, the five questions)"
            )
    return muse


def _validate_network(network: Any) -> dict:
    network = _require_dict(network, "network")
    slots = _require_dict(network.get("slots", {}), "network.slots")
    if len(slots) > len(LATTICE_SLOTS):
        raise GameValidationError(
            f"network.slots: at most {len(LATTICE_SLOTS)} wired slots "
            "(07-progression-neural-network.md §1.1)"
        )
    placed: dict[str, str] = {}
    for slot_id, agent_id in slots.items():
        if slot_id not in LATTICE_SLOTS:
            raise GameValidationError(
                f"network.slots: unknown slot id {slot_id!r} — the lattice is "
                "core-1..3 / inner-1..6 / outer-1..12 (07 §1.1)"
            )
        agent = _known_agent(agent_id, f"network.slots[{slot_id}]")
        if agent in placed.values():
            raise GameValidationError(
                f"network.slots: agent {agent!r} is placed in more than one slot"
            )
        placed[slot_id] = agent

    periphery = network.get("periphery", [])
    if not isinstance(periphery, list):
        raise GameValidationError("network.periphery: must be a list of agent ids")
    for i, agent_id in enumerate(periphery):
        _known_agent(agent_id, f"network.periphery[{i}]")

    edges = network.get("edges", [])
    if not isinstance(edges, list):
        raise GameValidationError("network.edges: must be a list")
    seen_edges: set[frozenset[str]] = set()
    for i, edge in enumerate(edges):
        edge = _require_dict(edge, f"network.edges[{i}]")
        for end in ("a", "b"):
            val = edge.get(end)
            if not isinstance(val, str) or val not in LATTICE_SLOTS:
                raise GameValidationError(
                    f"network.edges[{i}].{end}: unknown slot id {val!r}"
                )
        a, b = str(edge["a"]), str(edge["b"])
        if a == b:
            raise GameValidationError(
                f"network.edges[{i}]: an edge cannot connect a slot to itself"
            )
        for end, val in (("a", a), ("b", b)):
            if val not in placed:
                raise GameValidationError(
                    f"network.edges[{i}].{end}: slot {val!r} is unoccupied — edges "
                    "exist only between adjacent occupied slots (07 §2)"
                )
        key = frozenset({a, b})
        if key in seen_edges:
            raise GameValidationError(f"network.edges[{i}]: duplicate edge {a}–{b}")
        seen_edges.add(key)
        cost = edge.get("cost")
        if cost not in THREAD_COSTS:
            raise GameValidationError(
                f"network.edges[{i}].cost: Thread cost must be one of "
                f"{'/'.join(map(str, THREAD_COSTS))} (07 §2; got {cost!r})"
            )
        expected = EDGE_COSTS.get(frozenset({_tier(a), _tier(b)}))
        if expected is None:
            raise GameValidationError(
                f"network.edges[{i}]: {_tier(a)}–{_tier(b)} slots are never "
                "adjacent in the lattice (07 §1.1)"
            )
        if cost != expected:
            raise GameValidationError(
                f"network.edges[{i}].cost: a {_tier(a)}–{_tier(b)} edge costs "
                f"{expected} Synapse Thread (07 §2; got {cost})"
            )
    network["synergy_summary"] = _synergy_summary(placed, edges)
    return network


def _synergy_summary(placed: dict[str, str], edges: list[dict]) -> dict:
    """Recompute the synergy summary from wiring (07 §2.1) — server-derived,
    never trusted from the client. Forged agents (unknown domain) classify as
    lattice-integrity, the catch-all pairing class."""
    counts = {"depth": 0, "pipeline": 0, "tension": 0, "integrity": 0}
    thread_spent = 0
    for edge in edges:
        thread_spent += int(edge["cost"])
        da = AGENT_DOMAINS.get(placed[edge["a"]])
        db = AGENT_DOMAINS.get(placed[edge["b"]])
        if da is None or db is None:
            counts["integrity"] += 1
            continue
        dist = abs(DOMAIN_RING.index(da) - DOMAIN_RING.index(db))
        dist = min(dist, len(DOMAIN_RING) - dist)
        if dist == 0:
            counts["depth"] += 1
        elif dist == 1:
            counts["pipeline"] += 1
        elif dist == 4:
            counts["tension"] += 1
        else:
            counts["integrity"] += 1
    return {**counts, "edges": len(edges), "thread_spent": thread_spent}


def _validate_roster(roster: Any) -> list:
    if not isinstance(roster, list):
        raise GameValidationError("roster: must be a list of caught-agent entries")
    seen: set[str] = set()
    for i, entry in enumerate(roster):
        entry = _require_dict(entry, f"roster[{i}]")
        agent = _known_agent(entry.get("agent_id"), f"roster[{i}].agent_id")
        if agent in seen:
            raise GameValidationError(f"roster[{i}]: duplicate agent {agent!r}")
        seen.add(agent)
        level = entry.get("resonance_level", RESONANCE_MIN)
        if not isinstance(level, int) or not RESONANCE_MIN <= level <= RESONANCE_MAX:
            raise GameValidationError(
                f"roster[{i}].resonance_level: must be an integer "
                f"{RESONANCE_MIN}-{RESONANCE_MAX} (07 §3; got {level!r})"
            )
        if not isinstance(entry.get("promoted", False), bool):
            raise GameValidationError(f"roster[{i}].promoted: must be a boolean")
    return roster


def _validate_den(den: Any) -> dict:
    den = _require_dict(den, "den")
    stage = den.get("stage", 1)
    if stage not in DEN_STAGES:
        raise GameValidationError(
            f"den.stage: must be 1, 2 or 3 (08 §7 — Socket/Annex/Commons; got {stage!r})"
        )
    items = den.get("items", [])
    if not isinstance(items, list):
        raise GameValidationError("den.items: must be a list of room item ids")
    for i, ref in enumerate(items):
        item_id = ref.get("item_id") if isinstance(ref, dict) else ref
        if not isinstance(item_id, str) or not item_id:
            raise GameValidationError(
                f"den.items[{i}]: must be a room item id string (or an object "
                "with item_id) referencing the room_store manifest"
            )
    return den


def _validate_progress(progress: Any) -> dict:
    progress = _require_dict(progress, "progress")
    zones = progress.get("zones_unlocked", [])
    if not isinstance(zones, list):
        raise GameValidationError("progress.zones_unlocked: must be a list")
    for zone in zones:
        if zone not in ZONES:
            raise GameValidationError(
                f"progress.zones_unlocked: unknown zone {zone!r} — the five zones "
                f"are {', '.join(ZONES)} (master plan §4.9)"
            )
    cleared = progress.get("gauntlets_cleared", [])
    if not isinstance(cleared, list):
        raise GameValidationError("progress.gauntlets_cleared: must be a list")
    for g in cleared:
        if g not in GAUNTLETS:
            raise GameValidationError(
                f"progress.gauntlets_cleared: unknown gauntlet {g!r} — the eight "
                f"gates are {', '.join(GAUNTLETS)} (master plan §4.9)"
            )
    if len(set(cleared)) != len(cleared):
        raise GameValidationError("progress.gauntlets_cleared: duplicate gauntlet")
    flags = progress.get("campaign_flags", {})
    _require_dict(flags, "progress.campaign_flags")
    return progress


def _validate_settings(settings: Any) -> dict:
    return _require_dict(settings, "settings")


_SECTION_VALIDATORS = {
    "muse": _validate_muse,
    "network": _validate_network,
    "roster": _validate_roster,
    "den": _validate_den,
    "progress": _validate_progress,
    "settings": _validate_settings,
}

_EMPTY_SECTIONS: dict[str, Any] = {
    "muse": {},
    "network": {"slots": {}, "edges": [], "periphery": [], "synergy_summary": {}},
    "roster": [],
    "den": {"stage": 1, "items": []},
    "progress": {"zones_unlocked": [], "gauntlets_cleared": [], "campaign_flags": {}},
    "settings": {},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_slot(slot: int) -> Optional[dict]:
    """The full save document for ``slot``, or None when the slot is empty."""
    try:
        return json.loads(_slot_path(slot).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def list_slots() -> list[dict]:
    """Per-slot summaries for the save-select screen (never full documents)."""
    summaries = []
    for slot in range(1, MAX_SLOTS + 1):
        save = load_slot(slot)
        if save is None:
            summaries.append({"slot": slot, "exists": False})
            continue
        summaries.append(
            {
                "slot": slot,
                "exists": True,
                "created_at": save.get("created_at"),
                "updated_at": save.get("updated_at"),
                "muse_name": (save.get("muse") or {}).get("name"),
                "roster_count": len(save.get("roster") or []),
                "den_stage": (save.get("den") or {}).get("stage"),
                "gauntlets_cleared": len(
                    (save.get("progress") or {}).get("gauntlets_cleared") or []
                ),
            }
        )
    return summaries


def write_slot(slot: int, sections: dict) -> tuple[dict, bool]:
    """Validate + persist a section-level merge into ``slot``.

    ``sections`` carries any subset of :data:`SECTIONS`; each provided
    section replaces that section wholesale, omitted sections are untouched
    (the documented merge semantics). Returns ``(save, created)``. Raises
    :class:`GameValidationError` on any constraint violation — nothing is
    written on a rejected body (validate-all-then-write).
    """
    if not isinstance(sections, dict) or not sections:
        raise GameValidationError(
            f"body: provide at least one section of {', '.join(SECTIONS)}"
        )
    unknown = sorted(set(sections) - set(SECTIONS))
    if unknown:
        raise GameValidationError(
            f"unknown section(s) {', '.join(map(repr, unknown))} — valid sections "
            f"are {', '.join(SECTIONS)}"
        )
    validated = {
        name: _SECTION_VALIDATORS[name](value) for name, value in sections.items()
    }
    existing = load_slot(slot)
    created = existing is None
    now = _now_iso()
    save = existing or {
        "v": SAVE_VERSION,
        "slot": slot,
        "created_at": now,
        **{name: json.loads(json.dumps(v)) for name, v in _EMPTY_SECTIONS.items()},
    }
    save.update(validated)
    save["v"] = SAVE_VERSION
    save["slot"] = slot
    save["updated_at"] = now
    _atomic_write_json(_slot_path(slot), save)
    return save, created


def delete_slot(slot: int) -> bool:
    try:
        _slot_path(slot).unlink()
        return True
    except FileNotFoundError:
        return False


__all__ = [
    "AGENT_DOMAINS",
    "DESIGN",
    "DOMAIN_RING",
    "FORGED_PREFIX",
    "GAUNTLETS",
    "GameValidationError",
    "LATTICE_SLOTS",
    "MAX_SLOTS",
    "SAVE_VERSION",
    "SECTIONS",
    "THREAD_COSTS",
    "ZONES",
    "delete_slot",
    "game_dir",
    "list_slots",
    "load_slot",
    "parse_slot",
    "write_slot",
]
