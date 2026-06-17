"""Bridge: let MUSE retrieve from the Second Brain knowledge module.

The Second Brain (``second_brain/``) is a Postgres(pgvector)+Neo4j-backed hybrid
retrieval subsystem. This module is the thin, **opt-in** seam that lets the MUSE
runtime pull retrieved-knowledge context from it — *without* making MUSE depend on
its database drivers or a running backend:

* the heavy module is imported **lazily**, and
* a missing module / driver / backend surfaces as a catchable
  :class:`SecondBrainUnavailable` (so the caller falls back to MUSE's own
  retrieval — GraphRAG + evidence + memory + the
  :mod:`hermes_cli.jarvis_prime.fusion_ranker`) instead of crashing.

The actual database connection is a runtime concern configured via the
``SECOND_BRAIN_*`` environment variables (see ``second_brain/.env.example``); this
bridge holds no credentials and starts no service. The ``factory`` seam keeps the
bridge unit-testable with a fake brain — no live database required.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Callable, Optional


class SecondBrainUnavailable(RuntimeError):
    """The Second Brain module, a driver, or its backend isn't usable here.

    Callers should catch this and fall back to MUSE's native retrieval.
    """


@dataclass
class RetrievedContext:
    """A backend-agnostic view of one Second Brain retrieval."""

    text: str
    block_count: int
    source: str = "second_brain"


# A factory builds a ready-to-query brain. The real one is lazy so importing this
# bridge never pulls in second_brain's database stack; tests inject a fake.
BrainFactory = Callable[..., Any]


def _default_factory(*, enable_graph: bool = False) -> Any:
    # Graph defaults off: the vector + document + retrieval layers (Postgres /
    # pgvector) are the retrieval path; Neo4j is optional and heavier.
    from second_brain.knowledge import SecondBrain, load_settings

    return SecondBrain(load_settings(), enable_graph=enable_graph)


def is_available() -> bool:
    """True if the ``second_brain.knowledge`` package can be imported.

    This only checks importability (cheap, driver-free) — it does **not** prove a
    database is reachable. A successful import with no backend still raises
    :class:`SecondBrainUnavailable` at :func:`retrieve` time, by design.
    """

    try:
        return importlib.util.find_spec("second_brain.knowledge") is not None
    except (ImportError, ValueError):
        # find_spec imports the *parent* package to locate the submodule; when
        # second_brain isn't installed that raises ModuleNotFoundError (an
        # ImportError) rather than returning None. The probe must never crash.
        return False


def retrieve(
    query: str,
    *,
    top_k: Optional[int] = None,
    enable_graph: bool = False,
    factory: Optional[BrainFactory] = None,
) -> RetrievedContext:
    """Retrieve fused context for ``query`` from the Second Brain.

    Raises :class:`SecondBrainUnavailable` (never an import/connection error) when
    the module, a driver, or the backend isn't usable, so MUSE can fall back to
    its own retrieval path.
    """

    make = factory or _default_factory
    try:
        brain = make(enable_graph=enable_graph)
    except Exception as exc:  # ImportError (no driver), connection error, etc.
        raise SecondBrainUnavailable(
            f"Second Brain backend not available: {exc}"
        ) from exc

    try:
        payload = brain.retrieve(query, top_k=top_k)
        text = payload.to_prompt() if hasattr(payload, "to_prompt") else str(payload)
        blocks = getattr(payload, "blocks", []) or []
        return RetrievedContext(text=text, block_count=len(blocks))
    except SecondBrainUnavailable:
        raise
    except Exception as exc:
        raise SecondBrainUnavailable(
            f"Second Brain retrieval failed: {exc}"
        ) from exc
    finally:
        close = getattr(brain, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


__all__ = [
    "RetrievedContext",
    "SecondBrainUnavailable",
    "is_available",
    "retrieve",
]
