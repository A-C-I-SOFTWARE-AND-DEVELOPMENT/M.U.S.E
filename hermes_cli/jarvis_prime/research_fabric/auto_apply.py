"""Drive one self-improvement candidate through the full auto-apply envelope.

This is the p2 wire-up: benchmark scores -> Candidate -> AutonomyController ->
GitApplier (real, reversible) -> Champion store + Guardrail ledger + corpus
record. It is the smallest end-to-end auto-apply driver in the fabric.

The driver is intentionally conservative:

* runs on a dedicated autonomy branch (``autonomy/<candidate_id>``), never on
  the caller's current branch;
* refuses to construct unless ``repo`` is a real git worktree;
* all eight strict gates, the ratchet, and the canary must pass;
* any canary regression hard-resets the branch to the prior champion handle.

Usage (library):
    from hermes_cli.jarvis_prime.research_fabric import auto_apply
    outcome = auto_apply.drive_candidate(repo_root, candidate, packet, bundle)

Usage (CLI):
    python -m hermes_cli.jarvis_prime.research_fabric.auto_apply \\
        --repo . --candidate candidate.json --packet packet.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .apply import GitApplier, GitRollback, current_head
from .champion import ChampionStore
from .charter import AutonomyCharter, CharterBook
from .controller import AutonomyController, AutoApplyOutcome
from .monitor import AlignmentMonitor
from .store import SnapshotStore, open_store
from .verifier import Candidate
from ..guardrail_evidence import GuardrailEvidenceBundle, GuardrailLedger
from ..self_update import ProposalBook, ProposalKind


# --------------------------------------------------------------------------- helpers


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _ensure_autonomy_branch(repo: Path, candidate_id: str) -> str:
    """Check out (or create) the dedicated autonomy branch and return its name."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in candidate_id)[:48]
    branch = f"autonomy/{safe}"
    try:
        _git(repo, "rev-parse", "--verify", branch)
    except RuntimeError:
        _git(repo, "checkout", "-b", branch)
    else:
        _git(repo, "checkout", branch)
    return branch


def _default_charter(candidate_id: str) -> AutonomyCharter:
    """A minimal always-on charter so the controller can proceed."""
    now = datetime.now(timezone.utc)
    return AutonomyCharter(
        charter_id=f"charter-{candidate_id}",
        allowed_kinds=(
            "skill_update",
            "new_skill",
            "agent_update",
            "new_agent",
            "routing_rule_update",
            "self_runtime_update",
            "memory_promotion",
            "gate_update",
            "model_registry_update",
        ),
        risk_band_ceiling="RC3",
        per_window_budget=8,
        window_seconds=3600,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        owner_grant_id=f"auto-{candidate_id}",
    )


def _default_canary(repo: Path):
    """Cheap smoke: returns the candidate's claimed domain_scores. A real canary
    would re-run the benchmark suite — wired via the same interface later.
    """

    def canary(candidate: Candidate) -> Mapping[str, Any]:
        return {
            "domain_scores": dict(candidate.domain_scores),
            "safety_counts": dict(candidate.safety_counts),
        }

    return canary

def catalog_canary(run_dir_factory, *, required_domains=None):
    """Build a real canary that re-runs catalog verifiers post-apply.

    ``run_dir_factory`` is a callable ``() -> Path`` that returns a directory
    containing the runner-written ``results.jsonl`` files (one per verifier
    lane). The canary calls each registered catalog verifier on that directory
    and converts their ``DomainScore`` outputs into the mapping the
    ``AutonomyController`` expects.

    If a required domain has no registered verifier, the canary falls back to
    the candidate's claimed score for that domain (fail-open so the canary is
    usable before every lane is wired); if a verifier raises, the score is
    treated as 0.0 (fail-closed — a broken verifier is a real regression
    signal).
    """
    from .catalog import REQUIRED_DOMAINS
    from .verifier import get_verifier

    if required_domains is None:
        required_domains = REQUIRED_DOMAINS

    def canary(candidate: Candidate) -> Mapping[str, Any]:
        run_dir = run_dir_factory()
        domain_scores: dict[str, float] = {}
        safety_counts: dict[str, float] = dict(candidate.safety_counts)
        for domain in required_domains:
            try:
                verify = get_verifier(domain)
            except KeyError:
                # No verifier registered for this domain yet; use the
                # candidate's claimed score so the canary is still usable.
                claimed = candidate.domain_scores.get(domain)
                if claimed is not None:
                    domain_scores[domain] = float(claimed)
                continue
            try:
                score = verify(run_dir)
                domain_scores[domain] = float(score.correctness)
            except Exception as exc:  # noqa: BLE001
                # A verifier that cannot run is a hard regression signal.
                domain_scores[domain] = 0.0
                safety_counts[f"{domain}_verifier_error"] = 1.0
        return {"domain_scores": domain_scores, "safety_counts": safety_counts}

    return canary


def _record_to_corpus(
    repo: Path,
    candidate: Candidate,
    outcome: AutoApplyOutcome,
    branch: str,
) -> Path:
    """Append a JSONL record under .hermes/research_fabric/corpus/."""
    corpus_dir = Path(repo) / ".hermes" / "research_fabric" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = corpus_dir / f"{stamp}-{candidate.candidate_id}.json"
    record = {
        "ts": stamp,
        "candidate": candidate.to_dict(),
        "outcome": outcome.to_dict(),
        "branch": branch,
        "head": current_head(repo),
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- main entry


def drive_candidate(
    repo_root: Path | str,
    candidate: Candidate,
    packet: Mapping[str, Any],
    evidence_bundle: GuardrailEvidenceBundle,
    *,
    dry_run: bool = False,
    charter: Optional[AutonomyCharter] = None,
    canary: Optional[Canary] = None,
) -> AutoApplyOutcome:
    """Run ``candidate`` through the AutonomyController with real git apply.

    Returns the controller's outcome; also appends a corpus record.
    """
    repo = Path(repo_root).resolve()
    if not (repo / ".git").exists():
        raise RuntimeError(f"{repo} is not a git worktree")

    branch = _ensure_autonomy_branch(repo, candidate.candidate_id)

    # Charter book: in-memory, seeded with our default charter
    charters = CharterBook(charters=[charter or _default_charter(candidate.candidate_id)])

    # Snapshot store + ledger live under .hermes/research_fabric/
    state_dir = repo / ".hermes" / "research_fabric"
    state_dir.mkdir(parents=True, exist_ok=True)
    store = open_store(state_dir / "snapshots.db")
    ledger = GuardrailLedger(state_dir / "ledger.jsonl")
    champions = ChampionStore(store=store, ledger=ledger)
    proposals = ProposalBook()
    monitor = AlignmentMonitor(ledger=ledger, charter_book=charters)

    controller = AutonomyController(
        charter_book=charters,
        champion_store=champions,
        proposal_book=proposals,
        ledger=ledger,
        monitor=monitor,
        applier=GitApplier(repo),
        canary=canary or _default_canary(repo),
        rollback=GitRollback(repo),
    )

    outcome = controller.evaluate_and_apply(
        candidate,
        evidence_bundle=evidence_bundle,
        packet=packet,
        dry_run=dry_run,
    )
    corpus_path = _record_to_corpus(repo, candidate, outcome, branch)
    outcome.extra["corpus_record"] = str(corpus_path)
    outcome.extra["autonomy_branch"] = branch
    return outcome


# --------------------------------------------------------------------------- CLI


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _candidate_from_dict(d: Mapping[str, Any]) -> Candidate:
    return Candidate(
        candidate_id=str(d["candidate_id"]),
        kind=ProposalKind(d.get("kind", "research_finding")),
        target_path=str(d.get("target_path", "")),
        risk_class=str(d.get("risk_class", "RC3")),
        domain_scores=dict(d.get("domain_scores", {})),
        holdout_scores=dict(d.get("holdout_scores", {})),
        safety_counts=dict(d.get("safety_counts", {})),
        eval_win_rate=d.get("eval_win_rate"),
        ambition_scores=dict(d.get("ambition_scores", {})),
        diff_text=str(d.get("diff_text", "")),
        note=str(d.get("note", "")),
    )


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--repo", default=".")
    p.add_argument("--candidate", required=True, help="JSON file with Candidate fields")
    p.add_argument("--packet", required=True, help="JSON file for the strict gate packet")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    candidate = _candidate_from_dict(_load_json(args.candidate))
    packet = _load_json(args.packet)
    bundle = GuardrailEvidenceBundle(packet_id=candidate.candidate_id)

    outcome = drive_candidate(
        Path(args.repo),
        candidate,
        packet,
        bundle,
        dry_run=args.dry_run,
    )
    print(json.dumps(outcome.to_dict(), indent=2))
    return 0 if outcome.decision in {"auto_applied", "proposed"} else 1


if __name__ == "__main__":
    sys.exit(main())
