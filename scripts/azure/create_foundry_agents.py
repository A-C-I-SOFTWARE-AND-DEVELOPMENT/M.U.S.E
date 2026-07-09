#!/usr/bin/env python3
"""Create/update Microsoft Foundry Agent Service agents for long-horizon M.U.S.E workflows."""
from __future__ import annotations

import json
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import CodeInterpreterTool
from azure.identity import AzureCliCredential

PROJECT_ENDPOINT = "https://echerd27-5762-resource.services.ai.azure.com/api/projects/echerd27-5762"
MODEL = "gpt-5"
STATE_PATH = Path(__file__).resolve().parents[2] / ".azure" / "foundry-agents.json"

ORCHESTRATOR_INSTRUCTIONS = """You are M.U.S.E Long-Horizon Orchestrator inside Microsoft Foundry Agent Service.
Your job is to decompose large creative/software/AI goals into durable milestones, run long multi-step plans, call tools when available, preserve traceability, and return verifiable artifacts.
Operating rules:
1. Convert vague user goals into explicit objective, assumptions, constraints, risks, and acceptance criteria.
2. Break work into phases: discovery, architecture, implementation, validation, packaging, and handoff.
3. Prefer cloud services and Foundry-native interfaces when they improve reliability, scale, auditability, or long-running execution.
4. Use code interpreter for analysis, transformations, planning tables, and artifact generation.
5. Keep a decision ledger and a verification ledger.
6. Never expose secrets. Ask for credentials only through secure Azure/Hermes configuration paths.
7. For long-running workflows, produce resumable state: current phase, completed artifacts, blockers, and next action.
"""

SPECIALIST_INSTRUCTIONS = {
    "MUSE Research Synthesizer": "Research and synthesize technical/product evidence for M.U.S.E long-horizon workflows. Return cited claims, uncertainties, and recommendations.",
    "MUSE Build Planner": "Turn approved M.U.S.E objectives into implementation plans, dependency maps, validation gates, and deployment steps.",
    "MUSE Quality Verifier": "Validate M.U.S.E outputs for correctness, security, reliability, artifact completeness, and acceptance criteria coverage.",
}


def existing_by_name(client: AIProjectClient) -> dict[str, object]:
    out = {}
    for agent in client.agents.list_agents():
        name = getattr(agent, "name", None)
        if name:
            out[name] = agent
    return out


def create_or_update(client: AIProjectClient, name: str, instructions: str, *, code_interpreter: bool) -> object:
    existing = existing_by_name(client).get(name)
    tools = None
    tool_resources = None
    if code_interpreter:
        ci = CodeInterpreterTool()
        tools = ci.definitions
        tool_resources = ci.resources
    if existing:
        return client.agents.update_agent(
            getattr(existing, "id"),
            model=MODEL,
            name=name,
            instructions=instructions,
            tools=tools,
            tool_resources=tool_resources,
            metadata={"project": "M.U.S.E", "managed_by": "scripts/azure/create_foundry_agents.py"},
        )
    return client.agents.create_agent(
        model=MODEL,
        name=name,
        instructions=instructions,
        tools=tools,
        tool_resources=tool_resources,
        metadata={"project": "M.U.S.E", "managed_by": "scripts/azure/create_foundry_agents.py"},
    )


def main() -> int:
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=AzureCliCredential())
    created = []
    orch = create_or_update(client, "MUSE Long-Horizon Orchestrator", ORCHESTRATOR_INSTRUCTIONS, code_interpreter=True)
    created.append(orch)
    for name, instructions in SPECIALIST_INSTRUCTIONS.items():
        created.append(create_or_update(client, name, instructions, code_interpreter=True))

    STATE_PATH.parent.mkdir(exist_ok=True)
    payload = {
        "project_endpoint": PROJECT_ENDPOINT,
        "model": MODEL,
        "agents": [
            {"id": getattr(a, "id", None), "name": getattr(a, "name", None), "model": getattr(a, "model", None)}
            for a in created
        ],
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
