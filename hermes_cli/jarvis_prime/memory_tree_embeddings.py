"""Optional dense-embedding retrieval lane for the JARVIS Memory Tree.

Additive and **default-off**. When enabled, :meth:`MemoryTreeStore.search`
blends a cosine-similarity term (over cached node embeddings) into its lexical
score, reusing the holographic plugin's embedding backends so there is exactly
one embedding implementation in the tree. With no configuration the Memory Tree
behaves byte-for-byte as before (pure term-overlap search).

Storage: embeddings live in a rebuildable JSONL **sidecar** next to the tree
(``memory_tree.emb.jsonl``), keyed by node id + a hash of the indexed text, so
the authoritative ``memory_tree.jsonl`` never carries vectors and a model
change simply re-embeds on next access. There is no FAISS/ANN index — the tree
is small and a brute-force cosine over active nodes is cheap, mirroring the
holographic retriever's candidate-set cosine.

Enable via environment (rollback-friendly, like ``HERMES_MEMORY_LAYERS``)::

    HERMES_MEMORY_TREE_EMBEDDINGS=1          # turn the lane on
    HERMES_MEMORY_TREE_EMBED_WEIGHT=0.35     # blend weight (default 0.35)
    HERMES_MEMORY_TREE_EMBED_BACKEND=auto    # auto | openai | sentence-transformers
    HERMES_MEMORY_TREE_EMBED_MODEL=...        # backend-specific default if omitted
    HERMES_MEMORY_TREE_EMBED_BASE_URL=...     # OpenAI-compatible endpoint (openai backend)
    HERMES_MEMORY_TREE_EMBED_API_KEY_ENV=OPENAI_API_KEY
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional

# Default blend weight when the lane is enabled without an explicit weight.
DEFAULT_EMBED_WEIGHT = 0.35


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def resolve_embedding_config() -> dict[str, Any]:
    """Resolve the Memory Tree embedding config from the environment.

    Returns a dict with a top-level ``enabled``/``weight`` plus an
    ``embeddings`` sub-block shaped exactly like the one the holographic
    :func:`make_backend` factory consumes, so we reuse that factory verbatim.
    """

    enabled = _env_flag("HERMES_MEMORY_TREE_EMBEDDINGS", False)
    weight = _env_float("HERMES_MEMORY_TREE_EMBED_WEIGHT", DEFAULT_EMBED_WEIGHT)
    backend = (os.environ.get("HERMES_MEMORY_TREE_EMBED_BACKEND") or "auto").strip()
    model = os.environ.get("HERMES_MEMORY_TREE_EMBED_MODEL") or None
    base_url = os.environ.get("HERMES_MEMORY_TREE_EMBED_BASE_URL") or None
    api_key_env = (
        os.environ.get("HERMES_MEMORY_TREE_EMBED_API_KEY_ENV") or "OPENAI_API_KEY"
    )
    return {
        "enabled": enabled,
        "weight": weight,
        "embeddings": {
            # ``make_backend`` only builds a backend when this is truthy; the
            # store forces it True once it has decided to enable the lane.
            "enabled": enabled,
            "backend": backend,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
        },
    }


def indexed_text(node: Any) -> str:
    """The text a node contributes to retrieval — matches the lexical ``hay``.

    Mirrors ``MemoryTreeStore.search`` so the dense lane indexes exactly what
    the term-overlap lane already indexes (title + summary + text + tags).
    """

    tags = " ".join(getattr(node, "tags", ()) or ())
    parts = (
        getattr(node, "title", "") or "",
        getattr(node, "summary", "") or "",
        getattr(node, "text", "") or "",
        tags,
    )
    return " ".join(p for p in parts if p).strip()


def _text_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def build_backend(config: dict[str, Any]) -> Optional[Any]:
    """Build the holographic embedding backend for ``config`` (or ``None``).

    Reuses ``plugins.memory.holographic.embeddings.make_backend`` so there is a
    single embedding-backend implementation shared with the holographic store.
    Imported lazily: the heavy plugin import only happens when the lane is on.
    """

    try:
        from plugins.memory.holographic.embeddings import make_backend
    except Exception:
        return None
    return make_backend(config)


class MemoryTreeEmbeddingIndex:
    """Rebuildable sidecar of node embeddings + brute-force cosine similarity."""

    def __init__(self, backend: Any, path: Path) -> None:
        self.backend = backend
        self.path = Path(path)
        # node_id -> {"hash", "model", "dim", "vec"}
        self._cache: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._query_cache: tuple[str, "list[float] | None"] | None = None

    @property
    def model_id(self) -> str:
        name = getattr(self.backend, "name", "backend")
        model = getattr(self.backend, "model_name", "")
        return f"{name}:{model}"

    # -- persistence --------------------------------------------------------

    def load(self) -> "MemoryTreeEmbeddingIndex":
        if not self.path.exists():
            return self
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        rec = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    nid = rec.get("id")
                    if nid:
                        self._cache[nid] = {
                            "hash": rec.get("hash", ""),
                            "model": rec.get("model", ""),
                            "dim": rec.get("dim", 0),
                            "vec": rec.get("vec") or [],
                        }
        except OSError:
            pass
        return self

    def flush(self) -> None:
        """Persist the sidecar if it changed since the last flush."""

        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for nid, rec in self._cache.items():
            lines.append(
                json.dumps(
                    {
                        "id": nid,
                        "hash": rec.get("hash", ""),
                        "model": rec.get("model", ""),
                        "dim": rec.get("dim", 0),
                        "vec": rec.get("vec") or [],
                    },
                    sort_keys=True,
                )
            )
        payload = "\n".join(lines) + ("\n" if lines else "")
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".memtree-emb-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self._dirty = False

    # -- embedding ----------------------------------------------------------

    def embed_query(self, query: str) -> "list[float] | None":
        """Embed the query once per query string (memoized)."""

        if not query:
            return None
        if self._query_cache is not None and self._query_cache[0] == query:
            return self._query_cache[1]
        vec: "list[float] | None"
        try:
            vec = self.backend.embed(query)
        except Exception:
            vec = None
        self._query_cache = (query, vec)
        return vec

    def vector_for(self, node: Any) -> "list[float] | None":
        """Return the node's cached vector, embedding + caching on first miss.

        A model or text change invalidates the cache entry (hash/model keyed),
        so stale vectors never silently score against a new backbone.
        """

        text = indexed_text(node)
        if not text:
            return None
        h = _text_hash(text)
        cached = self._cache.get(node.id)
        if (
            cached
            and cached.get("hash") == h
            and cached.get("model") == self.model_id
            and cached.get("vec")
        ):
            return cached["vec"]
        try:
            vec = self.backend.embed(text)
        except Exception:
            vec = None
        if not vec:
            # Keep any prior vector rather than dropping it on a transient
            # embed failure; return None so the caller stays neutral.
            return cached.get("vec") if cached else None
        self._cache[node.id] = {
            "hash": h,
            "model": self.model_id,
            "dim": len(vec),
            "vec": list(vec),
        }
        self._dirty = True
        return self._cache[node.id]["vec"]

    def similarity(self, q_vec: "list[float] | None", node: Any) -> float:
        """Cosine similarity (shifted to ``[0, 1]``) between query and node.

        Returns a neutral ``0.5`` whenever the query has no vector, the node
        cannot be embedded, or dimensions mismatch — mirroring the holographic
        retriever so a missing dense signal never distorts ranking.
        """

        if not q_vec:
            return 0.5
        v = self.vector_for(node)
        if not v or len(v) != len(q_vec):
            return 0.5
        try:
            from plugins.memory.holographic.embeddings import cosine
        except Exception:
            return 0.5
        return (cosine(q_vec, v) + 1.0) / 2.0

    def reindex(self, nodes: Iterable[Any]) -> int:
        """Embed every node (recomputing changed/new ones) and persist once."""

        count = 0
        for node in nodes:
            if self.vector_for(node) is not None:
                count += 1
        self.flush()
        return count


def build_index(config: dict[str, Any], sidecar_path: Path) -> Optional[MemoryTreeEmbeddingIndex]:
    """Build a loaded embedding index for ``config``, or ``None`` if no backend.

    ``config`` must already have ``config["embeddings"]["enabled"]`` set truthy
    by the caller (the store decides enablement); this only wires the backend.
    """

    backend = build_backend(config)
    if backend is None:
        return None
    return MemoryTreeEmbeddingIndex(backend, sidecar_path).load()
