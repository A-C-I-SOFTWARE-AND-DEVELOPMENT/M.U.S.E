#!/usr/bin/env python3
"""Connect the local M.U.S.E checkout/Hermes config to a Microsoft Foundry project.

This script is intentionally safe:
- It never writes Azure secrets.
- It preserves the user's active Hermes default model unless --activate is used.
- It can run before az login; in that case it writes project metadata and reports
  the missing-auth blocker instead of failing destructively.

Inputs come from config/azure-foundry-muse.yaml plus environment overrides:
- AZURE_FOUNDRY_BASE_URL: OpenAI-compatible inference URL, e.g.
  https://<resource>.openai.azure.com/openai/v1
- AZURE_FOUNDRY_MODEL: deployment/model to use when activating Azure Foundry
- AZURE_FOUNDRY_API_KEY: optional static key; otherwise Entra ID is preferred
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML is required: {exc}")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "config" / "azure-foundry-muse.yaml"
HERMES_HOME = Path(os.environ.get("HERMES_HOME", r"C:\Users\Echer\AppData\Local\hermes"))
HERMES_CONFIG = HERMES_HOME / "config.yaml"
STATE_DIR = PROJECT_ROOT / ".azure"
STATE_FILE = STATE_DIR / "muse-foundry-connection.json"


def _az_executable() -> str:
    """Return an Azure CLI executable usable from Git Bash/MSYS Python on Windows."""
    for name in ("az", "az.cmd", "az.exe"):
        found = shutil.which(name)
        if found:
            return found
    # Common Windows install location when PATH differs between shells and Python.
    candidate = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft SDKs" / "Azure" / "CLI2" / "wbin" / "az.cmd"
    if candidate.exists():
        return str(candidate)
    return "az"


AZ = _az_executable()


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return proc.returncode, proc.stdout.strip()
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "timeout").strip() if isinstance(exc.stdout, str) else "timeout"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")


def az_account() -> tuple[dict[str, Any] | None, str]:
    code, out = run([AZ, "account", "show", "-o", "json"], timeout=20)
    if code != 0:
        return None, out
    try:
        return json.loads(out), out
    except Exception:
        return None, out


def az_resource_show(resource_group: str, resource_name: str) -> tuple[dict[str, Any] | None, str]:
    # The resource type varies across Foundry rename waves. Try generic name lookup first.
    code, out = run([
        AZ, "resource", "list",
        "--resource-group", resource_group,
        "--name", resource_name,
        "-o", "json",
    ], timeout=40)
    if code != 0:
        return None, out
    try:
        items = json.loads(out)
        if items:
            return items[0], out
    except Exception:
        pass
    return None, out


def endpoint_candidates(resource: dict[str, Any] | None, resource_name: str) -> list[str]:
    c: list[str] = []
    if resource:
        props = resource.get("properties") or {}
        for key in ("endpoint", "openAIEndpoint", "endpointUrl", "inferenceEndpoint", "target"):
            val = props.get(key)
            if isinstance(val, str) and val.startswith("https://"):
                c.append(val.rstrip("/"))
        # Some cognitive/AI resources expose customSubDomainName.
        sub = props.get("customSubDomainName") or resource.get("name") or resource_name
        if isinstance(sub, str) and sub:
            c.extend([
                f"https://{sub}.openai.azure.com/openai/v1",
                f"https://{sub}.services.ai.azure.com/models",
                f"https://{sub}.cognitiveservices.azure.com/openai/v1",
            ])
    c.extend([
        f"https://{resource_name}.openai.azure.com/openai/v1",
        f"https://{resource_name}.services.ai.azure.com/models",
        f"https://{resource_name}.cognitiveservices.azure.com/openai/v1",
    ])
    seen = set()
    out = []
    for url in c:
        if url not in seen:
            seen.add(url); out.append(url)
    return out


def configure_hermes(manifest: dict[str, Any], base_url: str | None, default_model: str, activate: bool) -> Path:
    if not HERMES_CONFIG.exists():
        raise SystemExit(f"Hermes config not found: {HERMES_CONFIG}")
    cfg = load_yaml(HERMES_CONFIG)
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = HERMES_CONFIG.with_name(f"config.yaml.pre-azure-foundry-muse-{ts}.bak")
    shutil.copy2(HERMES_CONFIG, backup)

    az = manifest["azure_foundry"]
    cfg["azure_foundry_projects"] = cfg.get("azure_foundry_projects") or {}
    cfg["azure_foundry_projects"]["muse"] = {
        "project_name": az["project_name"],
        "resource_group": az["resource_group"],
        "resource_name": az["resource_name"],
        "portal_resource_id": az["portal_resource_id"],
        "portal_url": az["portal_url"],
        "auth_mode": "entra_id",
        "scope": az["inference"].get("scope", "https://ai.azure.com/.default"),
        "base_url": base_url or "",
        "default_model": default_model,
    }

    providers = cfg.setdefault("providers", {})
    api_mode = "codex_responses" if default_model.lower().startswith(("gpt-5", "o1", "o3", "o4")) else "chat_completions"
    providers["azure-foundry-muse"] = {
        "name": "M.U.S.E Microsoft Foundry",
        "base_url": base_url or "",
        "key_env": "AZURE_FOUNDRY_API_KEY",
        "api_mode": api_mode,
        "auth_mode": "entra_id",
        "default_model": default_model,
        "models": {default_model: {}},
        "project_name": az["project_name"],
        "resource_group": az["resource_group"],
        "resource_name": az["resource_name"],
    }

    aliases = cfg.setdefault("model_aliases", {})
    for alias in az["hermes"].get("add_aliases", []):
        aliases[alias] = {
            "model": default_model,
            "provider": "azure-foundry",
            "base_url": base_url or "",
            "auth_mode": "entra_id",
        }

    if activate:
        cfg["model"] = {
            "default": default_model,
            "provider": "azure-foundry",
            "base_url": base_url or "",
            "api_mode": api_mode,
            "auth_mode": "entra_id",
            "entra": {"scope": az["inference"].get("scope", "https://ai.azure.com/.default")},
        }

    save_yaml(HERMES_CONFIG, cfg)
    return backup


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--activate", action="store_true", help="Make Azure Foundry the active Hermes model provider")
    manifest_default_base_url = ""
    manifest_default_model = "gpt-4o"
    if MANIFEST.exists():
        try:
            _manifest_boot = load_yaml(MANIFEST)
            _inf = ((_manifest_boot.get("azure_foundry") or {}).get("inference") or {})
            manifest_default_base_url = str(_inf.get("base_url") or "").strip()
            manifest_default_model = str(_inf.get("default_model_fallback") or "gpt-4o").strip() or "gpt-4o"
        except Exception:
            pass
    ap.add_argument("--base-url", default=os.environ.get("AZURE_FOUNDRY_BASE_URL", "").strip() or manifest_default_base_url)
    ap.add_argument("--model", default=os.environ.get("AZURE_FOUNDRY_MODEL", "").strip() or manifest_default_model)
    args = ap.parse_args()

    manifest = load_yaml(MANIFEST)
    az = manifest["azure_foundry"]
    account, account_raw = az_account()
    resource = None
    az_blocker = None
    if account:
        resource, resource_raw = az_resource_show(az["resource_group"], az["resource_name"])
    else:
        az_blocker = account_raw

    candidates = endpoint_candidates(resource, az["resource_name"])
    base_url = args.base_url or (candidates[0] if resource else "")
    backup = configure_hermes(manifest, base_url, args.model, args.activate)

    STATE_DIR.mkdir(exist_ok=True)
    state = {
        "connected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "portal_url": az["portal_url"],
        "project_name": az["project_name"],
        "resource_group": az["resource_group"],
        "resource_name": az["resource_name"],
        "az_logged_in": bool(account),
        "az_account": account,
        "resource_discovered": bool(resource),
        "resource": resource,
        "base_url_configured": base_url,
        "endpoint_candidates": candidates,
        "default_model": args.model,
        "activated": args.activate,
        "hermes_config": str(HERMES_CONFIG),
        "hermes_config_backup": str(backup),
        "blocker": az_blocker,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "az_logged_in": bool(account),
        "resource_discovered": bool(resource),
        "base_url_configured": base_url,
        "activated": args.activate,
        "state_file": str(STATE_FILE),
        "hermes_config_backup": str(backup),
        "blocker": az_blocker,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
