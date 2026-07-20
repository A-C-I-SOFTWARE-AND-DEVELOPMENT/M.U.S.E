"""Agent Factory — runtime creation of specialist agents.

Extends the static AoS council registry with the ability to mint new
specialist agents at runtime from a capability spec. Agents are written to
the operating registry so the existing dispatcher can route to them.

Key types:
    AgentSpec: dataclass describing a specialist (name, capabilities, model, ...)
    create_agent(spec): register a new agent in the operating registry
    delete_agent(agent_id): remove an agent from the registry
    create_from_task(task_description, model): LLM-driven spec generation

The registry file is JSON — safe to read/write from a single process. For
multi-process concurrency, wrap calls in a filelock.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

__all__ = [
    "AgentSpec",
    "create_agent",
    "delete_agent",
    "get_agent",
    "list_agents",
    "create_from_task",
    "default_registry_path",
]


# ---------------------------------------------------------------------------
# Registry path resolution
# ---------------------------------------------------------------------------


def default_registry_path() -> Path:
    """Locate the operating registry relative to the repo root."""
    here = Path(__file__).resolve()
    # .../hermes_cli/jarvis_prime/aos_council/agent_factory.py → repo root
    repo_root = here.parents[3]
    return repo_root / "skills" / "aos-enterprise-council" / "operating-registry" / "registry.json"


# ---------------------------------------------------------------------------
# AgentSpec
# ---------------------------------------------------------------------------


@dataclass
class AgentSpec:
    """Runtime-mintable specialist agent specification."""

    name: str
    capabilities: list[str]
    model: str
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    base_url: Optional[str] = None
    provider: Optional[str] = None
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    reputation: float = 0.5  # prior — updated by agent_market.record_outcome
    when_to_use: str = ""
    when_not_to_use: str = ""
    verification_method: str = "owner_review"
    owner_gate: bool = False
    agent_id: str = field(default_factory=lambda: f"agent-{uuid.uuid4().hex[:12]}")
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSpec":
        # Tolerate missing keys on read so old entries still load
        return cls(
            name=data["name"],
            capabilities=list(data.get("capabilities", [])),
            model=data.get("model", ""),
            system_prompt=data.get("system_prompt", ""),
            tools=list(data.get("tools", [])),
            base_url=data.get("base_url"),
            provider=data.get("provider"),
            cost_per_1k_input=float(data.get("cost_per_1k_input", 0.0)),
            cost_per_1k_output=float(data.get("cost_per_1k_output", 0.0)),
            reputation=float(data.get("reputation", 0.5)),
            when_to_use=data.get("when_to_use", ""),
            when_not_to_use=data.get("when_not_to_use", ""),
            verification_method=data.get("verification_method", "owner_review"),
            owner_gate=bool(data.get("owner_gate", False)),
            agent_id=data.get("agent_id") or f"agent-{uuid.uuid4().hex[:12]}",
            created_at=data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
        )


# ---------------------------------------------------------------------------
# Registry I/O
# ---------------------------------------------------------------------------


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": "3.1.0",
            "dynamic_agents": [],
            "created_by": "agent_factory",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _save_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "agent"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_agent(spec: AgentSpec, registry_path: Optional[Path] = None) -> str:
    """Register a new agent. Returns the agent_id."""
    path = registry_path or default_registry_path()
    data = _load_registry(path)
    agents = data.setdefault("dynamic_agents", [])

    # Replace if agent_id already present, else append
    for i, existing in enumerate(agents):
        if existing.get("agent_id") == spec.agent_id:
            agents[i] = spec.to_dict()
            _save_registry(path, data)
            return spec.agent_id

    agents.append(spec.to_dict())
    _save_registry(path, data)
    return spec.agent_id


def get_agent(agent_id: str, registry_path: Optional[Path] = None) -> Optional[AgentSpec]:
    path = registry_path or default_registry_path()
    data = _load_registry(path)
    for entry in data.get("dynamic_agents", []):
        if entry.get("agent_id") == agent_id:
            return AgentSpec.from_dict(entry)
    return None


def list_agents(registry_path: Optional[Path] = None) -> list[AgentSpec]:
    path = registry_path or default_registry_path()
    data = _load_registry(path)
    return [AgentSpec.from_dict(e) for e in data.get("dynamic_agents", [])]


def delete_agent(agent_id: str, registry_path: Optional[Path] = None) -> bool:
    """Remove an agent. Returns True if removed, False if not found."""
    path = registry_path or default_registry_path()
    data = _load_registry(path)
    agents = data.get("dynamic_agents", [])
    new_agents = [a for a in agents if a.get("agent_id") != agent_id]
    if len(new_agents) == len(agents):
        return False
    data["dynamic_agents"] = new_agents
    _save_registry(path, data)
    return True


# ---------------------------------------------------------------------------
# LLM-driven spec generation (optional, lightweight)
# ---------------------------------------------------------------------------


_SPEC_PROMPT = """You are an agent spec generator. Given a task description,
produce a JSON object describing the specialist agent best suited to execute it.

Required keys:
  name: short human name (e.g. "rust-fixer")
  capabilities: list of 3-7 lowercase capability tags (e.g. ["rust", "cargo", "ffi"])
  system_prompt: 2-4 sentence instruction for the agent
  tools: list of tool names from [terminal, read_file, write_file, patch, search_files, browser_navigate, delegate_task]
  when_to_use: one-sentence routing hint
  when_not_to_use: one-sentence routing hint

Output ONLY valid JSON, no commentary.

Task: {task}
"""


def create_from_task(
    task_description: str,
    model: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    registry_path: Optional[Path] = None,
) -> AgentSpec:
    """Use an LLM to generate an AgentSpec from a free-form task description.

    Falls back to a minimal generic spec if the LLM call fails or returns
    invalid JSON.
    """
    try:
        from openai import OpenAI  # local import so the module is stdlib-only without it

        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": _SPEC_PROMPT.format(task=task_description)}
            ],
            temperature=0.3,
            timeout=30.0,
        )
        text = response.choices[0].message.content or ""
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
        payload = json.loads(text)
        spec = AgentSpec(
            name=_slugify(payload.get("name", "agent")),
            capabilities=[str(c).lower() for c in payload.get("capabilities", [])][:8],
            model=model,
            system_prompt=str(payload.get("system_prompt", ""))[:2000],
            tools=[str(t) for t in payload.get("tools", [])][:16],
            base_url=base_url,
            when_to_use=str(payload.get("when_to_use", ""))[:500],
            when_not_to_use=str(payload.get("when_not_to_use", ""))[:500],
        )
    except Exception:
        # Fallback: minimal generic spec so dispatch still has *something*
        spec = AgentSpec(
            name=_slugify(task_description.split()[0] if task_description else "agent"),
            capabilities=["general"],
            model=model,
            system_prompt=f"You are a specialist for: {task_description}",
            tools=["terminal", "read_file", "write_file"],
            base_url=base_url,
            when_to_use=task_description[:200],
        )

    create_agent(spec, registry_path=registry_path)
    return spec
