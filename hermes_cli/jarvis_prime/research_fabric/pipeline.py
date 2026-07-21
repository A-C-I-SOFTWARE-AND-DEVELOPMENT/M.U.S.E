"""End-to-end wiring for the research fabric.

Opens the persistent stores (SQLite index + hash-chained guardrail ledger +
charter book) and assembles the :class:`AutonomyController`. The CLI and tests
use :func:`open_context`; the controller is created without an ``applier`` by
default, so any CLI ``run`` is a safe dry-run unless a caller injects one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger, hermes_home
from hermes_cli.jarvis_prime.self_update import ProposalBook

from .catalog import REQUIRED_DOMAINS, candidate_dicts
from .champion import ChampionStore
from .charter import CharterBook
from .controller import AutonomyController
from .monitor import AlignmentMonitor
from .store import SnapshotStore, open_store
from .validators import RatchetWall


def default_artifacts_dir(repo_root: Path) -> Path:
    return repo_root / "artifacts" / "research_fabric"


def default_db_path(repo_root: Path) -> Path:
    return default_artifacts_dir(repo_root) / "research_fabric.sqlite3"


@dataclass
class FabricContext:
    repo_root: Path
    store: SnapshotStore
    ledger: GuardrailLedger
    champions: ChampionStore
    charters: CharterBook
    proposals: ProposalBook
    monitor: AlignmentMonitor
    controller: AutonomyController

    def close(self) -> None:
        self.store.close()


def open_context(
    repo_root: Path,
    *,
    db_path: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    charter_path: Optional[Path] = None,
    **controller_kwargs: Any,
) -> FabricContext:
    repo_root = Path(repo_root).resolve()
    store = open_store(db_path or default_db_path(repo_root))
    ledger = GuardrailLedger(ledger_path) if ledger_path else GuardrailLedger()
    charters = CharterBook.load(charter_path)
    champions = ChampionStore(store=store, ledger=ledger)
    proposals = ProposalBook()
    monitor = AlignmentMonitor(ledger=ledger, charter_book=charters)
    controller = AutonomyController(
        charter_book=charters,
        champion_store=champions,
        proposal_book=proposals,
        ledger=ledger,
        monitor=monitor,
        ratchet=RatchetWall(),
        **controller_kwargs,
    )
    return FabricContext(
        repo_root=repo_root,
        store=store,
        ledger=ledger,
        champions=champions,
        charters=charters,
        proposals=proposals,
        monitor=monitor,
        controller=controller,
    )


def report_payload(ctx: FabricContext) -> dict[str, Any]:
    champ = ctx.champions.current()
    active = ctx.charters.active()
    chain = ctx.ledger.verify_chain()
    store_chain = ctx.store.verify_chain()
    return {
        "required_domains": list(REQUIRED_DOMAINS),
        "champion": champ.to_dict() if champ else None,
        "active_charter": active.to_dict() if active else None,
        "charters": [c.to_dict() for c in ctx.charters.charters],
        "ledger_chain": chain.to_dict(),
        "store_chain": store_chain.to_dict(),
        "ledger_length": chain.length,
        "inventory": candidate_dicts(),
    }


__all__ = [
    "FabricContext",
    "open_context",
    "report_payload",
    "default_artifacts_dir",
    "default_db_path",
]
