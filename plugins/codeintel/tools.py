"""Three agent-facing code-intelligence tools.

  dependency_audit — OSV.dev known-vulnerability scan for a package@version
  dependency_info  — deps.dev licenses/versions/advisories for a package
  run_code         — Piston sandboxed execution (DOUBLE-gated, opt-in)

Uniform envelope ``{"success": bool, ...}``. ``dependency_audit`` and
``dependency_info`` are read-only and need only ``codeintel.enabled``.
``run_code`` additionally requires ``codeintel.allow_code_execution`` and
sends the supplied code to a third-party public sandbox.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.codeintel import config as codeintel_config
from plugins.codeintel.client import CodeintelClient
from tools.http_client import HttpClientError

# Cap on code we'll ship to the sandbox — protects against accidentally
# uploading a huge file and bounds third-party egress.
MAX_CODE_CHARS = 50_000


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


# ── check_fns ────────────────────────────────────────────────────────────────


def check_codeintel_enabled() -> bool:
    """Read-only tools: visible whenever the plugin is enabled."""
    return codeintel_config.load_config().enabled


def check_run_code_ready() -> bool:
    """run_code: visible only when enabled AND code execution is allowed."""
    cfg = codeintel_config.load_config()
    return cfg.enabled and cfg.allow_code_execution


def _enabled_or_error() -> str | None:
    if not codeintel_config.load_config().enabled:
        return _err("plugin_disabled", "codeintel.enabled is false")
    return None


# ── schemas ──────────────────────────────────────────────────────────────────

DEPENDENCY_AUDIT_SCHEMA: Dict[str, Any] = {
    "name": "dependency_audit",
    "description": (
        "Check a package version for known vulnerabilities via OSV.dev (free, "
        "no key). Provide the ecosystem (pypi/npm/cargo/go/maven/rubygems/"
        "nuget), package name, and optionally a version. Returns matching "
        "advisories with IDs, summary, aliases (CVEs), and severity. An empty "
        "list means no known vulnerabilities for that query. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ecosystem": {
                "type": "string",
                "description": "e.g. 'pypi', 'npm', 'cargo'.",
            },
            "name": {"type": "string", "description": "Package name."},
            "version": {"type": "string", "description": "Optional exact version."},
        },
        "required": ["ecosystem", "name"],
        "additionalProperties": False,
    },
}

DEPENDENCY_INFO_SCHEMA: Dict[str, Any] = {
    "name": "dependency_info",
    "description": (
        "Look up a package on deps.dev (free, no key). Without a version: "
        "returns known versions. With a version: returns its licenses, "
        "published date, and advisory keys. System is pypi/npm/cargo/go/maven/"
        "nuget. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "system": {"type": "string", "description": "e.g. 'pypi', 'npm', 'cargo'."},
            "name": {"type": "string", "description": "Package name."},
            "version": {"type": "string", "description": "Optional version."},
        },
        "required": ["system", "name"],
        "additionalProperties": False,
    },
}

RUN_CODE_SCHEMA: Dict[str, Any] = {
    "name": "run_code",
    "description": (
        "Execute a short code snippet in the public Piston sandbox and return "
        "stdout/stderr/exit code. Useful for verifying a small example during "
        "code review. NOTE: the code is sent to a third-party sandbox "
        "(emkc.org); do not include secrets. Disabled unless the operator sets "
        "codeintel.allow_code_execution: true. No local execution."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "e.g. 'python', 'javascript', 'rust'.",
            },
            "code": {"type": "string", "description": "Source code to run."},
            "stdin": {"type": "string", "description": "Optional standard input."},
            "version": {
                "type": "string",
                "description": "Optional runtime version; defaults to latest.",
            },
        },
        "required": ["language", "code"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def _slim_vuln(v: Dict[str, Any]) -> Dict[str, Any]:
    severity = None
    for s in v.get("severity") or []:
        if isinstance(s, dict) and s.get("score"):
            severity = s.get("score")
            break
    return {
        "id": v.get("id"),
        "summary": v.get("summary"),
        "aliases": v.get("aliases"),
        "severity": severity,
        "modified": v.get("modified"),
    }


def handle_dependency_audit(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = args.get("name")
    ecosystem = args.get("ecosystem")
    if not isinstance(name, str) or not name.strip():
        return _err("bad_args", "name is required")
    if not isinstance(ecosystem, str) or not ecosystem.strip():
        return _err("bad_args", "ecosystem is required")
    version = args.get("version") if isinstance(args.get("version"), str) else None
    eco = CodeintelClient.resolve_osv_ecosystem(ecosystem)
    try:
        payload = CodeintelClient().osv_query(name.strip(), eco, version)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    vulns = [
        _slim_vuln(v) for v in (payload or {}).get("vulns", []) if isinstance(v, dict)
    ]
    return _ok(
        ecosystem=eco,
        name=name.strip(),
        version=version,
        vulnerable=bool(vulns),
        vulnerabilities=vulns,
    )


def handle_dependency_info(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    name = args.get("name")
    system = args.get("system")
    if not isinstance(name, str) or not name.strip():
        return _err("bad_args", "name is required")
    if not isinstance(system, str) or not system.strip():
        return _err("bad_args", "system is required")
    version = args.get("version") if isinstance(args.get("version"), str) else None
    sys_name = CodeintelClient.resolve_depsdev_system(system)
    try:
        payload = CodeintelClient().depsdev(sys_name, name.strip(), version)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    payload = payload or {}
    if version:
        return _ok(
            system=sys_name,
            name=name.strip(),
            version=version,
            licenses=payload.get("licenses"),
            advisory_keys=[
                a.get("id")
                for a in payload.get("advisoryKeys", [])
                if isinstance(a, dict)
            ],
            published_at=payload.get("publishedAt"),
        )
    versions = [
        (vk.get("versionKey") or {}).get("version")
        for vk in payload.get("versions", [])
        if isinstance(vk, dict)
    ]
    return _ok(system=sys_name, name=name.strip(), versions=versions[:100])


def handle_run_code(args: Dict[str, Any], **_kw) -> str:
    cfg = codeintel_config.load_config()
    if not cfg.enabled:
        return _err("plugin_disabled", "codeintel.enabled is false")
    if not cfg.allow_code_execution:
        return _err(
            "code_execution_disabled",
            "codeintel.allow_code_execution is false; refusing to send code to "
            "the third-party Piston sandbox. Set it to true in ~/.hermes/config.yaml.",
        )
    language = args.get("language")
    code = args.get("code")
    if not isinstance(language, str) or not language.strip():
        return _err("bad_args", "language is required")
    if not isinstance(code, str) or not code:
        return _err("bad_args", "code is required")
    if len(code) > MAX_CODE_CHARS:
        return _err("bad_args", f"code exceeds {MAX_CODE_CHARS} characters")
    stdin_arg = args.get("stdin")
    stdin = stdin_arg if isinstance(stdin_arg, str) else ""
    version_arg = args.get("version")
    version = version_arg if isinstance(version_arg, str) and version_arg else "*"
    try:
        payload = CodeintelClient().piston_execute(
            language.strip(), code, version=version, stdin=stdin
        )
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    run = (payload or {}).get("run") or {}
    return _ok(
        language=(payload or {}).get("language"),
        version=(payload or {}).get("version"),
        stdout=run.get("stdout"),
        stderr=run.get("stderr"),
        exit_code=run.get("code"),
        output=run.get("output"),
    )


# (name, schema, handler, emoji, check_fn, requires_env)
TOOL_REGISTRATIONS = (
    (
        "dependency_audit",
        DEPENDENCY_AUDIT_SCHEMA,
        handle_dependency_audit,
        "🛡️",
        check_codeintel_enabled,
        [],
    ),
    (
        "dependency_info",
        DEPENDENCY_INFO_SCHEMA,
        handle_dependency_info,
        "🔬",
        check_codeintel_enabled,
        [],
    ),
    ("run_code", RUN_CODE_SCHEMA, handle_run_code, "▶️", check_run_code_ready, []),
)
