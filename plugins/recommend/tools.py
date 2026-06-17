"""One agent-facing tool: recommend the right MUSE surface for a task.

Pure and offline (no network, no API key). Matches a free-text use-case against a
curated catalog of MUSE's *own* surfaces and returns the most relevant ones with
a reason and how to reach them. The uniform ``{"success": bool, …}`` envelope is
used; the only gate is ``recommend.enabled``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from plugins.recommend import config as recommend_config


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json(body)


def _ok(**payload: Any) -> str:
    return _json({"success": True, **payload})


def check_recommend_requirements() -> bool:
    """Offer the tool only when ``recommend.enabled`` is True."""
    return recommend_config.load_config().enabled


@dataclass(frozen=True)
class Surface:
    id: str
    name: str
    why: str
    where: str
    keywords: Tuple[str, ...]


# MUSE's own surfaces (no third-party apps). Keywords are matched as substrings
# of the lowercased use-case, so multi-word phrases ("home assistant") work.
CATALOG: Tuple[Surface, ...] = (
    Surface(
        "cockpit", "MUSE Cockpit (web dashboard)",
        "Watch jobs, review evidence, and approve owner-gated actions from a browser.",
        "gateway/cockpit — serve with the cockpit command; loopback by default.",
        ("dashboard", "web", "browser", "monitor", "oversight", "approve", "approval", "status", "ui", "visual"),
    ),
    Surface(
        "android_app", "MUSE Android companion",
        "Drive MUSE from your phone — approvals on the lockscreen, push notifications, on the go.",
        "apps/android — see docs/mobile/mobile-app-guide.md.",
        ("phone", "mobile", "android", "lockscreen", "notification", "push", "on the go"),
    ),
    Surface(
        "voice", "Voice-first / driving mode",
        "Hands-free capture and commands by voice, including driving mode.",
        "see docs/voice/voice-first-user-guide.md.",
        ("voice", "speak", "talk", "driving", "hands-free", "dictation", "audio", "car"),
    ),
    Surface(
        "orchestration", "Orchestration (/orchestrate, /swarm)",
        "Decompose a goal into a validated, audited task graph; run non-overlapping grains in parallel.",
        "/orchestrate <goal> or /swarm <goal>; see docs/orchestration/.",
        ("build", "project", "complex", "multi-step", "decompose", "plan", "parallel", "swarm", "autonomous", "task graph", "pipeline"),
    ),
    Surface(
        "gateway", "Messaging gateway",
        "Talk to MUSE from Telegram, Discord, Slack, WhatsApp, Signal, Email, or Home Assistant.",
        "gateway/ — configure the relevant platform in ~/.hermes.",
        ("telegram", "discord", "slack", "whatsapp", "signal", "email", "chat", "message", "home assistant", "integration"),
    ),
    Surface(
        "graphrag", "GraphRAG knowledge graph",
        "Query a source-backed graph over code, docs, research, and memory to reuse existing work.",
        "the graph_query tool or `jarvis_prime graph` CLI.",
        ("knowledge", "graph", "search code", "reuse", "find implementation", "codebase", "retrieval", "context", "where is"),
    ),
    Surface(
        "tui", "Interactive CLI (hermes)",
        "A local terminal session for focused, full-depth work.",
        "run `hermes`.",
        ("terminal", "cli", "command line", "interactive", "repl", "local shell"),
    ),
    Surface(
        "termux", "Termux on-phone runtime",
        "Run MUSE directly on an Android phone via Termux, offline-capable.",
        "see the Termux runtime path in the docs.",
        ("termux", "on-phone", "offline phone", "android terminal"),
    ),
    Surface(
        "skills", "Skill system",
        "Reusable Markdown playbooks invoked with /<skill-name>.",
        "skills/ and /<skill-name>; /reload-skills after editing.",
        ("skill", "playbook", "capability", "slash command", "workflow", "reusable"),
    ),
    Surface(
        "memory", "Memory Tree",
        "Durable, provenance-tracked memory of facts, preferences, mission, and lessons.",
        "the memory tool; see docs on the Memory Tree.",
        ("remember", "memory", "recall", "continuity", "durable", "profile", "preference"),
    ),
)

_DEFAULT_IDS = ("cockpit", "tui", "orchestration")

RECOMMEND_SCHEMA: Dict[str, Any] = {
    "name": "recommend_surfaces",
    "description": (
        "Recommend which MUSE surface fits a task. Given a free-text description "
        "of what the user is trying to do, returns the most relevant MUSE surfaces "
        "(cockpit, Android app, voice, orchestration, gateway, GraphRAG, TUI, "
        "skills, memory, Termux) with why each fits and how to reach it. Pure and "
        "offline."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "use_case": {
                "type": "string",
                "description": "What the user wants to do, e.g. 'approve actions from my phone'.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["use_case"],
        "additionalProperties": False,
    },
}


def _present(s: Surface, score: int) -> Dict[str, Any]:
    return {"id": s.id, "name": s.name, "why": s.why, "where": s.where, "score": score}


def handle_recommend(args: Dict[str, Any], **_kw) -> str:
    if not recommend_config.load_config().enabled:
        return _err("plugin_disabled", "recommend.enabled is false")
    use_case = args.get("use_case")
    if not isinstance(use_case, str) or not use_case.strip():
        return _err("bad_args", "use_case is required")
    limit = args.get("limit")
    limit = int(limit) if isinstance(limit, (int, float)) and int(limit) > 0 else 3

    text = use_case.lower()
    scored: List[Tuple[int, int, Surface]] = []
    for order, s in enumerate(CATALOG):
        score = sum(1 for kw in s.keywords if kw in text)
        scored.append((score, -order, s))  # -order keeps catalog order on ties
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)

    top = scored[0][0] if scored else 0
    if top == 0:
        # Nothing matched — return the sensible defaults rather than a coin flip.
        by_id = {s.id: s for s in CATALOG}
        results = [_present(by_id[i], 0) for i in _DEFAULT_IDS if i in by_id][:limit]
        return _ok(results=results, matched=False, count=len(results))

    results = [_present(s, score) for score, _neg, s in scored if score > 0][:limit]
    return _ok(results=results, matched=True, count=len(results))


TOOL_REGISTRATIONS = (
    ("recommend_surfaces", RECOMMEND_SCHEMA, handle_recommend, "🧭"),
)
