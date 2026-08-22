"""Deterministic repo navigation.

Combines lexical, path, import, test, and git-history signals to answer the
questions that have to be answered before an edit is made:

- *Where does this issue live?* (:class:`IssueLocalizer`)
- *What tests cover this file, and what depends on it?* (:class:`DependencyTracer`)
- *Where exactly should the edit go, and how do I verify it?* (:class:`EditSiteRanker`)

The :class:`Navigator` ties these together and emits a focused packet — the
candidate files, the tests to run and the blast radius. No LLM is used for
localization, so every ranking is reproducible and explainable.
"""

from __future__ import annotations

from plugins.prime.navigation.code_map import CodeMap
from plugins.prime.navigation.dependency_trace import (
    DependencyTracer,
    TestLink,
)
from plugins.prime.navigation.edit_site_ranker import (
    EditSite,
    EditSiteRanker,
)
from plugins.prime.navigation.issue_localizer import (
    IssueLocalizer,
    Localization,
)
from plugins.prime.navigation.navigator import (
    Navigator,
    NavigationResult,
)
from plugins.prime.navigation.repo_index import (
    IndexedFile,
    RepoIndex,
    classify_role,
    detect_language,
)
from plugins.prime.navigation.symbol_graph import SymbolGraph

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
