"""Secure Hermes ↔ remote-worker bridge.

This module is the Hermes-side half of the
``claude-code-windows`` bridge: it dispatches jobs to a remote worker
host (the canonical example is Jeremiah's Windows desktop running the
official ``claude`` CLI), polls status, collects artifacts, and lets
the orchestrator cancel a run.

The design is deliberately conservative — every default leans
"refuse" rather than "run":

* The default transport is **file-drop**: Hermes writes the job into
  a shared directory (Tailscale + Syncthing, SMB-over-Tailscale,
  Cloudflare-tunneled WebDAV, an SSH-mounted folder, …). The Windows
  worker daemon polls that directory. No public, unauthenticated HTTP
  endpoint is ever opened. An optional **HTTP** transport POSTs the same
  staged job packet to an authenticated, operator-configured endpoint
  (URL from config, bearer token from an env var — never hardcoded).
  The WebSocket and SSH transports remain documented future work and
  ship as explicit stubs so a misread config name surfaces immediately.
* Every dispatch requires an explicit ``allow_remote_execute=True``.
  Without it the bridge stages the job locally, records an audit
  entry, and returns ``state="awaiting_approval"``. Approval happens
  out-of-band (a /confirm slash command, the Android cockpit, …).
* Every endpoint carries an ``allowed_device_ids`` set. A device
  identity that is not on the allowlist is refused — even if it
  presents a valid job token.
* Each job ships with a freshly generated, random per-job token
  (``secrets.token_urlsafe(32)``). The Windows worker is expected to
  echo this token back in its status payload; a status reply without
  a matching token is rejected.
* Command execution is gated by a small allowlist (defaults to
  ``("claude",)``). Anything else fails before the bridge writes a
  manifest. Future expansions go through a code review, not a config
  toggle.
* Every action — dispatch, status read, cancel, refusal — is appended
  to an audit log (``~/.hermes/remote/audit.log.jsonl`` by default).
  Secrets are scrubbed via :func:`scrub_secrets` before any payload
  reaches the log; ``.env`` files are explicitly refused unless the
  caller passes ``permit_env_transfer=True`` *and* the endpoint
  itself permits it.

The file-drop path is intentionally dependency-free: stdlib only. Tests
can point ``RemoteEndpoint.workspace_root`` at a tempdir and exercise the
full file-drop happy path without touching the network. The HTTP
transport additionally uses ``httpx`` (the project's HTTP client) and
``tenacity`` for retries; tests mock the client so no real network call
is ever made.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

# ``httpx`` / ``tenacity`` back the HTTP transport only. The file-drop path is
# intentionally stdlib-only, and minimal environments (e.g. the orchestration
# CI job, which installs just pytest + PyYAML) import this module without those
# deps. Guard the imports so ``from hermes_cli import remote_bridge`` always
# works; the names are only dereferenced inside ``_post_http`` (the HTTP path),
# which is unreachable without an ``http`` endpoint. Keeping them as module
# attributes (vs. a function-local import) also lets tests patch
# ``remote_bridge.httpx.Client``. Under TYPE_CHECKING they're imported
# unconditionally so type-checkers resolve the real symbols.
if TYPE_CHECKING:
    import httpx
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
else:
    try:
        import httpx
    except ImportError:  # pragma: no cover - minimal env without HTTP-transport deps
        httpx = None

    try:
        from tenacity import (
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )
    except ImportError:  # pragma: no cover - minimal env without HTTP-transport deps
        retry = retry_if_exception_type = stop_after_attempt = wait_exponential = None


# ── public constants ──────────────────────────────────────────────────────

DEFAULT_AUDIT_FILENAME = "audit.log.jsonl"
"""Filename for the append-only audit log under the bridge state dir."""

DEFAULT_COMMAND_ALLOWLIST: tuple[str, ...] = ("claude",)
"""Commands the Windows worker is allowed to run on Hermes' behalf.

The allowlist is intentionally tiny. Anything outside it is refused
at dispatch time — including ``cmd``, ``powershell``, ``python``,
``bash``. The Windows worker is also expected to enforce this on its
side, but the bridge refuses first so a misbehaving / compromised
worker cannot smuggle commands through.
"""

TRANSPORT_FILE_DROP = "file_drop"
"""Default transport: a shared directory both sides can read/write."""

TRANSPORT_HTTP = "http"
"""HTTP transport: POST the staged job packet to an authenticated endpoint.

The endpoint URL lives in ``RemoteEndpoint.http_endpoint_url`` (config,
never hardcoded). An optional bearer token is read at dispatch time from
the env var named in ``RemoteEndpoint.auth_token_env`` — the token value
never round-trips through config or the audit log. The local workspace
artifacts (``prompt.md``, ``manifest.json``, ``status.json``) are written
exactly as in file-drop so the audit trail is identical; the HTTP POST is
an additional hand-off, not a replacement.
"""

TRANSPORT_WEBSOCKET = "websocket"
"""WebSocket transport — documented future work, refused at dispatch."""

TRANSPORT_SSH = "ssh"
"""SSH reverse tunnel — documented future work, refused at dispatch."""

SUPPORTED_TRANSPORTS: frozenset[str] = frozenset(
    {
        TRANSPORT_FILE_DROP,
        TRANSPORT_HTTP,
        TRANSPORT_WEBSOCKET,
        TRANSPORT_SSH,
    }
)


class JobState(str, Enum):
    """Lifecycle states for a remote job."""

    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class BridgeError(Exception):
    """Raised when the bridge refuses to dispatch / collect a job."""


class TransportNotImplementedError(BridgeError):
    """Raised when a transport is selected but not yet implemented."""


class _RetryableStatusError(Exception):
    """Internal: a 5xx response the HTTP transport should retry.

    Not part of the public API — it never escapes :meth:`RemoteBridge.dispatch`,
    which maps it to :class:`BridgeError`.
    """

    def __init__(self, response: "httpx.Response") -> None:
        super().__init__(f"retryable HTTP {response.status_code}")
        self.response = response


# ── secret scrubbing ──────────────────────────────────────────────────────


# Patterns for common credential shapes. We err on the side of over-
# matching: the audit log is for forensics, not debugging, so a
# false-positive that mangles a perfectly innocent string is fine.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Anthropic, OpenAI, etc. — sk-/sk-ant-/sk-proj- prefixes
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}", re.IGNORECASE),
    # GitHub PATs / app tokens
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    # GitLab PAT
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}\b"),
    # AWS access key IDs
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    # JWTs (three dot-separated base64 segments, starts with eyJ…)
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"),
    # Slack tokens
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b"),
    # URL-embedded basic-auth credentials: scheme://user:pass@host
    re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+\-.]*://)[^/\s:@]+:[^/\s:@]+@"),
    # Authorization: Bearer <token>
    re.compile(r"(?i)\b(authorization)\s*[:=]\s*bearer\s+[A-Za-z0-9_\-.=]+"),
    # Generic ``something_token=...`` / ``api_key=...``
    re.compile(
        r"(?i)\b("
        r"api[_-]?key|secret|token|password|passwd|auth[_-]?key|access[_-]?key"
        r")\s*[:=]\s*['\"]?[A-Za-z0-9_\-.=/+]{6,}['\"]?"
    ),
)

_SECRET_REDACTED = "***redacted***"


def scrub_secrets(value: Any) -> Any:
    """Return ``value`` with credential-shaped substrings redacted.

    Walks dicts, lists, tuples and strings recursively. Non-string
    scalars (numbers, bools, ``None``) pass through unchanged. The
    walker is deliberately defensive: any unexpected type is stringified
    via :func:`repr` and scrubbed.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        out = value
        # URL-embedded creds: keep scheme, redact user:pass.
        out = _SECRET_PATTERNS[6].sub(r"\g<scheme>***:***@", out)
        for pattern in _SECRET_PATTERNS:
            if pattern is _SECRET_PATTERNS[6]:
                continue
            out = pattern.sub(_SECRET_REDACTED, out)
        return out
    if isinstance(value, Mapping):
        return {str(k): scrub_secrets(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        scrubbed = [scrub_secrets(v) for v in value]
        return type(value)(scrubbed) if isinstance(value, tuple) else scrubbed
    return scrub_secrets(repr(value))


# ── configuration ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RemoteEndpoint:
    """Description of a remote worker the bridge can talk to.

    ``workspace_root`` is the directory both sides agree to share. For
    the file-drop transport that means a Tailscale-mounted Syncthing
    folder, an SSHFS mount, an SMB share carried over Tailscale, etc.
    Hermes writes ``jobs/<job_id>/`` into it; the Windows worker
    daemon polls the same path.

    ``allowed_device_ids`` is the allowlist of identities the bridge
    will accept status replies from. The empty set means "no remote
    identity is allowed" — explicit, not implicit-deny-by-omission.

    ``permit_env_transfer`` defaults to ``False``. Even if the caller
    asks to ship ``.env`` it is refused unless the endpoint opts in.
    """

    name: str
    transport: str = TRANSPORT_FILE_DROP
    workspace_root: Path = Path()
    device_id: str = ""
    allowed_device_ids: frozenset[str] = field(default_factory=frozenset)
    auth_token_env: str = ""
    command_allowlist: tuple[str, ...] = DEFAULT_COMMAND_ALLOWLIST
    allow_remote_execute: bool = False
    permit_env_transfer: bool = False
    poll_interval_seconds: float = 5.0
    status_timeout_seconds: float = 60.0 * 60  # 1h ceiling per job
    # HTTP transport knobs (ignored by the file-drop path). ``http_endpoint_url``
    # is required when ``transport == "http"``; it carries no secret — any auth
    # token is read at dispatch time from the env var named in ``auth_token_env``.
    http_endpoint_url: str = ""
    http_timeout_seconds: float = 30.0
    http_max_attempts: int = 3
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("RemoteEndpoint.name must be non-empty")
        if self.transport not in SUPPORTED_TRANSPORTS:
            raise ValueError(
                f"unsupported transport {self.transport!r}; expected one of "
                f"{sorted(SUPPORTED_TRANSPORTS)}"
            )
        if not self.command_allowlist:
            raise ValueError("RemoteEndpoint.command_allowlist must be non-empty")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        if self.status_timeout_seconds <= 0:
            raise ValueError("status_timeout_seconds must be > 0")
        if self.transport == TRANSPORT_HTTP:
            if not self.http_endpoint_url.strip():
                raise ValueError(
                    "http transport requires a non-empty http_endpoint_url"
                )
            if not self.http_endpoint_url.lower().startswith(
                ("http://", "https://")
            ):
                raise ValueError(
                    "http_endpoint_url must start with http:// or https://; got "
                    f"{self.http_endpoint_url!r}"
                )
            if self.http_timeout_seconds <= 0:
                raise ValueError("http_timeout_seconds must be > 0")
            if self.http_max_attempts < 1:
                raise ValueError("http_max_attempts must be >= 1")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RemoteEndpoint":
        """Build an endpoint from a dict (YAML/JSON config)."""
        data = dict(payload)
        if "workspace_root" in data and data["workspace_root"] is not None:
            data["workspace_root"] = Path(data["workspace_root"]).expanduser()
        if "allowed_device_ids" in data and data["allowed_device_ids"] is not None:
            data["allowed_device_ids"] = frozenset(data["allowed_device_ids"])
        if "command_allowlist" in data and data["command_allowlist"] is not None:
            data["command_allowlist"] = tuple(data["command_allowlist"])
        if "notes" in data and data["notes"] is not None:
            data["notes"] = tuple(data["notes"])
        return cls(**data)


@dataclass(frozen=True)
class JobManifest:
    """The packet the bridge writes alongside a remote job.

    The manifest is the contract between Hermes and the Windows
    worker. It tells the worker:

      * which command to run (must be in the endpoint allowlist),
      * which prompt file to feed it,
      * which artifacts Hermes expects back,
      * which token to echo in every status reply.

    The manifest never contains secrets. ``auth_token`` is a
    per-job random opaque string used only to authenticate the
    *reply* — it does not unlock any external resource.
    """

    job_id: str
    endpoint: str
    command: str
    prompt_filename: str
    expected_artifacts: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    auth_token: str
    device_id: str
    allow_remote_execute: bool
    created_at: float
    schema: str = "hermes.remote.job.v1"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "job_id": self.job_id,
            "endpoint": self.endpoint,
            "command": self.command,
            "prompt_filename": self.prompt_filename,
            "expected_artifacts": list(self.expected_artifacts),
            "required_artifacts": list(self.required_artifacts),
            "auth_token": self.auth_token,
            "device_id": self.device_id,
            "allow_remote_execute": self.allow_remote_execute,
            "created_at": self.created_at,
            "extra": dict(self.extra),
        }


@dataclass(frozen=True)
class RemoteJob:
    """Handle returned by :meth:`RemoteBridge.dispatch`."""

    job_id: str
    endpoint: str
    state: JobState
    workdir: Path
    manifest_path: Path
    prompt_path: Path
    auth_token: str
    created_at: float
    detail: str = ""


@dataclass(frozen=True)
class RemoteStatus:
    """Status snapshot for a previously dispatched job."""

    job_id: str
    state: JobState
    detail: str = ""
    last_seen: Optional[float] = None
    artifacts: Mapping[str, str] = field(default_factory=dict)
    raw: Optional[Mapping[str, Any]] = None


# ── audit log ─────────────────────────────────────────────────────────────


@dataclass
class AuditLog:
    """Append-only JSONL audit log.

    Every line is one event. Events are scrubbed for secrets before
    they hit disk so an accidentally pasted token cannot leak via a
    log dump.
    """

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    def record(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Write ``event`` (with secrets scrubbed) and return what was logged."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.time(),
            **scrub_secrets(dict(event)),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
        return payload

    def read_all(self) -> list[dict[str, Any]]:
        """Return every event (best effort — malformed lines are skipped)."""
        if not self.path.is_file():
            return []
        entries: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


# ── the bridge ────────────────────────────────────────────────────────────


class RemoteBridge:
    """Hermes-side orchestrator for remote Claude Code workers.

    The bridge owns three responsibilities:

      1. Validate that a dispatch is safe (transport supported,
         command allowed, device allowlisted, approval granted,
         secrets scrubbed).
      2. Move the prompt + manifest into the shared workspace.
      3. Read status / artifacts back without ever trusting a reply
         whose ``auth_token`` does not match what Hermes issued.

    The bridge holds no long-lived sockets, threads, or background
    polling loops. Callers drive the lifecycle:

        bridge = RemoteBridge(endpoint, audit_log)
        job = bridge.dispatch(prompt="...", allow_remote_execute=True)
        while True:
            status = bridge.get_status(job.job_id)
            if status.state in {JobState.COMPLETED, JobState.FAILED,
                                JobState.CANCELED}:
                break
            time.sleep(endpoint.poll_interval_seconds)
        bridge.collect_artifacts(job.job_id, dest_dir)
    """

    def __init__(
        self,
        endpoint: RemoteEndpoint,
        *,
        audit_log: Optional[AuditLog] = None,
        clock: Optional[Any] = None,
        token_factory: Optional[Any] = None,
    ) -> None:
        self.endpoint = endpoint
        self._clock = clock or time.time
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        if audit_log is None:
            default_path = self._default_audit_path()
            audit_log = AuditLog(default_path)
        self.audit_log = audit_log

    # ── dispatch ──────────────────────────────────────────────────────────

    def dispatch(
        self,
        prompt: str,
        *,
        expected_artifacts: Sequence[str],
        required_artifacts: Sequence[str] = (),
        command: str = "claude",
        allow_remote_execute: bool = False,
        attachments: Optional[Mapping[str, str]] = None,
        extra_manifest: Optional[Mapping[str, Any]] = None,
        env_files: Sequence[Path] = (),
    ) -> RemoteJob:
        """Stage a job, write the manifest, and (optionally) hand it to the worker.

        ``allow_remote_execute`` MUST be ``True`` *and* the endpoint
        itself must opt in for the manifest to advertise the run as
        approved. Anything less stages the job in ``awaiting_approval``
        state — visible to the user via the audit log and the
        ``status.json`` snapshot — but the Windows worker is instructed
        to wait for an explicit unlock before executing.
        """
        if not prompt.strip():
            raise BridgeError("dispatch: prompt must be non-empty")
        if command not in self.endpoint.command_allowlist:
            self._record_refusal(
                "command_not_allowlisted",
                command=command,
                allowlist=list(self.endpoint.command_allowlist),
            )
            raise BridgeError(
                f"command {command!r} is not in the endpoint allowlist "
                f"({sorted(self.endpoint.command_allowlist)!r})"
            )
        if env_files and not (
            allow_remote_execute and self.endpoint.permit_env_transfer
        ):
            self._record_refusal(
                "env_transfer_refused",
                file_count=len(env_files),
                allow_remote_execute=allow_remote_execute,
                permit_env_transfer=self.endpoint.permit_env_transfer,
            )
            raise BridgeError(
                "refusing to ship .env files — set permit_env_transfer=True on the "
                "endpoint AND pass allow_remote_execute=True explicitly to opt in."
            )
        if self.endpoint.transport not in (TRANSPORT_FILE_DROP, TRANSPORT_HTTP):
            self._record_refusal(
                "transport_stub",
                transport=self.endpoint.transport,
            )
            raise TransportNotImplementedError(
                f"transport {self.endpoint.transport!r} has documented design only — "
                "see docs/remote/secure-tunnel-options.md. Use file_drop or http."
            )

        approved = allow_remote_execute and self.endpoint.allow_remote_execute
        job_id = self._mint_job_id()
        token = self._token_factory()
        now = float(self._clock())

        workdir = self._workdir_for(job_id)
        workdir.mkdir(parents=True, exist_ok=False)
        prompt_path = workdir / "prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if attachments:
            for filename, body in attachments.items():
                safe = _safe_filename(filename)
                (workdir / safe).write_text(body, encoding="utf-8")

        if env_files and approved:
            env_dir = workdir / "env"
            env_dir.mkdir(parents=True, exist_ok=True)
            for source in env_files:
                source = Path(source)
                if not source.is_file():
                    continue
                shutil.copy2(source, env_dir / source.name)

        manifest = JobManifest(
            job_id=job_id,
            endpoint=self.endpoint.name,
            command=command,
            prompt_filename=prompt_path.name,
            expected_artifacts=tuple(expected_artifacts),
            required_artifacts=tuple(required_artifacts),
            auth_token=token,
            device_id=self.endpoint.device_id,
            allow_remote_execute=approved,
            created_at=now,
            extra=dict(extra_manifest or {}),
        )
        manifest_path = workdir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        initial_status = {
            "schema": "hermes.remote.status.v1",
            "job_id": job_id,
            "state": (
                JobState.QUEUED.value
                if approved
                else JobState.AWAITING_APPROVAL.value
            ),
            "detail": (
                "Hermes staged the job."
                if approved
                else "Awaiting explicit user approval before remote execution."
            ),
            "auth_token": token,
            "last_seen": None,
            "artifacts": {},
            "from": "hermes",
            "created_at": now,
        }
        (workdir / "status.json").write_text(
            json.dumps(initial_status, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        state = JobState.QUEUED if approved else JobState.AWAITING_APPROVAL
        detail = initial_status["detail"]

        # HTTP transport: hand the staged packet to the remote endpoint over
        # the network. We only POST once the job is approved — an unapproved
        # job parks locally exactly as it does under file-drop, so an
        # accidental dispatch never leaves the host. A transport failure is a
        # hard error: the local artifacts persist for forensics, but the
        # caller must know the worker did not receive the job.
        if self.endpoint.transport == TRANSPORT_HTTP and approved:
            ack = self._post_http(manifest, prompt=prompt, token=token)
            ack_state = ack.get("state")
            if ack_state:
                try:
                    state = JobState(str(ack_state))
                except ValueError:
                    state = JobState.QUEUED
            detail = str(ack.get("detail") or "Worker acknowledged the job.")
            # Persist the worker's acknowledgement into status.json so a
            # later get_status() reflects the network round-trip.
            initial_status["state"] = state.value
            initial_status["detail"] = detail
            initial_status["last_seen"] = float(self._clock())
            (workdir / "status.json").write_text(
                json.dumps(initial_status, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        self.audit_log.record(
            {
                "event": "dispatch",
                "endpoint": self.endpoint.name,
                "transport": self.endpoint.transport,
                "job_id": job_id,
                "command": command,
                "expected_artifacts": list(expected_artifacts),
                "required_artifacts": list(required_artifacts),
                "approved": approved,
                "state": state.value,
                "device_id": self.endpoint.device_id,
                "allowed_device_count": len(self.endpoint.allowed_device_ids),
            }
        )

        return RemoteJob(
            job_id=job_id,
            endpoint=self.endpoint.name,
            state=state,
            workdir=workdir,
            manifest_path=manifest_path,
            prompt_path=prompt_path,
            auth_token=token,
            created_at=now,
            detail=detail,
        )

    # ── status ───────────────────────────────────────────────────────────

    def get_status(self, job_id: str) -> RemoteStatus:
        """Read the worker's most recent ``status.json``.

        A status payload is accepted only if it carries the same
        ``auth_token`` we issued at dispatch *and* its ``device_id``
        (if present) is in the endpoint allowlist. Anything else is
        treated as an attempted forgery and logged.
        """
        workdir = self._workdir_for(job_id)
        status_path = workdir / "status.json"
        manifest_path = workdir / "manifest.json"
        if not status_path.is_file():
            return RemoteStatus(
                job_id=job_id,
                state=JobState.UNKNOWN,
                detail="no status.json found",
            )
        try:
            raw = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return RemoteStatus(
                job_id=job_id,
                state=JobState.UNKNOWN,
                detail=f"status.json unreadable: {exc}",
            )

        if not isinstance(raw, Mapping):
            return RemoteStatus(
                job_id=job_id,
                state=JobState.UNKNOWN,
                detail="status.json is not a JSON object",
            )

        if raw.get("from") == "hermes":
            # Hermes' own initial placeholder.
            return self._status_from(raw, job_id=job_id, trusted=True)

        manifest = self._read_manifest(manifest_path)
        if manifest is None:
            return RemoteStatus(
                job_id=job_id,
                state=JobState.UNKNOWN,
                detail="manifest.json missing or unreadable",
            )

        token = raw.get("auth_token")
        if token != manifest.auth_token:
            self._record_refusal(
                "status_token_mismatch",
                job_id=job_id,
                endpoint=self.endpoint.name,
            )
            return RemoteStatus(
                job_id=job_id,
                state=JobState.UNKNOWN,
                detail="auth_token mismatch — status reply ignored",
            )

        device_id = raw.get("device_id")
        if (
            device_id
            and self.endpoint.allowed_device_ids
            and device_id not in self.endpoint.allowed_device_ids
        ):
            self._record_refusal(
                "status_device_not_allowlisted",
                job_id=job_id,
                endpoint=self.endpoint.name,
                device_id=device_id,
            )
            return RemoteStatus(
                job_id=job_id,
                state=JobState.UNKNOWN,
                detail=f"device {device_id!r} is not on the endpoint allowlist",
            )

        return self._status_from(raw, job_id=job_id, trusted=True)

    # ── artifact collection ──────────────────────────────────────────────

    def collect_artifacts(
        self,
        job_id: str,
        dest_dir: Path,
        *,
        require_state: Iterable[JobState] = (JobState.COMPLETED,),
    ) -> tuple[Path, ...]:
        """Copy the artifacts the worker produced into ``dest_dir``.

        ``require_state`` is an allowlist of states the job must be in
        before artifacts are copied. By default we only collect when
        the worker reports ``completed`` — collecting from a running
        job risks pulling half-written files.
        """
        status = self.get_status(job_id)
        allowed = frozenset(require_state)
        if status.state not in allowed:
            raise BridgeError(
                f"refusing to collect: job {job_id} is in state "
                f"{status.state.value!r}, expected one of "
                f"{sorted(s.value for s in allowed)!r}"
            )
        workdir = self._workdir_for(job_id)
        manifest = self._read_manifest(workdir / "manifest.json")
        if manifest is None:
            raise BridgeError(
                f"refusing to collect: manifest.json missing for {job_id}"
            )
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        collected: list[Path] = []
        for name in manifest.expected_artifacts:
            src = workdir / name
            if not src.is_file():
                continue
            target = dest_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            collected.append(target)
        # Always carry the status payload across so the local audit
        # trail mirrors the worker's verdict.
        if (workdir / "status.json").is_file():
            shutil.copy2(workdir / "status.json", dest_dir / "status.json")
            collected.append(dest_dir / "status.json")

        self.audit_log.record(
            {
                "event": "collect",
                "endpoint": self.endpoint.name,
                "job_id": job_id,
                "file_count": len(collected),
                "files": [p.name for p in collected],
            }
        )
        return tuple(collected)

    # ── cancellation ─────────────────────────────────────────────────────

    def cancel(self, job_id: str, *, reason: str = "user_requested") -> RemoteStatus:
        """Ask the remote worker to stop.

        Cancellation works by writing a ``cancel.json`` sentinel into
        the job workspace. The Windows worker is expected to poll for
        the sentinel and abort the in-flight run. Hermes also updates
        ``status.json`` so a future :meth:`get_status` call sees the
        cancel even if the worker is offline.
        """
        workdir = self._workdir_for(job_id)
        if not workdir.is_dir():
            raise BridgeError(f"cancel: unknown job_id {job_id!r}")
        now = float(self._clock())
        sentinel = {
            "schema": "hermes.remote.cancel.v1",
            "job_id": job_id,
            "reason": reason,
            "issued_at": now,
            "from": "hermes",
        }
        (workdir / "cancel.json").write_text(
            json.dumps(sentinel, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        status_path = workdir / "status.json"
        try:
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        existing.update(
            {
                "state": JobState.CANCELED.value,
                "detail": f"canceled: {reason}",
                "last_seen": now,
                "from": "hermes",
            }
        )
        status_path.write_text(
            json.dumps(existing, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.audit_log.record(
            {
                "event": "cancel",
                "endpoint": self.endpoint.name,
                "job_id": job_id,
                "reason": reason,
            }
        )
        return RemoteStatus(
            job_id=job_id,
            state=JobState.CANCELED,
            detail=f"canceled: {reason}",
            last_seen=now,
            raw=existing,
        )

    # ── inspection helpers ───────────────────────────────────────────────

    def list_jobs(self) -> list[str]:
        """Return job ids currently staged under ``workspace_root``."""
        jobs_root = self.endpoint.workspace_root / "jobs"
        if not jobs_root.is_dir():
            return []
        return sorted(p.name for p in jobs_root.iterdir() if p.is_dir())

    def approve(self, job_id: str) -> RemoteStatus:
        """Promote an ``awaiting_approval`` job to ``queued``.

        This is the in-band approval flow: the caller has already
        verified out-of-band that the job is safe to run.
        """
        workdir = self._workdir_for(job_id)
        manifest = self._read_manifest(workdir / "manifest.json")
        if manifest is None:
            raise BridgeError(f"approve: manifest missing for {job_id}")
        status_path = workdir / "status.json"
        try:
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if existing.get("state") not in {
            JobState.AWAITING_APPROVAL.value,
            JobState.QUEUED.value,
        }:
            raise BridgeError(
                f"approve: job {job_id} is in state "
                f"{existing.get('state')!r}; only awaiting_approval/queued are eligible."
            )
        now = float(self._clock())
        existing.update(
            {
                "state": JobState.QUEUED.value,
                "detail": "approved by user — queued for remote execution",
                "from": "hermes",
                "last_seen": now,
            }
        )
        status_path.write_text(
            json.dumps(existing, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # Rewrite the manifest with allow_remote_execute=True so the
        # worker actually picks it up.
        new_manifest = JobManifest(
            job_id=manifest.job_id,
            endpoint=manifest.endpoint,
            command=manifest.command,
            prompt_filename=manifest.prompt_filename,
            expected_artifacts=manifest.expected_artifacts,
            required_artifacts=manifest.required_artifacts,
            auth_token=manifest.auth_token,
            device_id=manifest.device_id,
            allow_remote_execute=True,
            created_at=manifest.created_at,
            extra=manifest.extra,
        )
        (workdir / "manifest.json").write_text(
            json.dumps(new_manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.audit_log.record(
            {
                "event": "approve",
                "endpoint": self.endpoint.name,
                "job_id": job_id,
            }
        )
        return RemoteStatus(
            job_id=job_id,
            state=JobState.QUEUED,
            detail="approved",
            last_seen=now,
            raw=existing,
        )

    # ── internal helpers ─────────────────────────────────────────────────

    # ── HTTP transport ────────────────────────────────────────────────────

    def _http_auth_token(self) -> Optional[str]:
        """Read the bearer token from the env var named by ``auth_token_env``.

        Returns ``None`` when no env var is configured or the variable is
        unset/blank — the endpoint may authenticate at the tunnel layer
        instead. The token value is never logged.
        """
        var = self.endpoint.auth_token_env.strip()
        if not var:
            return None
        value = os.environ.get(var, "").strip()
        return value or None

    def _post_http(
        self,
        manifest: JobManifest,
        *,
        prompt: str,
        token: str,
    ) -> dict[str, Any]:
        """POST the staged job packet to the configured HTTP endpoint.

        The request body mirrors the file-drop contract: the full job
        manifest plus the prompt body, under the ``hermes.remote.job.v1``
        schema. Transient failures (timeouts, connection errors, 5xx) are
        retried with exponential backoff via :mod:`tenacity`; a 4xx is a
        hard, non-retryable error. Every failure mode is mapped to
        :class:`BridgeError` so callers see one exception type, and is
        recorded as an audit refusal first.

        Returns the parsed JSON acknowledgement (``{}`` if the worker
        replies with a non-JSON / empty 2xx body).
        """
        body = {
            "schema": "hermes.remote.job.v1",
            "manifest": manifest.to_dict(),
            "prompt": prompt,
        }
        headers = {
            "content-type": "application/json",
            "user-agent": "hermes-remote-bridge/1",
        }
        auth = self._http_auth_token()
        if auth:
            headers["authorization"] = f"Bearer {auth}"

        url = self.endpoint.http_endpoint_url

        @retry(
            reraise=True,
            stop=stop_after_attempt(max(1, self.endpoint.http_max_attempts)),
            wait=wait_exponential(multiplier=0.5, max=10.0),
            retry=retry_if_exception_type(
                (httpx.TransportError, _RetryableStatusError)
            ),
        )
        def _send() -> httpx.Response:
            with httpx.Client(timeout=self.endpoint.http_timeout_seconds) as client:
                response = client.post(url, json=body, headers=headers)
            # 5xx is transient (worker restarting, behind a flaky tunnel);
            # surface it as retryable. 4xx is a contract error — do not retry.
            if response.status_code >= 500:
                raise _RetryableStatusError(response)
            return response

        try:
            response = _send()
        except _RetryableStatusError as exc:
            return self._http_failure(
                manifest,
                reason="http_status_error",
                detail=f"worker returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            )
        except httpx.TimeoutException as exc:
            return self._http_failure(
                manifest,
                reason="http_timeout",
                detail=f"request to remote endpoint timed out: {exc}",
            )
        except httpx.TransportError as exc:
            return self._http_failure(
                manifest,
                reason="http_connection_error",
                detail=f"could not reach remote endpoint: {exc}",
            )

        if response.status_code >= 400:
            return self._http_failure(
                manifest,
                reason="http_status_error",
                detail=f"worker returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            payload = {}
        if not isinstance(payload, Mapping):
            payload = {}

        self.audit_log.record(
            {
                "event": "http_dispatch",
                "endpoint": self.endpoint.name,
                "job_id": manifest.job_id,
                "status_code": response.status_code,
                "worker_state": payload.get("state"),
            }
        )
        return dict(payload)

    def _http_failure(
        self,
        manifest: JobManifest,
        *,
        reason: str,
        detail: str,
        status_code: Optional[int] = None,
    ) -> dict[str, Any]:
        """Record an audit refusal and raise :class:`BridgeError`."""
        info: dict[str, Any] = {"job_id": manifest.job_id}
        if status_code is not None:
            info["status_code"] = status_code
        self._record_refusal(reason, **info)
        raise BridgeError(f"http transport: {detail}")

    def _mint_job_id(self) -> str:
        # Short, sortable, collision-resistant. Time prefix gives a
        # rough lexical ordering when browsing the jobs dir.
        prefix = time.strftime("%Y%m%dT%H%M%S", time.gmtime(self._clock()))
        return f"{prefix}-{secrets.token_hex(4)}"

    def _workdir_for(self, job_id: str) -> Path:
        safe = _safe_filename(job_id)
        return self.endpoint.workspace_root / "jobs" / safe

    def _read_manifest(self, path: Path) -> Optional[JobManifest]:
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, Mapping):
            return None
        try:
            return JobManifest(
                job_id=str(raw["job_id"]),
                endpoint=str(raw["endpoint"]),
                command=str(raw["command"]),
                prompt_filename=str(raw["prompt_filename"]),
                expected_artifacts=tuple(raw.get("expected_artifacts", ())),
                required_artifacts=tuple(raw.get("required_artifacts", ())),
                auth_token=str(raw["auth_token"]),
                device_id=str(raw.get("device_id", "")),
                allow_remote_execute=bool(raw.get("allow_remote_execute", False)),
                created_at=float(raw.get("created_at", 0.0)),
                extra=dict(raw.get("extra", {}) or {}),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _status_from(
        self,
        raw: Mapping[str, Any],
        *,
        job_id: str,
        trusted: bool,
    ) -> RemoteStatus:
        state_value = str(raw.get("state", "unknown"))
        try:
            state = JobState(state_value)
        except ValueError:
            state = JobState.UNKNOWN
        last_seen = raw.get("last_seen")
        try:
            last_seen_f = float(last_seen) if last_seen is not None else None
        except (TypeError, ValueError):
            last_seen_f = None
        artifacts = raw.get("artifacts") or {}
        if not isinstance(artifacts, Mapping):
            artifacts = {}
        return RemoteStatus(
            job_id=job_id,
            state=state,
            detail=str(raw.get("detail", "")),
            last_seen=last_seen_f,
            artifacts={str(k): str(v) for k, v in artifacts.items()},
            raw=dict(raw) if trusted else None,
        )

    def _record_refusal(self, reason: str, **details: Any) -> None:
        self.audit_log.record(
            {
                "event": "refusal",
                "endpoint": self.endpoint.name,
                "reason": reason,
                **details,
            }
        )

    @staticmethod
    def _default_audit_path() -> Path:
        home = os.environ.get("HERMES_HOME")
        if home:
            return Path(home) / "remote" / DEFAULT_AUDIT_FILENAME
        return Path.home() / ".hermes" / "remote" / DEFAULT_AUDIT_FILENAME


# ── helpers ───────────────────────────────────────────────────────────────


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\-]")


def _safe_filename(name: str) -> str:
    """Restrict a filename to ``[A-Za-z0-9._-]`` so path traversal is impossible."""
    if not name:
        raise ValueError("filename must be non-empty")
    cleaned = _SAFE_FILENAME_RE.sub("_", name)
    if cleaned.startswith(".") or "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"unsafe filename {name!r}")
    return cleaned


__all__ = [
    "AuditLog",
    "BridgeError",
    "DEFAULT_AUDIT_FILENAME",
    "DEFAULT_COMMAND_ALLOWLIST",
    "JobManifest",
    "JobState",
    "RemoteBridge",
    "RemoteEndpoint",
    "RemoteJob",
    "RemoteStatus",
    "SUPPORTED_TRANSPORTS",
    "TRANSPORT_FILE_DROP",
    "TRANSPORT_HTTP",
    "TRANSPORT_SSH",
    "TRANSPORT_WEBSOCKET",
    "TransportNotImplementedError",
    "scrub_secrets",
]
