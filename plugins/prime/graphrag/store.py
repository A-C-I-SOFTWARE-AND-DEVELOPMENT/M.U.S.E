"""GraphStore — durable, local-first persistence for the knowledge graph.

The graph is an additive *cache* built from authoritative subsystems (repo,
docs, Research Vault, Memory Tree). It is therefore safe to delete
and rebuild at any time — deleting ``~/.hermes/prime/graph/graph.json``
is a complete rollback.

Persistence mirrors the Memory Tree / Research Vault stores: a single JSON
document written atomically (temp file + ``os.replace``) with owner-only
permissions where the platform supports it. No network, stdlib only.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from plugins.prime.graphrag.graph import KnowledgeGraph


def _hermes_home() -> Path:
    """Resolve ``$HERMES_HOME`` (honoured lazily so tests can point it at a
    tmpdir) falling back to ``~/.hermes``.
    """

    return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def default_graph_path() -> Path:
    return _hermes_home() / "prime" / "graph" / "graph.json"


class GraphStore:
    """Loads/saves a :class:`KnowledgeGraph` to a JSON document."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_graph_path()
        self.load_diagnostics: list[str] = []

    # -- io -----------------------------------------------------------------

    def load(self) -> KnowledgeGraph:
        if not self.path.exists():
            return KnowledgeGraph()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.load_diagnostics.append(f"load failed: {exc}")
            return KnowledgeGraph()
        return KnowledgeGraph.from_dict(data)

    def save(self, graph: KnowledgeGraph) -> Path:
        target = self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(graph.to_dict(), sort_keys=True, indent=0)
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=".graph-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    def exists(self) -> bool:
        return self.path.exists()
