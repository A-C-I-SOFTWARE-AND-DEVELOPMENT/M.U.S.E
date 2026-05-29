"""HyperAgent-style repo navigation for JARVIS Prime.

A first-class repository navigation layer — *not* another generic agent. It
combines deterministic lexical, path, import, test, and git-history signals to
answer the questions a coding agent must answer before it edits anything:

- *Where does this issue live?* (:class:`IssueLocalizer`)
- *What tests cover this file, and what depends on it?* (:class:`DependencyTracer`)
- *Where exactly should the edit go, and how do I verify it?* (:class:`EditSiteRanker`)

The :class:`Navigator` ties these together and emits a worker packet plus a
decision-ledger record so the orchestrator can dispatch a focused, auditable
edit. No LLM is used for localization; everything here is reproducible.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.navigation.code_map import CodeMap
from hermes_cli.jarvis_prime.navigation.dependency_trace import (
    DependencyTracer,
    TestLink,
)
from hermes_cli.jarvis_prime.navigation.edit_site_ranker import (
    EditSite,
    EditSiteRanker,
)
from hermes_cli.jarvis_prime.navigation.issue_localizer import (
    IssueLocalizer,
    Localization,
)
from hermes_cli.jarvis_prime.navigation.navigator import (
    Navigator,
    NavigationResult,
)
from hermes_cli.jarvis_prime.navigation.repo_index import (
    IndexedFile,
    RepoIndex,
    classify_role,
    detect_language,
)
from hermes_cli.jarvis_prime.navigation.symbol_graph import SymbolGraph

__all__ = [
    "CodeMap",
    "DependencyTracer",
    "TestLink",
    "EditSite",
    "EditSiteRanker",
    "IssueLocalizer",
    "Localization",
    "Navigator",
    "NavigationResult",
    "IndexedFile",
    "RepoIndex",
    "classify_role",
    "detect_language",
    "SymbolGraph",
]
