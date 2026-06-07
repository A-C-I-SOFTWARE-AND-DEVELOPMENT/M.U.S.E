"""``hermes models gemma …`` command logic for JARVIS Prime.

Kept deliberately small and self-contained so the top-level CLI
(``hermes_cli/main.py``) only needs a thin parser + a one-line dispatch hook.
Subcommands:

* ``status``     — configured / installed / smoke-tested / promoted matrix.
* ``doctor``     — run the Gemma wiring + safety doctor.
* ``smoke``      — opt-in local completion probe (``--variant``). Network only
                   when explicitly invoked; injectable runner for tests.
* ``recommend``  — OSS-brain Gemma recommendations by tier / task.
* ``scorecards`` — measured Gemma scorecards.
* ``promote``    — owner-gated route-promotion proposal (``--task-class``,
                   ``--dry-run``). Builds a proposal; never auto-applies.

Every handler returns an exit code. ``--json`` is honored where it makes sense.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Optional


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _proposals_store_path() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "proposals.jsonl"


# Variants we surface in status/recommend. 12B is model-card only (no Ollama tag).
_GEMMA_VARIANTS = ("gemma4-e2b", "gemma4-e4b", "gemma4-26b-a4b", "gemma4-31b")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def _cmd_status(args: argparse.Namespace) -> int:
    from hermes_model_catalog import load_catalog
    from hermes_cli.local_models.catalog import load_open_weight_catalog

    catalog = load_catalog()
    configured = [m.ref for m in catalog.models if m.family == "gemma"]
    candidates = [
        m.name for m in load_open_weight_catalog().models if "gemma" in m.name
    ]
    installed = _detect_installed(getattr(args, "_ollama_runner", None))
    promoted = _promoted_lanes()
    load_status = _load_status_map()

    payload = {
        "configured": configured,
        "open_weight_candidates": candidates,
        "installed": installed,  # None ⇒ not probed (opt-in)
        "smoke_tested": "opt-in (run `hermes models gemma smoke --variant <v>`)",
        "load_status": load_status,  # persisted smoke results, by variant
        "promoted_lanes": promoted,
    }
    if getattr(args, "json", False):
        _print_json(payload)
        return 0
    print("Gemma 4 — JARVIS wiring status")
    print(f"  configured : {', '.join(configured) or '(none)'}")
    print(f"  candidates : {', '.join(candidates) or '(none)'}")
    if installed is None:
        print("  installed  : not probed (installed/smoke checks are opt-in)")
    else:
        print(f"  installed  : {', '.join(installed) or '(none found)'}")
    if load_status:
        summary = ", ".join(
            f"{v}={(e.get('status') if isinstance(e, dict) else e)}"
            for v, e in sorted(load_status.items())
        )
        print(f"  smoke      : {summary}")
    else:
        print("  smoke      : opt-in — `hermes models gemma smoke --variant <variant>`")
    print(f"  promoted   : {', '.join(promoted) or '(none — scorecards govern)'}")
    return 0


def _load_status_map() -> dict[str, Any]:
    """Persisted Gemma load (smoke) results, by variant. ``{}`` when none."""
    try:
        from hermes_cli.jarvis_prime import gemma_load_status as gls

        return gls.load_status()
    except Exception:
        return {}


def _detect_installed(runner: Optional[Callable[[], str]]) -> Optional[list[str]]:
    """Best-effort installed-variant detection. ``None`` ⇒ not probed."""
    if runner is None:
        return None
    try:
        out = runner() or ""
    except Exception:
        return None
    return [ln.split()[0] for ln in out.splitlines() if "gemma4" in ln.lower()]


def _promoted_lanes() -> list[str]:
    """Task classes whose owner override currently pins a Gemma model."""
    try:
        from hermes_cli.jarvis_prime import task_router as tr

        overrides = tr.load_overrides()
        return [
            tc
            for tc, model in (overrides.get("task_overrides") or {}).items()
            if tr.is_gemma(model)
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def _cmd_doctor(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.gemma_doctor import run_gemma_doctor

    report = run_gemma_doctor(
        ollama_list_runner=getattr(args, "_ollama_runner", None)
    )
    if getattr(args, "json", False):
        _print_json(report.to_dict())
    else:
        print(report.render())
    return 0 if report.ok else 1


# ---------------------------------------------------------------------------
# smoke (opt-in; network only when invoked)
# ---------------------------------------------------------------------------


def _cmd_smoke(args: argparse.Namespace) -> int:
    variant = getattr(args, "variant", None)
    if not variant:
        print("usage: hermes models gemma smoke --variant <variant>")
        return 2
    tag = variant if ":" in variant else variant.replace("gemma4-", "gemma4:").replace(
        "-a4b", ""
    )
    runner = getattr(args, "_smoke_runner", None) or _default_smoke_runner
    try:
        ok, detail = runner(tag)
    except Exception as exc:  # pragma: no cover - defensive
        ok, detail = False, f"smoke runner error: {exc}"
    # Persist the load result so the router's load-gate can prefer (or demote)
    # E4B for coding/reasoning lanes. Best-effort: never fail the smoke command
    # because the status file couldn't be written.
    try:
        from hermes_cli.jarvis_prime import gemma_load_status as gls

        gls.record_status(variant, ok, detail)
    except Exception:  # pragma: no cover - defensive
        pass
    status = "smoke_tested" if ok else "wired_not_confirmed"
    payload = {"variant": variant, "tag": tag, "status": status, "detail": detail}
    if getattr(args, "json", False):
        _print_json(payload)
    else:
        glyph = "✓" if ok else "·"
        print(f"{glyph} gemma smoke [{tag}]: {status} — {detail}")
    return 0 if ok else 1


def _default_smoke_runner(tag: str) -> tuple[bool, str]:
    """Run a 1-token local completion via ollama. Only reached when the user
    explicitly invokes ``smoke`` — never during import or normal tests."""
    import shutil
    import subprocess

    if shutil.which("ollama") is None:
        return False, "ollama not installed — install https://ollama.com to smoke-test"
    try:
        proc = subprocess.run(
            ["ollama", "run", tag, "Reply with the single word: ready"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        return False, f"smoke call failed: {exc}"
    if proc.returncode == 0 and proc.stdout.strip():
        return True, f"completion ok ({proc.stdout.strip()[:40]!r})"
    return False, (proc.stderr or "no output").strip()[:120]


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


def _cmd_recommend(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime import model_bootstrap as mb

    tier = getattr(args, "tier", None)
    task = getattr(args, "task", None)
    out: dict[str, Any] = {}
    if tier:
        out["tier"] = tier
        out["gemma_by_tier"] = mb.gemma_recommendations(tier)
    if task:
        from hermes_cli import oss_model_brain as ob

        cat = ob.load_oss_catalog()
        out["task"] = task
        out["models"] = [m.id for m in cat.recommend(task)]
    if not tier and not task:
        # Default: show per-tier Gemma recommendations.
        out["gemma_by_tier"] = {
            t: mb.gemma_recommendations(t)
            for t in ("laptop", "desktop", "workstation", "server")
        }
    if getattr(args, "json", False):
        _print_json(out)
        return 0
    print("Gemma 4 — recommendations")
    by_tier = out.get("gemma_by_tier")
    if isinstance(by_tier, dict):
        for t, recs in by_tier.items():
            print(f"  {t:11s}: {', '.join(r['name'] for r in recs) or '(none)'}")
    elif isinstance(by_tier, list):
        print(f"  {tier}: {', '.join(r['name'] for r in by_tier) or '(none)'}")
    if "models" in out:
        print(f"  task {task}: {', '.join(out['models'])}")
    return 0


# ---------------------------------------------------------------------------
# scorecards
# ---------------------------------------------------------------------------


def _cmd_scorecards(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook, model_family

    book = ScorecardBook.load()
    gemma = [c for c in book.scorecards if model_family(c.model) == "gemma4"]
    if getattr(args, "json", False):
        _print_json([c.to_dict() for c in gemma])
        return 0
    if not gemma:
        print("No Gemma scorecards recorded yet.")
        return 0
    print("Gemma 4 — recorded scorecards")
    for c in gemma:
        print(
            f"  {c.model} [{c.task_type}/{c.risk_class}] score={c.score:.2f} "
            f"owner_corr={c.owner_corrections} halluc={c.hallucination_corrections}"
        )
    return 0


# ---------------------------------------------------------------------------
# promote (owner-gated proposal; never auto-applies)
# ---------------------------------------------------------------------------


def _cmd_promote(args: argparse.Namespace) -> int:
    task_class = getattr(args, "task_class", None)
    if not task_class:
        print("usage: hermes models gemma promote --task-class <task> [--dry-run]")
        return 2
    from hermes_cli.jarvis_prime import task_router as tr
    from hermes_cli.jarvis_prime.model_scorecard import (
        ScorecardBook,
        route_promotion_candidates,
    )

    book = ScorecardBook.load()
    assessments = route_promotion_candidates(book, task_class, family="gemma4")
    eligible = [a for a in assessments if a.eligible]
    dry_run = getattr(args, "dry_run", False)

    if not eligible:
        payload = {
            "task_class": task_class,
            "eligible": False,
            "assessments": [a.to_dict() for a in assessments],
            "note": "No Gemma variant has earned promotion for this lane yet.",
        }
        if getattr(args, "json", False):
            _print_json(payload)
        else:
            print(f"No eligible Gemma promotion for {task_class}.")
            for a in assessments:
                print(f"  · {a.rationale()}")
        return 1

    top = eligible[0]
    proposal = _build_promotion_proposal(task_class, top)
    written = False
    if not dry_run:
        written = _append_proposal(proposal)

    payload = {
        "task_class": task_class,
        "eligible": True,
        "candidate": top.candidate,
        "baseline": top.baseline,
        "mean_delta": round(top.mean_delta, 4),
        "samples": top.candidate_samples,
        "latency_delta_ms": top.latency_delta_ms,
        "proposal": proposal,
        "proposal_written": written,
        "dry_run": dry_run,
    }
    if getattr(args, "json", False):
        _print_json(payload)
    else:
        print(f"Gemma promotion proposal for {task_class}:")
        print(f"  {top.rationale()}")
        print(f"  rollback: {proposal['rollback']}")
        if dry_run:
            print("  (dry-run — proposal NOT written; owner approval required to apply)")
        elif written:
            print(f"  proposal queued for owner approval at {_proposals_store_path()}")
            print("  approve via: hermes_cli.jarvis_prime proposals list / approve")
    return 0


def _build_promotion_proposal(task_class: str, assessment: Any) -> dict[str, Any]:
    from hermes_cli.jarvis_prime import task_router as tr
    from hermes_cli.jarvis_prime.self_update import (
        Proposal,
        ProposalEvidence,
        ProposalKind,
    )

    evidence = (
        ProposalEvidence(
            kind="scorecard",
            text=assessment.rationale(),
            confidence=1.0,
        ),
    )
    rollback = (
        f"reversible: `set_task_override('{task_class}', None)` clears the pin "
        f"(or approve a counter-proposal). Route overrides are owner-gated and atomic."
    )
    proposal = Proposal(
        kind=ProposalKind.ROUTING_RULE_UPDATE,
        target_path=str(tr.overrides_path()),
        rationale=(
            f"Scorecards show {assessment.candidate} outperforms the current "
            f"{task_class} default ({assessment.baseline}) by "
            f"{assessment.mean_delta:+.2f} mean score over "
            f"{assessment.candidate_samples} samples, with no correction/"
            f"hallucination regression."
        ),
        diff_intent=(
            f"pin task class '{task_class}' to '{assessment.candidate}' via "
            f"task_router.set_task_override (owner-gated, reversible)"
        ),
        evidence=evidence,
        risk_class="RC2",
    )
    d = proposal.to_dict()
    d["rollback"] = rollback
    d["scorecard"] = assessment.to_dict()
    return d


def _append_proposal(proposal: dict[str, Any]) -> bool:
    path = _proposals_store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(proposal, default=str))
            fh.write("\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "status": _cmd_status,
    "doctor": _cmd_doctor,
    "smoke": _cmd_smoke,
    "recommend": _cmd_recommend,
    "scorecards": _cmd_scorecards,
    "promote": _cmd_promote,
}


def dispatch(args: argparse.Namespace) -> int:
    """Route a parsed ``gemma`` subcommand to its handler. Returns an exit code."""
    sub = getattr(args, "gemma_command", None)
    handler = _HANDLERS.get(sub or "")
    if handler is None:
        print(
            "usage: hermes models gemma "
            "{status,doctor,smoke,recommend,scorecards,promote}"
        )
        return 2
    return handler(args)


__all__ = ["dispatch"]
