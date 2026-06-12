"""Optional, owner-gated ingestion of external MCP search sources into memory.

This wires the connected MCP **search** tools (Gmail, Google Drive, Notion,
Slack, PubMed, ICD-10, Era, …) into the holographic memory store as
provenanced, sensitivity-tagged facts — the blueprint's "source-labeled
retrieval layer over real documents".

Design principles:

* **Opt-in per source.** Every source profile defaults to disabled; nothing is
  ever auto-ingested. The owner runs ``jarvis_prime memory ingest`` explicitly.
* **Dry-run first.** ``ingest`` previews exactly what would be written; only
  ``apply=True`` (driven by an owner confirmation in the CLI) writes.
* **Provenance + redaction.** Each item carries its source, source_uri, trust,
  and sensitivity. Personal sources are run through
  :func:`agent.redact.redact_sensitive_text` before storage.
* **No silent overwrite.** Writes go through the holographic store, which
  deduplicates by content (a re-ingest returns the existing fact id).
* **Decoupled from MCP plumbing.** The actual tool call is an injectable
  callable so the logic is testable without live servers; the default caller
  resolves a live MCP tool by name through the tool registry.

Importance for stored facts is derived from the source trust so the longevity
layer (consolidation / tiered decay) treats owner/primary sources as durable
and community sources as more disposable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Trust → importance prior (mirrors memory_tree.SourceTrust weights).
_TRUST_WEIGHT = {
    "owner": 1.0,
    "primary": 0.95,
    "official_doc": 0.85,
    "reputable": 0.65,
    "community": 0.45,
    "unverified": 0.3,
}


@dataclass(frozen=True)
class MemorySourceProfile:
    """How to pull from one external search source and where it lands."""

    name: str
    tool: str                       # MCP tool base name, resolved by suffix
    query_arg: str = "query"
    limit_arg: Optional[str] = "limit"
    sensitivity: str = "public"     # personal | domain | public
    trust: str = "reputable"        # SourceTrust value name
    category: str = "general"       # holographic store category
    extra_args: dict = field(default_factory=dict)

    @property
    def importance(self) -> float:
        return _TRUST_WEIGHT.get(self.trust, 0.5)


# Built-in registry for the sources commonly connected this session. Server
# UUID prefixes are intentionally absent — the default caller resolves the live
# tool by matching the base name suffix, so the same profile works regardless
# of which MCP server instance provides it.
REGISTRY: dict[str, MemorySourceProfile] = {
    "gmail": MemorySourceProfile(
        "gmail", "search_threads", sensitivity="personal", trust="owner", category="personal"
    ),
    "gdrive": MemorySourceProfile(
        "gdrive", "search_files", sensitivity="personal", trust="owner", category="personal"
    ),
    "notion": MemorySourceProfile(
        "notion", "notion-search", sensitivity="personal", trust="owner", category="personal"
    ),
    "slack": MemorySourceProfile(
        "slack", "slack_search_public", sensitivity="personal", trust="reputable", category="personal"
    ),
    "pubmed": MemorySourceProfile(
        "pubmed", "search_articles", sensitivity="domain", trust="primary", category="research"
    ),
    "icd10": MemorySourceProfile(
        "icd10", "search_codes", sensitivity="domain", trust="official_doc", category="reference",
        extra_args={"code_type": "diagnosis"},
    ),
    "era": MemorySourceProfile(
        "era", "knowledge__recall_history", sensitivity="personal", trust="owner", category="personal"
    ),
}

# Keys commonly used by MCP search tools to wrap their result list / fields.
_LIST_KEYS = ("results", "items", "articles", "threads", "files", "messages",
              "matches", "data", "documents", "hits", "records", "codes")
_CONTENT_KEYS = ("snippet", "summary", "abstract", "text", "body", "content",
                 "description", "preview", "value", "message")
_TITLE_KEYS = ("title", "name", "subject", "heading", "label", "description")
_URI_KEYS = ("url", "uri", "link", "permalink", "source_url", "web_url", "href", "id")


@dataclass
class IngestCandidate:
    content: str
    title: str
    source_uri: str
    tags: str
    importance: float

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "title": self.title,
            "source_uri": self.source_uri,
            "tags": self.tags,
            "importance": round(self.importance, 3),
        }


@dataclass
class IngestReport:
    source: str
    query: str
    dry_run: bool
    fetched: int = 0
    candidates: list[IngestCandidate] = field(default_factory=list)
    written: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "query": self.query,
            "dry_run": self.dry_run,
            "fetched": self.fetched,
            "candidates": [c.to_dict() for c in self.candidates],
            "written": self.written,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Source profile resolution + config gating
# ---------------------------------------------------------------------------

def available_sources() -> list[str]:
    return sorted(REGISTRY)


def source_enabled(name: str, config: Optional[dict]) -> bool:
    """A source is enabled only if config opts it in. Default: disabled."""
    cfg = (config or {}).get(name) or {}
    return bool(cfg.get("enabled", False))


# ---------------------------------------------------------------------------
# Result extraction (generic across heterogeneous MCP search shapes)
# ---------------------------------------------------------------------------

def _coerce_result(raw: Any) -> Any:
    """MCP tools (and the registry dispatch) often return a JSON string."""
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


def _items_from(result: Any) -> list[dict]:
    result = _coerce_result(result)
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)] or [
            {"text": str(r)} for r in result
        ]
    if isinstance(result, dict):
        for key in _LIST_KEYS:
            val = result.get(key)
            if isinstance(val, list):
                return [r if isinstance(r, dict) else {"text": str(r)} for r in val]
        # A single-object result — treat it as one item.
        return [result]
    if isinstance(result, str) and result.strip():
        return [{"text": result.strip()}]
    return []


def _first(item: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v not in (None, "", [], {}):
            return str(v)
    return ""


def _item_to_candidate(profile: MemorySourceProfile, item: dict) -> Optional[IngestCandidate]:
    title = _first(item, _TITLE_KEYS)
    body = _first(item, _CONTENT_KEYS)
    text = " — ".join(p for p in (title, body) if p).strip()
    if not text:
        # Last resort: serialize the item compactly so nothing is silently lost.
        text = json.dumps(item, ensure_ascii=False)[:500]
    if not text.strip():
        return None
    uri = _first(item, _URI_KEYS) or f"mcp://{profile.name}"

    if profile.sensitivity == "personal":
        from agent.redact import redact_sensitive_text

        text = redact_sensitive_text(text, force=True)
        title = redact_sensitive_text(title, force=True) if title else title

    safe_uri = uri.replace(",", "%2C")
    tags = ",".join([
        f"source:{profile.name}",
        f"kind:{profile.sensitivity}",
        f"trust:{profile.trust}",
        f"uri:{safe_uri}",
    ])
    return IngestCandidate(
        content=text,
        title=title or profile.name,
        source_uri=uri,
        tags=tags,
        importance=profile.importance,
    )


# ---------------------------------------------------------------------------
# Default MCP tool caller (best-effort; tests inject a fake)
# ---------------------------------------------------------------------------

def _default_tool_caller(tool_name: str, args: dict) -> Any:
    """Resolve a registered MCP tool by name suffix and dispatch it.

    MCP tools are registered into ``tools.registry`` with server-prefixed,
    sanitized names. We match the first registered tool whose name ends with
    the profile's base tool name. Raises LookupError when nothing matches
    (e.g. the relevant MCP server isn't connected in this context).
    """
    from tools.registry import registry

    candidates = [
        n for n in registry.get_all_tool_names()
        if n == tool_name or n.endswith(tool_name) or n.endswith("_" + tool_name)
    ]
    if not candidates:
        raise LookupError(
            f"no connected MCP tool matches {tool_name!r} "
            f"(is the source's MCP server connected?)"
        )
    # Prefer the shortest match (closest to the bare tool name).
    name = min(candidates, key=len)
    return registry.dispatch(name, args)


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def ingest(
    source: str,
    query: str,
    *,
    limit: int = 10,
    apply: bool = False,
    config: Optional[dict] = None,
    tool_caller: Optional[Callable[[str, dict], Any]] = None,
    store: Any = None,
) -> IngestReport:
    """Search an external MCP source and (optionally) write the results to memory.

    ``apply=False`` (default) previews candidates without writing. ``apply=True``
    writes them to the holographic ``store`` as provenanced facts — the CLI only
    sets this after an explicit owner confirmation.
    """
    profile = REGISTRY.get(source)
    report = IngestReport(source=source, query=query, dry_run=not apply)
    if profile is None:
        report.errors.append(f"unknown source: {source!r}")
        return report
    if not source_enabled(source, config):
        report.errors.append(
            f"source {source!r} is disabled — enable it under "
            f"jarvis_prime.memory_sources.{source}.enabled"
        )
        return report

    caller = tool_caller or _default_tool_caller
    args = dict(profile.extra_args)
    args[profile.query_arg] = query
    if profile.limit_arg:
        args[profile.limit_arg] = limit

    try:
        raw = caller(profile.tool, args)
    except Exception as exc:
        report.errors.append(f"tool call failed: {exc}")
        return report

    items = _items_from(raw)[: max(1, limit)]
    report.fetched = len(items)

    seen: set[str] = set()
    for item in items:
        cand = _item_to_candidate(profile, item)
        if cand is None:
            continue
        if cand.content in seen:  # de-dup within the batch
            continue
        seen.add(cand.content)
        report.candidates.append(cand)

    if apply:
        if store is None:
            report.errors.append("apply=True requires a memory store")
            return report
        for cand in report.candidates:
            try:
                store.add_fact(
                    cand.content,
                    category=profile.category,
                    tags=cand.tags,
                    importance=cand.importance,
                )
                report.written += 1
            except Exception as exc:  # never let one bad item abort the batch
                report.errors.append(f"write failed: {exc}")

    return report
