#!/usr/bin/env python3
"""Represent the full M.U.S.E repository in Microsoft Foundry.

Creates a safe, secret-free Azure representation of:
- datasets and dataset-producing assets
- pipelines and orchestration flows
- Karpathy/LLM-wiki/RAG knowledge surfaces
- docs, skills, configs, scripts, and agent manifests
- Foundry Agent Service file_search vector store attached to M.U.S.E agents

The script intentionally uploads generated manifests/digests, not raw secrets or local caches.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from azure.ai.agents.models import CodeInterpreterTool, CodeInterpreterToolResource, FileSearchTool, FileSearchToolResource, ToolResources
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / ".azure"
PAYLOAD_DIR = STATE_DIR / "sync_payload"
STATE_PATH = STATE_DIR / "muse-foundry-sync.json"
AGENTS_STATE = STATE_DIR / "foundry-agents.json"
PROJECT_ENDPOINT = "https://echerd27-5762-resource.services.ai.azure.com/api/projects/echerd27-5762"
MODEL = "gpt-5"
VECTOR_STORE_NAME = "MUSE full project RAG"

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", ".next", "dist", "build", "target",
    ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache", ".azure", ".cache",
    "logs", "tmp", "data", "temp_vision_images", "browser-use", "agent-browser",
}
EXCLUDE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp4", ".mov", ".avi", ".mkv",
    ".mp3", ".wav", ".flac", ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dll",
    ".so", ".dylib", ".bin", ".onnx", ".safetensors", ".pt", ".pth", ".gguf", ".sqlite", ".db",
    ".lock", ".pyc",
}
SECRETISH = re.compile(r"(?i)(api[_-]?key|secret|password|token|credential|connectionstring|private[_-]?key|bearer\s+[a-z0-9._-]+)")
TEXT_SUFFIXES = {".md", ".txt", ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".sh", ".ps1", ".html", ".css", ".sql", ".csv", ".jsonl"}


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def rel(p: Path) -> str:
    return p.relative_to(PROJECT_ROOT).as_posix()


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    name = path.name.lower()
    if name in {".env", ".env.local", ".env.development", ".env.test", ".env.production"}:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    if SECRETISH.search(rel(path)):
        return True
    return False


def category(path: Path) -> str:
    r = rel(path).lower()
    n = path.name.lower()
    if "/dataset" in r or "dataset" in n or r.startswith("datasets/") or r.startswith("source-data/"):
        return "datasets"
    if "pipeline" in r or r.startswith(".github/workflows/") or "orchestrator" in r or "research_fabric" in r:
        return "pipelines"
    if "rag" in r or "retriev" in r or "embedding" in r or "vector" in r:
        return "rag"
    if "wiki" in r or "karpathy" in r or "llm-wiki" in r:
        return "karpathy_llm_wiki"
    if r.startswith("skills/") or r.startswith("optional-skills/"):
        return "skills"
    if r.startswith("docs/") or r.startswith("website/docs/"):
        return "docs"
    if r.startswith("agent/") or r.startswith("hermes_cli/"):
        return "runtime"
    if r.startswith("config/") or r.endswith("config.yaml"):
        return "config"
    if r.startswith("scripts/"):
        return "scripts"
    if r.startswith("tests/"):
        return "tests"
    return "other"


def safe_snippet(path: Path, limit: int = 1800) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""
    # Redact any suspicious inline credential assignments.
    redacted = []
    for line in text.splitlines()[:80]:
        if SECRETISH.search(line):
            redacted.append("[REDACTED secret-like line]")
        else:
            redacted.append(line[:300])
    return "\n".join(redacted)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_repo() -> list[dict[str, Any]]:
    files = []
    for p in PROJECT_ROOT.rglob("*"):
        if not p.is_file() or should_skip(p):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 2_000_000:
            continue
        files.append({
            "path": rel(p),
            "category": category(p),
            "suffix": p.suffix.lower(),
            "size": size,
            "sha256": sha256(p) if size <= 1_000_000 else None,
            "snippet": safe_snippet(p) if size <= 120_000 and category(p) in {"datasets", "pipelines", "rag", "karpathy_llm_wiki", "docs", "skills", "config"} else "",
        })
    return sorted(files, key=lambda x: (x["category"], x["path"]))


def write_payload(files: list[dict[str, Any]]) -> list[Path]:
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    counts = Counter(f["category"] for f in files)
    suffix_counts = Counter(f["suffix"] or "[none]" for f in files)

    inventory = PAYLOAD_DIR / "muse_repo_inventory.jsonl"
    with inventory.open("w", encoding="utf-8") as out:
        for f in files:
            out.write(json.dumps(f, ensure_ascii=False) + "\n")

    overview = PAYLOAD_DIR / "muse_full_azure_representation.md"
    overview.write_text(f"""# M.U.S.E Full Azure Representation

Generated: {now}
Project endpoint: {PROJECT_ENDPOINT}
Model: {MODEL}

This document is the top-level Azure-side representation of M.U.S.E. It is designed for Foundry Agent Service file_search/RAG and long-horizon agentic workflows.

## Representation layers

- Repository inventory: {len(files)} safe files scanned.
- Datasets: dataset files, dataset-producing scripts, eval/sample datasets, and source-data pointers.
- Pipelines: CI, orchestration, studio, research-fabric, Teams, and Azure sync pipelines.
- Karpathy system: LLM-wiki / compiled markdown knowledge-base pattern and related docs.
- RAG: Foundry vector store built from this representation pack and attached to M.U.S.E agents.
- Agents: Orchestrator, Research Synthesizer, Build Planner, Quality Verifier.
- Hermes config: provider/router/Azure config represented as redacted metadata.

## Category counts

{yaml.safe_dump(dict(counts), sort_keys=True)}

## File type counts

{yaml.safe_dump(dict(suffix_counts.most_common(40)), sort_keys=False)}

## Security

Secret-like file paths and lines are excluded/redacted. Local caches, venvs, node_modules, .git, .env files, binary model weights, media, databases, and build outputs are excluded.
""", encoding="utf-8")

    def write_category_doc(cat: str, title: str, extra: str = "") -> Path:
        path = PAYLOAD_DIR / f"muse_{cat}.md"
        selected = [f for f in files if f["category"] == cat]
        lines = [f"# {title}", "", extra.strip(), "", f"Total represented files: {len(selected)}", ""]
        for f in selected[:700]:
            lines.append(f"## `{f['path']}`")
            lines.append(f"- size: {f['size']}")
            lines.append(f"- sha256: {f['sha256'] or 'omitted'}")
            if f.get("snippet"):
                lines.append("\n```text")
                lines.append(f["snippet"][:1800])
                lines.append("```")
            lines.append("")
        if len(selected) > 700:
            lines.append(f"\nAdditional files omitted from this category doc: {len(selected)-700}; see muse_repo_inventory.jsonl.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    path_index = PAYLOAD_DIR / "muse_path_index.md"
    path_index.write_text("# M.U.S.E Complete Path Index\n\n" + "\n".join(f"- [{f['category']}] `{f['path']}` ({f['size']} bytes)" for f in files), encoding="utf-8")

    docs = [
        overview,
        path_index,
        write_category_doc("datasets", "M.U.S.E Dataset Registry", "Dataset assets and dataset-producing scripts represented for Foundry."),
        write_category_doc("pipelines", "M.U.S.E Pipeline Registry", "CI, orchestration, studio, research-fabric, and cloud sync pipelines."),
        write_category_doc("rag", "M.U.S.E RAG Registry", "Retrieval, embedding, vector, parsing, and GraphRAG-related assets."),
        write_category_doc("karpathy_llm_wiki", "M.U.S.E Karpathy LLM Wiki Registry", "Compiled markdown knowledge-system / RAG-alternative surfaces."),
        write_category_doc("skills", "M.U.S.E Skill Registry", "Hermes skill library represented for agent routing and knowledge retrieval."),
        write_category_doc("docs", "M.U.S.E Documentation Registry", "Docs represented for project-wide cloud retrieval."),
        write_category_doc("config", "M.U.S.E Configuration Registry", "Redacted configuration manifests and Azure connection metadata."),
    ]
    return docs


def load_agents() -> dict[str, str]:
    if AGENTS_STATE.exists():
        data = json.loads(AGENTS_STATE.read_text(encoding="utf-8"))
        return {a["name"]: a["id"] for a in data.get("agents", []) if a.get("name") and a.get("id")}
    return {}


def upload_and_index(client: AIProjectClient, payload_files: list[Path]) -> tuple[list[dict[str, str]], str]:
    uploaded = []
    for p in payload_files:
        # upload_and_poll currently has an SDK paging edge case on some Windows installs;
        # upload returns a processed file for these manifest-sized text assets.
        print(f"UPLOAD {p.name} {p.stat().st_size} bytes", flush=True)
        info = client.agents.files.upload(file_path=str(p), purpose="assistants")
        uploaded.append({"id": info.id, "filename": p.name})
    store = client.agents.vector_stores.create_and_poll(
        file_ids=[f["id"] for f in uploaded],
        name=VECTOR_STORE_NAME,
        metadata={"project": "M.U.S.E", "managed_by": "scripts/azure/sync_muse_to_foundry.py"},
        polling_interval=2,
    )
    return uploaded, store.id


def update_agents(client: AIProjectClient, vector_store_id: str, agents: dict[str, str]) -> list[dict[str, str]]:
    updated = []
    ci = CodeInterpreterTool()
    fs = FileSearchTool(vector_store_ids=[vector_store_id])
    tools = ci.definitions + fs.definitions
    resources = ToolResources(
        code_interpreter=CodeInterpreterToolResource(file_ids=[]),
        file_search=FileSearchToolResource(vector_store_ids=[vector_store_id]),
    )
    for name, agent_id in agents.items():
        instructions = None
        try:
            current = client.agents.get_agent(agent_id)
            instructions = getattr(current, "instructions", None)
        except Exception:
            current = None
        new_instructions = (instructions or f"You are {name} for M.U.S.E.").rstrip() + "\n\nAzure RAG update: the full M.U.S.E repository representation is attached through file_search. Use it to answer questions about datasets, pipelines, Karpathy/LLM-wiki, RAG, skills, docs, scripts, configs, and project architecture."
        agent = client.agents.update_agent(
            agent_id,
            model=MODEL,
            name=name,
            instructions=new_instructions,
            tools=tools,
            tool_resources=resources,
            metadata={"project": "M.U.S.E", "rag_vector_store": vector_store_id, "managed_by": "scripts/azure/sync_muse_to_foundry.py"},
        )
        updated.append({"name": name, "id": getattr(agent, "id", agent_id)})
    return updated


def smoke_test(client: AIProjectClient, orchestrator_id: str) -> dict[str, Any]:
    prompt = "Using your attached M.U.S.E file_search/RAG, list the Azure representation layers and mention datasets, pipelines, Karpathy LLM wiki, and RAG. Keep it concise."
    run = client.agents.create_thread_and_run(agent_id=orchestrator_id, thread={"messages": [{"role": "user", "content": prompt}]})
    import time
    status = None
    for _ in range(60):
        r = client.agents.runs.get(thread_id=run.thread_id, run_id=run.id)
        status = str(getattr(r.status, "value", r.status))
        if status.lower() in {"completed", "failed", "cancelled", "expired"}:
            break
        time.sleep(2)
    messages = list(client.agents.messages.list(thread_id=run.thread_id))
    text = ""
    for m in messages:
        if str(getattr(m, "role", "")).lower().endswith("agent"):
            parts = getattr(m, "content", []) or []
            extracted = []
            for p in parts:
                if isinstance(p, dict):
                    extracted.append(((p.get("text") or {}).get("value") or ""))
                else:
                    extracted.append(getattr(getattr(p, "text", None), "value", "") or "")
            text = "\n".join(x for x in extracted if x)
            break
    return {"thread_id": run.thread_id, "run_id": run.id, "status": status, "response_preview": text[:1200]}


def main() -> int:
    STATE_DIR.mkdir(exist_ok=True)
    files = scan_repo()
    payload_files = write_payload(files)
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=AzureCliCredential())
    uploaded, vector_store_id = upload_and_index(client, payload_files)
    agents = load_agents()
    updated = update_agents(client, vector_store_id, agents) if agents else []
    smoke = smoke_test(client, agents.get("MUSE Long-Horizon Orchestrator")) if agents.get("MUSE Long-Horizon Orchestrator") else {}
    state = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_endpoint": PROJECT_ENDPOINT,
        "model": MODEL,
        "scanned_file_count": len(files),
        "category_counts": dict(Counter(f["category"] for f in files)),
        "payload_files": [str(p.relative_to(PROJECT_ROOT)) for p in payload_files],
        "uploaded_files": uploaded,
        "vector_store": {"id": vector_store_id, "name": VECTOR_STORE_NAME},
        "updated_agents": updated,
        "smoke_test": smoke,
    }
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    public_state = PROJECT_ROOT / "config" / "azure-muse-sync-state.yaml"
    public = {k: v for k, v in state.items() if k not in {"uploaded_files"}}
    public["uploaded_file_count"] = len(uploaded)
    public_state.write_text(yaml.safe_dump(public, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
