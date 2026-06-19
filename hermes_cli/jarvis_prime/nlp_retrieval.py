"""W4 retrieval grounding for the muse NL compiler.

Deterministically enriches a repo work packet's file scope with candidate
files surfaced by the existing :class:`Navigator`. This is a thin, pure
adapter: it reuses the navigator's multi-signal localization (lexical, path,
symbol, test, git) — *no LLM, no network* — and degrades gracefully when the
navigator is unavailable (e.g. import error, empty repo, build failure).

The contract is **additive only**: grounding contributes *candidate* files,
verification tests and notes. It never narrows the safe per-intent default —
that union lives in the compiler. On any failure this returns a grounding with
``ok=False`` and empty candidates so callers' behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalGrounding:
    """Result of grounding an objective against the repo via the Navigator.

    ``ok`` is ``False`` when navigation was unavailable; in that case the
    candidate/verify tuples are empty and ``notes`` explains why.
    """

    candidate_files: tuple[str, ...] = ()
    verify_with: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    ok: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_files": list(self.candidate_files),
            "verify_with": list(self.verify_with),
            "notes": list(self.notes),
            "ok": self.ok,
        }


def ground_objective(
    objective: str, repo_root: str = ".", *, limit: int = 5
) -> RetrievalGrounding:
    """Ground ``objective`` against ``repo_root`` using the Navigator.

    Deterministic, no LLM, no network. The entire body is wrapped so that any
    failure (import error, navigator build failure, empty repo, …) yields a
    graceful ``ok=False`` grounding rather than propagating an exception.
    """

    try:
        from hermes_cli.jarvis_prime.navigation.navigator import Navigator

        result = Navigator.for_repo(repo_root).navigate(objective, limit=limit)
        packet = result.worker_packet()

        def _as_str_tuple(value: object) -> tuple[str, ...]:
            if isinstance(value, (list, tuple)):
                return tuple(str(v) for v in value)
            return ()

        candidate_files = _as_str_tuple(packet.get("candidate_files"))
        verify_with = _as_str_tuple(packet.get("verify_with"))

        notes: list[str] = []
        method = packet.get("navigation_method")
        if method:
            notes.append(f"navigation method: {method}")
        if candidate_files:
            notes.append(
                "candidate_files from navigator: " + ", ".join(candidate_files)
            )

        return RetrievalGrounding(
            candidate_files=candidate_files,
            verify_with=verify_with,
            notes=tuple(notes),
            ok=True,
        )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        return RetrievalGrounding(
            ok=False, notes=(f"navigation unavailable: {exc!r}",)
        )


__all__ = ["RetrievalGrounding", "ground_objective"]
