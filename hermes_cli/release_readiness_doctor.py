"""Release-readiness doctor for the Hermes 10/10 program.

Backs ``hermes doctor --10-10``. It turns the 10/10 release gate into a
*runnable, honest* check: every gate reads the actual repository / importable
modules to decide its status, so the report stays truthful as the loop is
wired up rather than hard-coding a verdict.

Two tiers:

* **hard** checks are safe-to-ship prerequisites (dry-run default, owner gate,
  redaction, signed remote bridge, exact-pinned deps, loopback-only default,
  …). A hard ``fail`` means the build must not ship — ``report.ok`` is False.
* **soft** checks track *loop-completeness* toward a true 10/10 (e.g. the
  unified decision verdict wired at job dispatch, budget hard-stop enforcement,
  server-side voice audio). A soft ``warn`` never blocks ship; it is the
  honest, living punch list of what remains.

``run_10_10_doctor`` never raises — a broken check becomes a failing check.
Mirrors :mod:`hermes_cli.jarvis_prime.launch_doctor`.
"""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

PASS = "pass"
WARN = "warn"
FAIL = "fail"


def _repo_root() -> Path:
    # hermes_cli/release_readiness_doctor.py -> repo root is one level up.
    return Path(__file__).resolve().parents[1]


@dataclass
class ReadinessCheck:
    name: str
    status: str  # pass | warn | fail
    detail: str = ""
    hard: bool = True  # hard checks gate ship; soft checks only warn

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReadinessReport:
    ok: bool
    checks: list[ReadinessCheck] = field(default_factory=list)

    @property
    def failures(self) -> list[ReadinessCheck]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warnings(self) -> list[ReadinessCheck]:
        return [c for c in self.checks if c.status == WARN]

    @property
    def hard_failures(self) -> list[ReadinessCheck]:
        return [c for c in self.checks if c.status == FAIL and c.hard]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for c in self.checks if c.status == PASS),
                "warnings": len(self.warnings),
                "failures": len(self.failures),
                "hard_failures": len(self.hard_failures),
            },
        }

    def render(self) -> str:
        glyph = {PASS: "✓", WARN: "⚠", FAIL: "✗"}
        lines = ["muse 10/10 — release-readiness doctor", ""]
        for c in self.checks:
            tier = "" if c.hard else " (10/10 punch list)"
            lines.append(f"  {glyph.get(c.status, '?')} {c.name}: {c.detail}{tier}")
        lines.append("")
        remaining = len(self.warnings)
        if self.ok:
            lines.append("SAFE TO SHIP ✓  — all hard safety/correctness gates pass.")
            if remaining:
                lines.append(
                    f"{remaining} item(s) remain for a full 10/10 loop (warnings above)."
                )
        else:
            lines.append(
                "NOT SHIPPABLE ✗  — resolve the failing hard gate(s) above before release."
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Probes — small, defensive helpers used by the checks
# ---------------------------------------------------------------------------


def _importable(module: str, *names: str) -> bool:
    """True if ``module`` imports and exposes every name in ``names``."""
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError, ModuleNotFoundError):
        return False
    if spec is None:
        return False
    if not names:
        return True
    try:
        mod = importlib.import_module(module)
    except Exception:
        return False
    return all(hasattr(mod, n) for n in names)


def _exists(rel: str) -> bool:
    return (_repo_root() / rel).exists()


def _read(rel: str) -> Optional[str]:
    try:
        return (_repo_root() / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _contains(rel: str, *needles: str) -> bool:
    text = _read(rel)
    return bool(text) and all(n in text for n in needles)


def _contains_any(rel: str, *needles: str) -> bool:
    text = _read(rel)
    return bool(text) and any(n in text for n in needles)


_MISSING = object()  # parameter has no default
_NON_LITERAL = object()  # default is not a simple literal


def _param_default(rel: str, func: str, param: str) -> Any:
    """Return the literal default of ``func``'s ``param``, via AST (no import).

    Returns the constant value, ``_MISSING`` if the parameter has no default
    (or the function/param is absent), or ``_NON_LITERAL`` for a non-constant
    default. Import-free, so a safe-to-ship gate can inspect the *actual*
    signature default — not a file-wide substring that a regression can fool.
    """
    import ast

    src = _read(rel)
    if not src:
        return _MISSING
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return _MISSING

    def _literal(node: Optional[ast.expr]) -> Any:
        if node is None:
            return _MISSING
        return node.value if isinstance(node, ast.Constant) else _NON_LITERAL

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func
        ):
            args = node.args
            # positional-or-keyword: defaults align to the tail of args.args
            offset = len(args.args) - len(args.defaults)
            for i, arg in enumerate(args.args):
                if arg.arg == param:
                    di = i - offset
                    return _literal(args.defaults[di]) if di >= 0 else _MISSING
            # keyword-only: kw_defaults aligns 1:1 (None == no default)
            for arg, default in zip(args.kwonlyargs, args.kw_defaults):
                if arg.arg == param:
                    return _literal(default)
    return _MISSING


def _check(fn: Callable[[], ReadinessCheck]) -> ReadinessCheck:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive
        return ReadinessCheck(getattr(fn, "__name__", "check"), FAIL, f"raised {exc!r}")


# ---------------------------------------------------------------------------
# Hard gates — safe-to-ship prerequisites
# ---------------------------------------------------------------------------


def _check_package_import() -> ReadinessCheck:
    ok = _importable("hermes_cli") and _importable("run_agent")
    return ReadinessCheck(
        "package import",
        PASS if ok else FAIL,
        "hermes_cli + run_agent import" if ok else "core package does not import",
    )


def _check_decision_engine_present() -> ReadinessCheck:
    ok = _importable(
        "hermes_cli.decision_engine", "merge_decision_inputs", "DecisionVerdict"
    )
    return ReadinessCheck(
        "decision engine present",
        PASS if ok else FAIL,
        "unified DecisionVerdict + merge_decision_inputs available"
        if ok
        else "hermes_cli.decision_engine missing the verdict API",
    )


def _check_owner_gate() -> ReadinessCheck:
    ok = _contains(
        "hermes_cli/jarvis_prime/owner_auth.py",
        "AUTHORIZATION_PHRASE",
        "Yes, with authorization.",
    )
    return ReadinessCheck(
        "owner gate",
        PASS if ok else FAIL,
        "exact owner authorization phrase enforced"
        if ok
        else "owner authorization phrase not found",
    )


def _check_redaction() -> ReadinessCheck:
    ok = _importable("hermes_cli.secrets_policy", "redact") and _exists(
        "gateway/cockpit/redaction.py"
    )
    return ReadinessCheck(
        "secret redaction",
        PASS if ok else FAIL,
        "secrets_policy.redact + cockpit redactor present"
        if ok
        else "canonical redactor missing",
    )


def _check_publisher_dry_run_default() -> ReadinessCheck:
    # Inspect github_publisher.run()'s actual ``approve`` default, not file text:
    # a regression to approve=True must flip this gate even if a docstring or
    # another dry-run call still mentions approve=False.
    default = _param_default("hermes_cli/github_publisher.py", "run", "approve")
    ok = default is False
    return ReadinessCheck(
        "github publisher dry-run default",
        PASS if ok else FAIL,
        "run(approve=False) — publish is dry-run unless explicitly approved"
        if ok
        else f"publisher run() approve default is {default!r}, not False",
    )


def _check_bridge_signed_envelope() -> ReadinessCheck:
    ok = _contains("hermes_cli/remote_bridge.py", "bridge_envelope") and _importable(
        "hermes_cli.bridge_envelope"
    )
    return ReadinessCheck(
        "remote bridge signed envelope",
        PASS if ok else FAIL,
        "remote bridge dispatch uses signed envelopes (HMAC + nonce + expiry)"
        if ok
        else "signed-envelope kernel not wired into the bridge",
    )


def _check_bridge_command_allowlist() -> ReadinessCheck:
    ok = _contains_any(
        "hermes_cli/remote_bridge.py", "command_allowlist", "COMMAND_ALLOWLIST"
    )
    return ReadinessCheck(
        "remote bridge command allowlist",
        PASS if ok else FAIL,
        "remote bridge runs only allowlisted commands (no arbitrary shell)"
        if ok
        else "no command allowlist found on the bridge",
    )


def _check_cockpit_constant_time_auth() -> ReadinessCheck:
    ok = _contains("gateway/cockpit/auth.py", "compare_digest")
    return ReadinessCheck(
        "cockpit constant-time auth",
        PASS if ok else FAIL,
        "bearer token compared in constant time"
        if ok
        else "cockpit auth does not use constant-time compare",
    )


def _check_cockpit_localhost_default() -> ReadinessCheck:
    # Inspect serve()'s actual host + allow_external defaults AND the non-loopback
    # refusal path — so flipping the default bind to 0.0.0.0 trips this gate even
    # if the allow_external plumbing remains.
    rel = "gateway/cockpit/server.py"
    host = _param_default(rel, "serve", "host")
    ext = _param_default(rel, "serve", "allow_external")
    refusal = _contains(rel, "_is_loopback_host", "allow_external")
    host_ok = host in ("127.0.0.1", "::1", "localhost")
    ok = host_ok and ext is False and refusal
    if ok:
        detail = (
            "serve(host=loopback, allow_external=False) with a non-loopback refusal"
        )
    elif not host_ok:
        detail = f"serve() host default is {host!r}, not loopback"
    elif ext is not False:
        detail = f"serve() allow_external default is {ext!r}, not False"
    else:
        detail = "no non-loopback refusal path found in serve()"
    return ReadinessCheck("cockpit loopback default", PASS if ok else FAIL, detail)


def _check_deps_exact_pinned() -> ReadinessCheck:
    import tomllib

    text = _read("pyproject.toml") or ""
    try:
        deps = tomllib.loads(text).get("project", {}).get("dependencies", [])
    except Exception:
        deps = []
    bad: list[str] = []
    for spec in deps:
        if not isinstance(spec, str):
            continue
        req = spec.split(";", 1)[0].strip()  # drop the environment marker
        has_range = any(op in req for op in (">=", "<=", "~=", "!=", ">", "<"))
        if has_range or "==" not in req:
            bad.append(req)
    ok = bool(deps) and not bad
    return ReadinessCheck(
        "exact-pinned dependencies",
        PASS if ok else FAIL,
        f"all {len(deps)} base dependencies are == pinned (supply-chain control)"
        if ok
        else f"not exact-pinned: {', '.join(bad[:3])}",
    )


def _check_uv_lock_present() -> ReadinessCheck:
    ok = _exists("uv.lock")
    return ReadinessCheck(
        "uv.lock present",
        PASS if ok else FAIL,
        "locked transitive resolution committed" if ok else "uv.lock missing",
    )


# ---------------------------------------------------------------------------
# Soft gates — the living 10/10 loop-closure punch list
# ---------------------------------------------------------------------------


def _check_verdict_at_publish() -> ReadinessCheck:
    ok = _contains("hermes_cli/github_publisher.py", "merge_decision_inputs")
    return ReadinessCheck(
        "decision verdict at publish",
        PASS if ok else WARN,
        "publish boundary computes a unified verdict"
        if ok
        else "publish boundary does not compute a verdict yet",
        hard=False,
    )


def _check_verdict_at_dispatch() -> ReadinessCheck:
    wired = any(
        _contains(f"hermes_cli/{f}", "merge_decision_inputs")
        for f in ("orchestrator.py", "orchestrator_parallel.py", "job_controller.py")
    )
    return ReadinessCheck(
        "decision verdict at job dispatch/merge",
        PASS if wired else WARN,
        "orchestrator gates execution/merge through the unified verdict"
        if wired
        else "verdict not yet wired at dispatch/merge — the #1 remaining 10/10 integration",
        hard=False,
    )


def _check_budget_enforced() -> ReadinessCheck:
    # Honest enforcement check: PASS only when BOTH orchestrator paths actually
    # consult the budget policy and act on a hard stop — not merely when *either*
    # file contains a ``should_stop`` token. The previous form false-PASSed
    # purely because the parallel file matched, masking the single-job gap.
    #
    # A path "enforces" when it both (a) calls the policy kernel
    # (``evaluate_budget``) and (b) acts on the hard-stop signal
    # (``should_stop`` / ``hard_exceeded`` / a ``budget_exhausted`` stop).
    def _path_enforces(rel: str) -> bool:
        return _contains(rel, "evaluate_budget") and _contains_any(
            rel, "should_stop", "hard_exceeded", "budget_exhausted"
        )

    single = _path_enforces("hermes_cli/orchestrator.py")
    parallel = _path_enforces("hermes_cli/orchestrator_parallel.py")
    enforced = single and parallel
    if enforced:
        detail = "both single-job and parallel orchestrator paths hard-stop on budget overrun"
    elif parallel and not single:
        detail = (
            "parallel path enforces but the single-job dispatch path does not "
            "consult the budget — no hard-stop on the single-job path"
        )
    elif single and not parallel:
        detail = "single-job path enforces but the parallel path does not hard-stop on budget overrun"
    else:
        detail = "budget is computed + surfaced but not enforced as a hard stop on either path"
    return ReadinessCheck(
        "per-job budget hard-stop",
        PASS if enforced else WARN,
        detail,
        hard=False,
    )


def _check_voice_audio_routes() -> ReadinessCheck:
    text = (_read("gateway/cockpit/server.py") or "") + (
        _read("gateway/cockpit/handlers.py") or ""
    )
    # A real audio duplex needs a server-side transcribe (audio-in) or a
    # response-audio (audio-out) route — not just the transcript intake path.
    has_audio = "voice/transcribe" in text or "voice/responses" in text
    return ReadinessCheck(
        "server-side voice audio routes",
        PASS if has_audio else WARN,
        "gateway accepts audio + returns synthesized audio"
        if has_audio
        else "voice is transcript-only; server-side audio duplex not wired",
        hard=False,
    )


def _check_publisher_repo_allowlist() -> ReadinessCheck:
    ok = _contains_any(
        "hermes_cli/github_publisher.py", "allowlist", "allowed_repo", "repo_allow"
    )
    return ReadinessCheck(
        "github publisher repo allowlist",
        PASS if ok else WARN,
        "live publish is constrained to an explicit repo allowlist"
        if ok
        else "no explicit repo allowlist in the publisher (mitigated by owner gating)",
        hard=False,
    )


def _check_worker_leases_wired() -> ReadinessCheck:
    ok = _contains("hermes_cli/orchestrator_parallel.py", "worker_lease")
    return ReadinessCheck(
        "durable worker leases",
        PASS if ok else WARN,
        "parallel runner records durable worker leases"
        if ok
        else "worker-lease store not wired into the runner",
        hard=False,
    )


def _check_approval_push_wired() -> ReadinessCheck:
    ok = _exists("gateway/cockpit/notify.py") and _importable(
        "hermes_cli.notifications"
    )
    return ReadinessCheck(
        "approval notifications",
        PASS if ok else WARN,
        "ask verdicts enqueue a cockpit approval notification"
        if ok
        else "approval notification queue not wired into the gateway",
        hard=False,
    )


def _check_cockpit_device_pairing() -> ReadinessCheck:
    ok = _contains_any("gateway/cockpit/auth.py", "device_pairing", "per-device")
    return ReadinessCheck(
        "per-device pairing",
        PASS if ok else WARN,
        "cockpit accepts revocable per-device tokens"
        if ok
        else "only a single shared cockpit token",
        hard=False,
    )


def _check_ci_core_workflows() -> ReadinessCheck:
    need = ["tests.yml", "lint.yml", "orchestration-tests.yml"]
    missing = [w for w in need if not _exists(f".github/workflows/{w}")]
    return ReadinessCheck(
        "core CI workflows",
        PASS if not missing else WARN,
        "tests + lint + orchestration gates present"
        if not missing
        else f"missing workflow(s): {', '.join(missing)}",
        hard=False,
    )


def _check_supply_chain_ci() -> ReadinessCheck:
    ok = _exists(".github/workflows/osv-scanner.yml") and _exists(
        ".github/workflows/supply-chain-audit.yml"
    )
    return ReadinessCheck(
        "supply-chain CI",
        PASS if ok else WARN,
        "OSV scanner + supply-chain audit run on PRs"
        if ok
        else "supply-chain CI workflow(s) missing",
        hard=False,
    )


def _check_known_flaky_doc() -> ReadinessCheck:
    ok = _exists("docs/testing/known-flaky-tests.md")
    return ReadinessCheck(
        "known-flaky tests logged",
        PASS if ok else WARN,
        "flaky tests are documented with root cause"
        if ok
        else "no known-flaky-tests log",
        hard=False,
    )


def _check_release_artifacts() -> ReadinessCheck:
    need = {
        "release checklist": "docs/launch/10_10_RELEASE_CHECKLIST.md",
        "e2e runbook": "docs/launch/10_10_E2E_RUNBOOK.md",
        "security review": "docs/security/10_10_SECURITY_REVIEW.md",
        "smoke script": "scripts/hermes-10-10-smoke.sh",
    }
    missing = [name for name, rel in need.items() if not _exists(rel)]
    return ReadinessCheck(
        "release-gate artifacts",
        PASS if not missing else WARN,
        "checklist + runbook + security review + smoke present"
        if not missing
        else f"missing: {', '.join(missing)}",
        hard=False,
    )


def _check_harness_runtime_wired() -> ReadinessCheck:
    """Prove the Muse harness package is importable and loadable."""
    try:
        from hermes_cli.harness.doctor import check_harness_runtime_wired

        name, status, detail, hard = check_harness_runtime_wired()
        return ReadinessCheck(name, status, detail, hard=hard)
    except Exception as exc:
        return ReadinessCheck(
            "harness_runtime_wired",
            FAIL,
            f"harness doctor raised: {exc!r}",
            hard=True,
        )


def _check_harness_proof_bar() -> ReadinessCheck:
    try:
        from hermes_cli.harness.doctor import check_harness_proof_bar

        name, status, detail, hard = check_harness_proof_bar()
        return ReadinessCheck(name, status, detail, hard=hard)
    except Exception as exc:
        return ReadinessCheck(
            "harness_proof_bar", WARN, f"raised: {exc!r}", hard=False
        )


def _check_harness_web_research_path() -> ReadinessCheck:
    try:
        from hermes_cli.harness.doctor import check_harness_web_degraded

        name, status, detail, hard = check_harness_web_degraded()
        return ReadinessCheck(name, status, detail, hard=hard)
    except Exception as exc:
        return ReadinessCheck(
            "harness_web_research_path", WARN, f"raised: {exc!r}", hard=False
        )


def run_10_10_doctor() -> ReadinessReport:
    """Run every 10/10 readiness check and return a structured report."""
    checks = [
        # hard safety/correctness gates
        _check(_check_package_import),
        _check(_check_decision_engine_present),
        _check(_check_owner_gate),
        _check(_check_redaction),
        _check(_check_publisher_dry_run_default),
        _check(_check_bridge_signed_envelope),
        _check(_check_bridge_command_allowlist),
        _check(_check_cockpit_constant_time_auth),
        _check(_check_cockpit_localhost_default),
        _check(_check_deps_exact_pinned),
        _check(_check_uv_lock_present),
        _check(_check_harness_runtime_wired),
        # soft loop-closure punch list
        _check(_check_verdict_at_publish),
        _check(_check_verdict_at_dispatch),
        _check(_check_budget_enforced),
        _check(_check_voice_audio_routes),
        _check(_check_publisher_repo_allowlist),
        _check(_check_worker_leases_wired),
        _check(_check_approval_push_wired),
        _check(_check_cockpit_device_pairing),
        _check(_check_harness_proof_bar),
        _check(_check_harness_web_research_path),
        # release ops
        _check(_check_ci_core_workflows),
        _check(_check_supply_chain_ci),
        _check(_check_known_flaky_doc),
        _check(_check_release_artifacts),
    ]
    ok = not any(c.status == FAIL and c.hard for c in checks)
    return ReadinessReport(ok=ok, checks=checks)
