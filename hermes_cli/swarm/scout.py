"""Scout Helper — parallel prefetch for swarm niches before specialists decode.

Runs gatherers in parallel and posts fenced packets to the Swarm Blackboard
(+ returns a context blob for TokenJuice / GrainAgentSpec.context injection).
Specialists should prefer SCOUT/* packets over re-searching.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
import json
import re
import subprocess
import threading

from hermes_cli.swarm.grain import SwarmPlan, now_iso

__all__ = [
    "ScoutPacket",
    "ScoutResult",
    "prefetch_for_plan",
    "prefetch_for_queries",
    "inject_scout_into_specs",
]


GatherFn = Callable[[str, Path], str]


@dataclass
class ScoutPacket:
    lane: str  # code | docs | web | memory | tools
    query: str
    grain_id: str
    text: str
    created_at: str = field(default_factory=now_iso)

    def fence(self) -> str:
        body = (self.text or "").strip() or "(no hits)"
        return (
            f"### SCOUT/{self.lane} — grain `{self.grain_id}`\n"
            f"query: {self.query}\n\n{body}\n"
        )


@dataclass
class ScoutResult:
    packets: list[ScoutPacket] = field(default_factory=list)
    tools_json: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def context_blob(self, *, grain_id: Optional[str] = None, limit: int = 12) -> str:
        """Render packets for injection into a grain's context."""
        selected = [
            p for p in self.packets
            if grain_id is None or p.grain_id in (grain_id, "shared", "*")
        ][:limit]
        if not selected and self.packets:
            selected = self.packets[:limit]
        parts = ["## Scout prefetch (prefer these over re-searching)\n"]
        for p in selected:
            parts.append(p.fence())
        if self.tools_json:
            parts.append(
                "### SCOUT/tools\n```json\n"
                + json.dumps(self.tools_json, indent=2)[:4000]
                + "\n```\n"
            )
        return "\n".join(parts)


def _rg_codebase(query: str, repo: Path) -> str:
    """Fast local codebase search via ripgrep (best-effort)."""
    q = re.sub(r"^(repo:\s*)", "", query, flags=re.I).strip()
    if not q:
        return ""
    # Extract a few meaningful tokens
    tokens = [t for t in re.findall(r"[A-Za-z0-9_-]{3,}", q) if t.lower() not in {
        "the", "and", "for", "with", "from", "repo", "docs"
    }][:4]
    if not tokens:
        tokens = [q[:40]]
    pattern = "|".join(re.escape(t) for t in tokens)
    try:
        proc = subprocess.run(
            [
                "rg", "-n", "-i", "--max-count", "8", "--glob", "!**/node_modules/**",
                "--glob", "!**/.git/**", "--glob", "!**/dist/**", pattern, str(repo),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        out = (proc.stdout or "").strip()
        if out:
            lines = out.splitlines()[:40]
            return "\n".join(lines)
        # Fallback: PowerShell Select-String is slow; try python walk of a few files
        return _python_grep(tokens, repo)
    except FileNotFoundError:
        return _python_grep(tokens, repo)
    except Exception as exc:
        return f"(code scout error: {exc})"


def _python_grep(tokens: Sequence[str], repo: Path) -> str:
    hits: list[str] = []
    exts = {".py", ".ts", ".tsx", ".js", ".md", ".yaml", ".yml", ".json"}
    skip = {"node_modules", ".git", "dist", "__pycache__", ".venv", "venv"}
    pat = re.compile("|".join(re.escape(t) for t in tokens), re.I)
    count_files = 0
    for path in repo.rglob("*"):
        if count_files > 400 or len(hits) >= 30:
            break
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        if any(part in skip for part in path.parts):
            continue
        count_files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                rel = path.relative_to(repo)
                hits.append(f"{rel}:{i}:{line.strip()[:160]}")
                if len(hits) >= 30:
                    break
    return "\n".join(hits) if hits else "(no code hits)"


def _docs_stub(query: str, repo: Path) -> str:
    """Search local docs/ markdown lightly."""
    q = re.sub(r"^(docs:\s*)", "", query, flags=re.I).strip()
    tokens = re.findall(r"[A-Za-z0-9_-]{3,}", q)[:4]
    docs_roots = [repo / "docs", repo / "README.md"]
    hits: list[str] = []
    pat = re.compile("|".join(re.escape(t) for t in tokens), re.I) if tokens else None
    for root in docs_roots:
        if root.is_file() and root.suffix == ".md":
            files = [root]
        elif root.is_dir():
            files = list(root.rglob("*.md"))[:80]
        else:
            continue
        for path in files:
            if len(hits) >= 20:
                break
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if pat and not pat.search(text[:8000]):
                continue
            # first matching line or title
            title = path.stem
            for line in text.splitlines()[:40]:
                if pat and pat.search(line):
                    hits.append(f"{path.name}: {line.strip()[:160]}")
                    break
            else:
                hits.append(f"{path.name}: (matched file) — {title}")
    return "\n".join(hits) if hits else "(no local docs hits)"


def _web_stub(query: str, _repo: Path) -> str:
    """Best-effort web stub — avoid network in unit tests; real hook optional."""
    q = re.sub(r"^(web:\s*)", "", query, flags=re.I).strip()
    # Optional live search if HERMES web helper exists
    try:
        from hermes_cli.jarvis_prime.niches import loader as _  # noqa: F401
    except Exception:
        pass
    return (
        f"(web scout deferred — query recorded: {q!r}. "
        "Specialist may use web tools only on Scout miss.)"
    )


def _memory_stub(query: str, _repo: Path) -> str:
    return f"(memory scout: no provider attached for query {query!r})"


def _tools_warm(toolsets: Sequence[str]) -> dict[str, Any]:
    """Warm / describe toolsets available to niches."""
    return {
        "toolsets": list(toolsets),
        "guidance": (
            "Prefer filesystem + codebase tools for repo work. "
            "Use web only if SCOUT/code and SCOUT/docs miss."
        ),
        "warmed_at": now_iso(),
    }


def prefetch_for_queries(
    queries: Sequence[tuple[str, str]],
    repo: Path,
    *,
    gatherers: Optional[dict[str, GatherFn]] = None,
    max_workers: int = 8,
) -> ScoutResult:
    """Run parallel gatherers for (grain_id, query) pairs.

    Lane is inferred from query prefix: ``repo:``→code, ``docs:``→docs,
    ``web:``→web, else code+docs.
    """
    import time

    t0 = time.time()
    gmap = {
        "code": _rg_codebase,
        "docs": _docs_stub,
        "web": _web_stub,
        "memory": _memory_stub,
    }
    if gatherers:
        gmap.update(gatherers)

    jobs: list[tuple[str, str, str]] = []  # lane, grain_id, query
    for grain_id, query in queries:
        q = (query or "").strip()
        if not q:
            continue
        low = q.lower()
        if low.startswith("repo:"):
            jobs.append(("code", grain_id, q))
        elif low.startswith("docs:"):
            jobs.append(("docs", grain_id, q))
        elif low.startswith("web:"):
            jobs.append(("web", grain_id, q))
        else:
            jobs.append(("code", grain_id, f"repo: {q}"))
            jobs.append(("docs", grain_id, f"docs: {q}"))

    packets: list[ScoutPacket] = []
    lock = threading.Lock()

    def _run(lane: str, grain_id: str, query: str) -> ScoutPacket:
        fn = gmap.get(lane, _rg_codebase)
        try:
            text = fn(query, repo) or ""
        except Exception as exc:
            text = f"(scout {lane} failed: {exc})"
        return ScoutPacket(lane=lane, query=query, grain_id=grain_id, text=text)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_run, *job) for job in jobs]
        for fut in as_completed(futs):
            pkt = fut.result()
            with lock:
                packets.append(pkt)

    packets.sort(key=lambda p: (p.grain_id, p.lane, p.query))
    return ScoutResult(
        packets=packets,
        tools_json=_tools_warm(("filesystem", "codebase", "web")),
        elapsed_ms=(time.time() - t0) * 1000,
    )


def prefetch_for_plan(
    plan: SwarmPlan,
    repo: Path,
    *,
    niche_queries: Optional[Sequence[str]] = None,
    blackboard: Any = None,
    gatherers: Optional[dict[str, GatherFn]] = None,
    max_workers: int = 8,
) -> ScoutResult:
    """Build Scout queries from plan goal + grain intents + optional niche queries."""
    queries: list[tuple[str, str]] = [("shared", plan.goal)]
    for grain in plan.grains:
        intent = getattr(grain, "intent", "") or grain.grain_id
        queries.append((grain.grain_id, str(intent)))
        queries.append((grain.grain_id, f"repo: {intent}"))
    for q in niche_queries or ():
        queries.append(("shared", q))

    result = prefetch_for_queries(
        queries, Path(repo), gatherers=gatherers, max_workers=max_workers
    )

    if blackboard is not None:
        try:
            for pkt in result.packets:
                blackboard.post(
                    pkt.grain_id,
                    pkt.fence(),
                    kind="scout",
                )
            blackboard.post(
                "scout",
                f"Scout complete: {len(result.packets)} packets in {result.elapsed_ms:.0f}ms",
                kind="decision",
            )
        except Exception:
            pass
    return result


def inject_scout_into_specs(
    specs: dict[str, Any],
    scout: ScoutResult,
) -> dict[str, Any]:
    """Append Scout context to each GrainAgentSpec.context (immutable → replace)."""
    from hermes_cli.swarm.specialist import GrainAgentSpec

    out: dict[str, Any] = {}
    for gid, spec in specs.items():
        blob = scout.context_blob(grain_id=gid)
        if not isinstance(spec, GrainAgentSpec):
            out[gid] = spec
            continue
        new_ctx = (spec.context or "") + "\n\n" + blob
        # rebuild frozen dataclass
        out[gid] = GrainAgentSpec(
            grain_id=spec.grain_id,
            model_lane=spec.model_lane,
            toolsets=spec.toolsets,
            iteration_budget=spec.iteration_budget,
            token_budget=spec.token_budget,
            memory_namespace=spec.memory_namespace,
            system_prompt=spec.system_prompt
            + "\nPrefer SCOUT/* packets over re-searching unless Scout miss.",
            context=new_ctx,
            dropped_context=spec.dropped_context,
            used_tokens=spec.used_tokens,
        )
    return out
