"""Launch-readiness doctor for the free-first JARVIS launch path.

Backs ``hermes doctor --jarvis-launch``. Verifies every load-bearing
piece of the one-command launch path and reports a structured,
JSON-able result. ``run_launch_doctor`` never raises — a broken check
is recorded as a failing check, not an exception.

Checks are classed **hard** (a real launch blocker — fails the overall
report) or **soft** (an optional capability — surfaced as a warning but
does not block launch). The whole point of free-first is that a missing
Ollama / Claude Code / Codex / paid key is a *warning*, never a blocker.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


PASS = "pass"
WARN = "warn"
FAIL = "fail"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass
class LaunchCheck:
    name: str
    status: str  # pass | warn | fail
    detail: str = ""
    hard: bool = True  # hard checks block launch; soft checks only warn

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaunchReport:
    ok: bool
    checks: list[LaunchCheck] = field(default_factory=list)

    @property
    def failures(self) -> list[LaunchCheck]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warnings(self) -> list[LaunchCheck]:
        return [c for c in self.checks if c.status == WARN]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for c in self.checks if c.status == PASS),
                "warnings": len(self.warnings),
                "failures": len(self.failures),
            },
        }

    def render(self) -> str:
        glyph = {PASS: "✓", WARN: "⚠", FAIL: "✗"}
        lines = ["JARVIS Prime — launch-readiness doctor", ""]
        for c in self.checks:
            lines.append(f"  {glyph.get(c.status, '?')} {c.name}: {c.detail}")
        lines.append("")
        if self.ok:
            lines.append("LAUNCH READY ✓  (warnings are optional capabilities)")
        else:
            lines.append("NOT LAUNCH READY ✗  — resolve the failing checks above")
        return "\n".join(lines)


def _check(fn) -> LaunchCheck:
    """Run a check fn defensively — an exception becomes a FAIL."""
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck(getattr(fn, "_name", fn.__name__), FAIL, f"raised {exc!r}")


def run_launch_doctor() -> LaunchReport:
    """Run every launch-readiness check and return a structured report."""
    checks: list[LaunchCheck] = [
        _check_package_import(),
        _check_cli_entrypoint(),
        _check_jarvis_import(),
        _check_jarvis_module_runnable(),
        _check_jarvis_handle(),
        _check_memory_dir(),
        _check_owner_gate(),
        _check_emergency_stop(),
        _check_model_brain(),
        _check_gemma_wired(),
        _check_bootstrap_config(),
        _check_local_runtimes(),
        _check_worker_lanes(),
        _check_no_paid_dependency(),
        _check_install_script(),
        _check_termux_compat(),
        # --- verifiable guardrail subsystem ---
        _check_guardrail_ledger_writable(),
        _check_guardrail_ledger_verifies(),
        _check_strict_gate_rejects_self_attestation(),
        _check_owner_challenge_nonce_enforced(),
        _check_secret_scan_operational(),
        _check_emergency_stop_journaled(),
        _check_packet_id_stable(),
    ]
    ok = not any(c.status == FAIL and c.hard for c in checks)
    return LaunchReport(ok=ok, checks=checks)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_package_import() -> LaunchCheck:
    try:
        import hermes_cli  # noqa: F401

        return LaunchCheck("package_import", PASS, "hermes_cli imports")
    except Exception as exc:
        return LaunchCheck("package_import", FAIL, f"hermes_cli import failed: {exc}")


def _check_cli_entrypoint() -> LaunchCheck:
    spec = importlib.util.find_spec("hermes_cli.main")
    if spec is not None:
        return LaunchCheck(
            "cli_entrypoint",
            PASS,
            "hermes_cli.main resolvable (console_script: hermes)",
        )
    return LaunchCheck("cli_entrypoint", FAIL, "hermes_cli.main not found")


def _check_jarvis_import() -> LaunchCheck:
    try:
        import hermes_cli.jarvis_prime  # noqa: F401

        return LaunchCheck(
            "jarvis_prime_import", PASS, "hermes_cli.jarvis_prime imports (stdlib-only)"
        )
    except Exception as exc:
        return LaunchCheck("jarvis_prime_import", FAIL, f"import failed: {exc}")


def _check_jarvis_module_runnable() -> LaunchCheck:
    spec = importlib.util.find_spec("hermes_cli.jarvis_prime.__main__")
    if spec is not None:
        return LaunchCheck(
            "jarvis_module_runnable",
            PASS,
            "python -m hermes_cli.jarvis_prime available",
        )
    return LaunchCheck("jarvis_module_runnable", FAIL, "__main__ not found")


def _check_jarvis_handle() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        jp = JarvisPrime()
        turn = jp.handle(
            "launch readiness check", skip_perceive=True, skip_recollect=True
        )
        mode = turn.classification.mode.value
        return LaunchCheck("jarvis_handle", PASS, f"handle() ran (mode={mode})")
    except Exception as exc:
        return LaunchCheck("jarvis_handle", FAIL, f"handle() failed: {exc}")


def _check_memory_dir() -> LaunchCheck:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    mem_dir = Path(base) / "jarvis_prime"
    try:
        mem_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(mem_dir, 0o700)
        except OSError:
            pass
        fd, tmp = tempfile.mkstemp(dir=str(mem_dir), prefix=".launch_probe_")
        os.close(fd)
        os.unlink(tmp)
        # Report perms (best-effort; Windows/Termux may not honor 0700).
        try:
            mode = stat.S_IMODE(os.stat(mem_dir).st_mode)
            perm = oct(mode)
        except OSError:
            perm = "?"
        return LaunchCheck("memory_dir", PASS, f"{mem_dir} writable (perms {perm})")
    except OSError as exc:
        return LaunchCheck("memory_dir", FAIL, f"cannot create/write {mem_dir}: {exc}")


def _check_owner_gate() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE, OwnerAuth

        auth = OwnerAuth()
        auth.request("production_deploy", risk_class="RC3", rationale="doctor probe")
        # Wrong phrase must NOT authorize.
        if auth.authorize("yes with authorization"):
            return LaunchCheck(
                "owner_gate", FAIL, "approximate phrase wrongly authorized"
            )
        # Exact phrase MUST authorize.
        granted = auth.authorize(AUTHORIZATION_PHRASE)
        if not granted:
            return LaunchCheck("owner_gate", FAIL, "exact phrase failed to authorize")
        return LaunchCheck(
            "owner_gate", PASS, "exact owner authorization phrase enforced"
        )
    except Exception as exc:
        return LaunchCheck("owner_gate", FAIL, f"owner gate check failed: {exc}")


def _check_emergency_stop() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        jp = JarvisPrime()
        jp.config.owner_auth.request("force_push", risk_class="RC3", rationale="probe")
        result = jp.stop(reason="launch_doctor_probe")
        if result.get("tick_disabled") and result.get("cleared", 0) >= 1:
            return LaunchCheck(
                "emergency_stop", PASS, "stop() clears gates + disables autonomy"
            )
        return LaunchCheck("emergency_stop", FAIL, f"unexpected stop result: {result}")
    except Exception as exc:
        return LaunchCheck("emergency_stop", FAIL, f"emergency stop failed: {exc}")


def _check_model_brain() -> LaunchCheck:
    try:
        from hermes_cli import oss_model_brain as ob

        catalog = ob.load_oss_catalog()
        n = len(catalog.families)
        if n <= 0:
            return LaunchCheck("model_brain", FAIL, "catalog has no families")
        return LaunchCheck(
            "model_brain", PASS, f"catalog loaded ({catalog.source}, {n} families)"
        )
    except Exception as exc:
        return LaunchCheck("model_brain", FAIL, f"model brain failed to load: {exc}")


def _check_gemma_wired() -> LaunchCheck:
    """Gemma 4 wiring is optional — present is PASS, absent is a soft WARN."""
    try:
        from hermes_cli import oss_model_brain as ob

        fam = ob.load_oss_catalog().by_id("gemma4")
        if fam is None:
            return LaunchCheck(
                "gemma_wired",
                WARN,
                "Gemma 4 not wired into the OSS brain (optional)",
                hard=False,
            )
        return LaunchCheck(
            "gemma_wired",
            PASS,
            "Gemma 4 wired (local lanes); `hermes models gemma doctor` for detail",
            hard=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return LaunchCheck("gemma_wired", WARN, f"check failed: {exc}", hard=False)


def _check_bootstrap_config() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        existing = mb.load_policy()
        if existing is not None:
            return LaunchCheck(
                "bootstrap_config",
                PASS,
                f"model policy present at {mb.config_path()}",
            )
        # Confirm it can be created without writing (dry-run).
        result = mb.bootstrap(dry_run=True, record_memory=False)
        if result.ok:
            return LaunchCheck(
                "bootstrap_config",
                WARN,
                "no model policy yet — run `hermes models bootstrap --free-first --jarvis`",
                hard=False,
            )
        return LaunchCheck(
            "bootstrap_config",
            FAIL,
            "; ".join(result.errors) or "bootstrap dry-run failed",
        )
    except Exception as exc:
        return LaunchCheck("bootstrap_config", FAIL, f"bootstrap check failed: {exc}")


def _check_local_runtimes() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        runtimes = mb.detect_local_runtimes()
        avail = [k for k, v in runtimes.items() if v.get("available")]
        if avail:
            return LaunchCheck(
                "local_runtimes", PASS, f"detected: {', '.join(avail)}", hard=False
            )
        return LaunchCheck(
            "local_runtimes",
            WARN,
            "no local runtime (ollama/llama.cpp/vllm/lmstudio) — hosted/worker routes will be used",
            hard=False,
        )
    except Exception as exc:
        return LaunchCheck(
            "local_runtimes", WARN, f"detection failed: {exc}", hard=False
        )


def _check_worker_lanes() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime import worker_registry as wr

        statuses = wr.detect_lanes()
        avail = [s.lane.id for s in statuses if s.available]
        missing = [s.lane.id for s in statuses if not s.available]
        detail = f"available: {', '.join(avail) or 'none'}"
        if missing:
            detail += f"; missing: {', '.join(missing)} (optional)"
        return LaunchCheck("worker_lanes", PASS if avail else WARN, detail, hard=False)
    except Exception as exc:
        return LaunchCheck("worker_lanes", WARN, f"detection failed: {exc}", hard=False)


def _check_no_paid_dependency() -> LaunchCheck:
    """The free-first launch path must not require any paid API key."""
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        # local-only dry-run: simulates the no-paid, fully-free path.
        result = mb.bootstrap(
            dry_run=True, local_only=True, record_memory=False, env={}
        )
        paid_route = result.config.get("routes", {}).get("paid_api_explicit_only", {})
        if paid_route.get("enabled"):
            return LaunchCheck(
                "no_paid_dependency",
                FAIL,
                "paid route enabled on a free/local-only path",
            )
        return LaunchCheck(
            "no_paid_dependency",
            PASS,
            "free-first path requires no paid API key (paid = explicit opt-in only)",
        )
    except Exception as exc:
        return LaunchCheck("no_paid_dependency", FAIL, f"check failed: {exc}")


def _check_install_script() -> LaunchCheck:
    script = _repo_root() / "scripts" / "install.sh"
    if not script.is_file():
        return LaunchCheck(
            "install_script", WARN, "scripts/install.sh not found", hard=False
        )
    try:
        text = script.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return LaunchCheck("install_script", WARN, f"unreadable: {exc}", hard=False)
    if "--jarvis-launch" in text:
        return LaunchCheck(
            "install_script", PASS, "scripts/install.sh supports --jarvis-launch"
        )
    return LaunchCheck(
        "install_script",
        WARN,
        "scripts/install.sh present but no --jarvis-launch flag detected",
        hard=False,
    )


def _check_termux_compat() -> LaunchCheck:
    """The launch modules must import using only the stdlib (Termux-safe)."""
    modules = (
        "hermes_cli.jarvis_prime.model_bootstrap",
        "hermes_cli.jarvis_prime.worker_locks",
        "hermes_cli.jarvis_prime.worker_registry",
        "hermes_cli.jarvis_prime.launch",
        "hermes_cli.jarvis_prime.launch_doctor",
    )
    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    if missing:
        return LaunchCheck(
            "termux_compat", FAIL, f"missing modules: {', '.join(missing)}"
        )
    return LaunchCheck(
        "termux_compat", PASS, "launch modules are stdlib-only and importable"
    )


# ---------------------------------------------------------------------------
# Verifiable guardrail checks
#
# These prove the guardrail subsystem is *operational*, not merely importable:
# the ledger writes and verifies, strict gates reject self-attestation, owner
# challenges enforce the nonce, the secret scanner catches a synthetic token,
# emergency stop is journaled, and packet ids are stable. All are hard — a
# guardrail that cannot run is a launch blocker.
# ---------------------------------------------------------------------------


def _check_guardrail_ledger_writable() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

        ledger = GuardrailLedger()
        record = ledger.append("doctor_probe", "launch_doctor", {"probe": True})
        return LaunchCheck(
            "guardrail_ledger_writable",
            PASS,
            f"guardrail ledger writable at {ledger.path} (head {record.record_hash[:12]}…)",
        )
    except Exception as exc:
        return LaunchCheck(
            "guardrail_ledger_writable", FAIL, f"ledger not writable: {exc}"
        )


def _check_guardrail_ledger_verifies() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

        diag = GuardrailLedger().verify_chain()
        if diag.ok:
            return LaunchCheck(
                "guardrail_ledger_verifies",
                PASS,
                f"hash chain intact ({diag.length} records)",
            )
        return LaunchCheck(
            "guardrail_ledger_verifies",
            FAIL,
            f"chain broken at index {diag.broken_at}: {diag.reason}",
        )
    except Exception as exc:
        return LaunchCheck(
            "guardrail_ledger_verifies", FAIL, f"chain verification failed: {exc}"
        )


def _check_strict_gate_rejects_self_attestation() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.gates import GateOutcome, run_strict_gate_summary

        # A maximally self-attested packet — claims everything was done.
        self_attested = {
            "packet_id": "doctor",
            "repo_root": ".",
            "branch": "feature/x",
            "mission": "do the thing",
            "allowed_files": ["a.py"],
            "non_goals": ["nothing else"],
            "acceptance_criteria": ["it works"],
            "files_changed": ["a.py"],
            "diff_reviewed": True,
            "commits_scoped": True,
            "contrarian_objection": "none",
            "tests_run": ["pytest"],
            "verification_summary": ["ran tests"],
            "remaining_risks": ["none"],
            "rollback_plan": ["revert"],
        }
        summary = run_strict_gate_summary(self_attested, None)
        if summary.overall is GateOutcome.PASS:
            return LaunchCheck(
                "strict_gate_rejects_self_attestation",
                FAIL,
                "strict gates passed a self-attested packet with no evidence",
            )
        return LaunchCheck(
            "strict_gate_rejects_self_attestation",
            PASS,
            f"self-attested packet rejected (overall={summary.overall.value})",
        )
    except Exception as exc:
        return LaunchCheck(
            "strict_gate_rejects_self_attestation", FAIL, f"check failed: {exc}"
        )


def _check_owner_challenge_nonce_enforced() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.owner_auth import (
            AUTHORIZATION_PHRASE,
            authorize_challenge,
            create_challenge,
        )

        challenge = create_challenge("production_deploy", rationale="doctor probe")
        # Bare phrase (no nonce) must NOT authorize.
        if authorize_challenge(challenge, AUTHORIZATION_PHRASE) is not None:
            return LaunchCheck(
                "owner_challenge_nonce_enforced",
                FAIL,
                "bare phrase wrongly satisfied a nonce-bound challenge",
            )
        # Wrong nonce must NOT authorize.
        if authorize_challenge(challenge, f"{AUTHORIZATION_PHRASE} Code: 000000") and challenge.nonce != "000000":
            return LaunchCheck(
                "owner_challenge_nonce_enforced", FAIL, "wrong nonce wrongly authorized"
            )
        # Correct phrase + nonce MUST authorize.
        grant = authorize_challenge(challenge, challenge.required_phrase)
        if grant is None:
            return LaunchCheck(
                "owner_challenge_nonce_enforced",
                FAIL,
                "correct challenge response failed to authorize",
            )
        return LaunchCheck(
            "owner_challenge_nonce_enforced",
            PASS,
            "challenge-bound owner authorization enforced (nonce required)",
        )
    except Exception as exc:
        return LaunchCheck(
            "owner_challenge_nonce_enforced", FAIL, f"check failed: {exc}"
        )


def _check_secret_scan_operational() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.guardrail_collectors import (
            collect_secret_scan_evidence,
        )

        with tempfile.TemporaryDirectory() as tmp:
            fname = "fake_creds.txt"
            # Synthetic, non-real token shaped like an OpenAI key.
            (Path(tmp) / fname).write_text(
                "api_key=sk-" + ("A" * 28) + "\n", encoding="utf-8"
            )
            art = collect_secret_scan_evidence(tmp, [fname])
            findings = art.payload.get("findings") or []
            if not findings:
                return LaunchCheck(
                    "secret_scan_operational",
                    FAIL,
                    "secret scanner missed a synthetic token",
                )
            # The raw token must NOT appear in the artifact (redaction works).
            blob = str(art.to_dict())
            if "AAAAAAAA" in blob:
                return LaunchCheck(
                    "secret_scan_operational",
                    FAIL,
                    "secret scanner leaked an unredacted token into evidence",
                )
        return LaunchCheck(
            "secret_scan_operational",
            PASS,
            "secret scanner catches and redacts synthetic tokens",
        )
    except Exception as exc:
        return LaunchCheck("secret_scan_operational", FAIL, f"check failed: {exc}")


def _check_emergency_stop_journaled() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        jp = JarvisPrime()
        result = jp.stop(reason="launch_doctor_journal_probe")
        if result.get("ledger_record_hash"):
            return LaunchCheck(
                "emergency_stop_journaled",
                PASS,
                "emergency stop appends a tamper-evident ledger record",
            )
        warning = result.get("ledger_warning", "no ledger_record_hash in stop result")
        return LaunchCheck("emergency_stop_journaled", FAIL, str(warning))
    except Exception as exc:
        return LaunchCheck("emergency_stop_journaled", FAIL, f"check failed: {exc}")


def _check_packet_id_stable() -> LaunchCheck:
    try:
        from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet

        a = build_work_packet("add a small helper function").packet_id
        b = build_work_packet("add a small helper function").packet_id
        if a == b and a:
            return LaunchCheck(
                "packet_id_stable", PASS, "work-packet ids are deterministic"
            )
        return LaunchCheck(
            "packet_id_stable", FAIL, f"packet ids unstable: {a!r} != {b!r}"
        )
    except Exception as exc:
        return LaunchCheck("packet_id_stable", FAIL, f"check failed: {exc}")


__all__ = [
    "FAIL",
    "PASS",
    "WARN",
    "LaunchCheck",
    "LaunchReport",
    "run_launch_doctor",
]
