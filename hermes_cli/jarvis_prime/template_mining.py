"""Template mining for the fast path — scaffolds from verifier-PASSED outputs.

Per cluster, the miner aligns the cluster's verifier-PASSED outputs (token-level
longest-common-subsequence, progressively reduced) into a stable literal
skeleton; the gaps become typed slots. Each emitted template is:

- ``scaffold.gbnf``  — a GBNF grammar forcing the skeleton literals (forced
  tokens cost ~0 decode steps) with typed slot rules between them;
- ``prefix.txt``     — the cluster's shared prompt prefix (common task-prompt
  prefix + one verified reasoning-first exemplar) for prompt-cache priming;
- ``meta.json``      — version, mode (``hard``/``soft``), source output hashes.

PASSED-only mining is structural: failed records are filtered out before any
alignment, and every source hash in ``meta.json`` is checked back against the
verifier-accepted set by the tests. Each grammar is self-checked by re-matching
every exemplar through an equivalent regex before emit (and validated with
llama.cpp's ``test-gbnf-validator`` where available).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from .bench.corpus import CorpusRecord
from .clusters import ClusterModel, EmbeddingBackend

ENV_TEMPLATES_DIR = "muse_TEMPLATES_DIR"
DEFAULT_TAU = 0.75
SCAFFOLD_FILE = "scaffold.gbnf"
PREFIX_FILE = "prefix.txt"
META_FILE = "meta.json"

# Spec default: clusters with fewer than 10 passed outputs are skipped. The
# fixture-scale container run passes a lower min_support explicitly (recorded
# as a deviation in the phase report).
SPEC_MIN_SUPPORT = 10

_TOKEN_RE = re.compile(r"\w+|\s+|[^\w\s]")


def templates_dir() -> Path:
    """Template registry root (env-overridable for live, on-device mining)."""

    override = os.environ.get(ENV_TEMPLATES_DIR, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class SlotSpec:
    """One template gap: a GBNF rule and the equivalent self-check regex."""

    kind: str  # "number" | "line" | "text"
    optional: bool

    @property
    def gbnf(self) -> str:
        if self.kind == "number":
            body = '[0-9]+ ("." [0-9]+)?'
        elif self.kind == "line":
            body = "[^\\n]+"
        else:  # bounded multi-line free text
            body = '([^\\n]* "\\n"){0,8} [^\\n]+'
        return f"({body})?" if self.optional else body

    @property
    def regex(self) -> str:
        if self.kind == "number":
            body = r"[0-9]+(?:\.[0-9]+)?"
        elif self.kind == "line":
            body = r"[^\n]+"
        else:
            body = r"(?:[^\n]*\n){0,8}[^\n]+"
        return f"(?:{body})?" if self.optional else body


@dataclass(frozen=True)
class MinedTemplate:
    cluster_id: int
    literals: tuple[str, ...]  # len == len(slots) + 1; may contain ""
    slots: tuple[SlotSpec, ...]
    prefix: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def scaffold_gbnf(self) -> str:
        parts: list[str] = []
        rules: list[str] = []
        for i, lit in enumerate(self.literals):
            if lit:
                parts.append(_gbnf_quote(lit))
            if i < len(self.slots):
                rule = f"slot{i}"
                rules.append(f"{rule} ::= {self.slots[i].gbnf}")
                parts.append(rule)
        root = " ".join(parts) if parts else '""'
        return "\n".join([f"root ::= {root}", *rules]) + "\n"

    @property
    def self_check_regex(self) -> str:
        out = []
        for i, lit in enumerate(self.literals):
            out.append(re.escape(lit))
            if i < len(self.slots):
                out.append(self.slots[i].regex)
        return "".join(out)

    def matches(self, text: str) -> bool:
        return re.fullmatch(self.self_check_regex, text) is not None


def _gbnf_quote(literal: str) -> str:
    escaped = (
        literal.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _lcs(a: Sequence[str], b: Sequence[str]) -> list[str]:
    """Classic DP longest common subsequence over token lists."""

    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, nxt = dp[i], dp[i + 1]
        for j in range(m - 1, -1, -1):
            row[j] = nxt[j + 1] + 1 if a[i] == b[j] else max(nxt[j], row[j + 1])
    out: list[str] = []
    i = j = 0
    while i < n and j < m:
        if a[i] == b[j]:
            out.append(a[i])
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def _gaps_against(skeleton: Sequence[str], text_tokens: Sequence[str]) -> Optional[list[str]]:
    """Greedy left-to-right alignment of skeleton tokens inside an exemplar.

    Returns the ``len(skeleton) + 1`` gap strings, or None when the skeleton is
    not a subsequence of the exemplar.
    """

    gaps: list[str] = []
    pos = 0
    current: list[str] = []
    for tok in skeleton:
        while pos < len(text_tokens) and text_tokens[pos] != tok:
            current.append(text_tokens[pos])
            pos += 1
        if pos >= len(text_tokens):
            return None
        gaps.append("".join(current))
        current = []
        pos += 1
    gaps.append("".join(text_tokens[pos:]))
    return gaps


def _slot_for(gap_values: Sequence[str]) -> SlotSpec:
    nonempty = [g for g in gap_values if g]
    optional = len(nonempty) < len(gap_values)
    if nonempty and all(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", g) for g in nonempty):
        return SlotSpec("number", optional)
    if all("\n" not in g for g in nonempty):
        return SlotSpec("line", optional)
    return SlotSpec("text", optional)


def _merge_fragmented_slots(
    literals: list[str], slots: list[SlotSpec]
) -> tuple[list[str], list[SlotSpec]]:
    """Collapse ``slot " " slot`` chains into one slot.

    LCS keeps common space tokens inside otherwise-varying text, fragmenting a
    free-text gap into word-sized slots whose count over-constrains the
    grammar. Any space-only literal (no newline — indentation stays structural)
    between two slots is folded into a single wider slot.
    """

    elements: list[Any] = [literals[0]]
    for slot, lit in zip(slots, literals[1:]):
        elements.extend((slot, lit))

    merged: list[Any] = [elements[0]]
    for el in elements[1:]:
        gap = merged[-1]
        if (
            isinstance(el, SlotSpec)
            and len(merged) >= 2
            and isinstance(merged[-2], SlotSpec)
            and isinstance(gap, str)
            and gap != ""
            and set(gap) <= {" "}
        ):
            prev: SlotSpec = merged[-2]
            kind = "text" if "text" in (prev.kind, el.kind) else "line"
            merged[-2] = SlotSpec(kind, prev.optional and el.optional)
            merged.pop()  # drop the space literal; merged now ends with the slot
        else:
            merged.append(el)

    out_literals = [merged[0]]
    out_slots = []
    for el in merged[1:]:
        if isinstance(el, SlotSpec):
            out_slots.append(el)
        else:
            out_literals.append(el)
    return out_literals, out_slots


def _common_prefix(texts: Sequence[str]) -> str:
    if not texts:
        return ""
    shortest: str = min(texts, key=lambda t: len(t))
    for i, ch in enumerate(shortest):
        if any(t[i] != ch for t in texts):
            return shortest[:i]
    return shortest


def mine_cluster(
    cluster_id: int,
    passed: Sequence[CorpusRecord],
    *,
    corpus_hash: str,
    backend_name: str,
) -> Optional[MinedTemplate]:
    """Mine one cluster's scaffold from its verifier-passed records."""

    outputs = [r.output for r in passed]
    token_lists = [_tokens(o) for o in outputs]
    skeleton = token_lists[0]
    for other in token_lists[1:]:
        skeleton = _lcs(skeleton, other)
    if not skeleton:
        return None

    per_exemplar_gaps = []
    for toks in token_lists:
        gaps = _gaps_against(skeleton, toks)
        if gaps is None:
            return None
        per_exemplar_gaps.append(gaps)

    # Collapse skeleton tokens into literal runs separated by active gaps
    # (gap positions where at least one exemplar has content).
    n_gaps = len(skeleton) + 1
    active = [any(g[i] for g in per_exemplar_gaps) for i in range(n_gaps)]
    literals: list[str] = []
    slots: list[SlotSpec] = []
    current_lit: list[str] = []
    for i in range(n_gaps):
        if active[i]:
            literals.append("".join(current_lit))
            current_lit = []
            slots.append(_slot_for([g[i] for g in per_exemplar_gaps]))
        if i < len(skeleton):
            current_lit.append(skeleton[i])
    literals.append("".join(current_lit))
    literals, slots = _merge_fragmented_slots(literals, slots)

    skeleton_chars = sum(len(t) for t in literals)
    mean_len = sum(len(o) for o in outputs) / len(outputs)
    coverage = skeleton_chars / mean_len if mean_len else 0.0
    # "hard" is reserved for structural clusters: high literal coverage, few
    # slots, and every slot single-line constrained (the grammar pins the
    # output shape). Anything with free-text gaps stays "soft" so reasoning is
    # never hard-forced.
    structural = all(s.kind in ("number", "line") for s in slots)
    mode = "hard" if coverage >= 0.5 and len(slots) <= 4 and structural else "soft"

    # Shared prompt prefix for cache priming: the cluster's common task-prompt
    # prefix plus ONE verified exemplar (reasoning comment before the answer
    # code — reasoning-first ordering).
    prompt_prefix = _common_prefix([r.prompt for r in passed]).rstrip()
    exemplar: str = min(outputs, key=lambda o: len(o))
    prefix = (
        "You answer tasks of this shape, always reasoning before the answer.\n"
        f"Task prefix: {prompt_prefix}\n"
        "Verified example output:\n"
        f"{exemplar.rstrip()}\n"
        "---\n"
    )

    template = MinedTemplate(
        cluster_id=cluster_id,
        literals=tuple(literals),
        slots=tuple(slots),
        prefix=prefix,
        meta={
            "v": 1,
            "version": 1,
            "cluster_id": cluster_id,
            "mode": mode,
            "support": len(passed),
            "coverage": round(coverage, 4),
            "slot_count": len(slots),
            "verified_only": True,
            "source_task_ids": sorted(r.task_id for r in passed),
            "source_output_hashes": sorted(r.output_hash for r in passed),
            "corpus_hash": corpus_hash,
            "backend_name": backend_name,
            "tau": DEFAULT_TAU,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    # Self-check: the grammar's regex twin must re-match every exemplar.
    if not all(template.matches(o) for o in outputs):
        return None
    return template


def mine_templates(
    records: Sequence[CorpusRecord],
    model: ClusterModel,
    *,
    backend: EmbeddingBackend,
    min_support: int = SPEC_MIN_SUPPORT,
) -> list[MinedTemplate]:
    """Mine templates for every cluster with enough verifier-PASSED outputs.

    Failed records never reach alignment — the PASSED filter is the first
    statement, and source hashes recorded in metadata are derived from the
    filtered set only.
    """

    passed = [r for r in records if r.verifier_passed]
    by_cluster: dict[int, list[CorpusRecord]] = {}
    for rec in passed:
        assignment = model.assign(rec.prompt, backend=backend)
        by_cluster.setdefault(assignment.cluster_id, []).append(rec)

    corpus_hash = hashlib.sha256(
        json.dumps(sorted(r.task_id for r in records)).encode("utf-8")
    ).hexdigest()
    mined: list[MinedTemplate] = []
    for cluster_id in sorted(by_cluster):
        members = by_cluster[cluster_id]
        if len(members) < min_support:
            continue
        template = mine_cluster(
            cluster_id,
            sorted(members, key=lambda r: r.task_id),
            corpus_hash=corpus_hash,
            backend_name=backend.name,
        )
        if template is not None:
            mined.append(template)
    return mined


def write_templates(templates: Sequence[MinedTemplate], out_dir: Path) -> list[Path]:
    written: list[Path] = []
    for template in templates:
        cluster_dir = out_dir / str(template.cluster_id)
        cluster_dir.mkdir(parents=True, exist_ok=True)
        (cluster_dir / SCAFFOLD_FILE).write_text(template.scaffold_gbnf, encoding="utf-8")
        (cluster_dir / PREFIX_FILE).write_text(template.prefix, encoding="utf-8")
        (cluster_dir / META_FILE).write_text(
            json.dumps(template.meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(cluster_dir)
    return written


@dataclass(frozen=True)
class TemplateFiles:
    """A template as loaded from disk (what the runtime fast path consumes)."""

    cluster_id: int
    scaffold_gbnf: str
    prefix: str
    meta: dict[str, Any]

    @property
    def mode(self) -> str:
        return str(self.meta.get("mode", "soft"))


def load_template(root: Path, cluster_id: int) -> Optional[TemplateFiles]:
    cluster_dir = root / str(cluster_id)
    scaffold = cluster_dir / SCAFFOLD_FILE
    prefix = cluster_dir / PREFIX_FILE
    meta = cluster_dir / META_FILE
    if not (scaffold.exists() and prefix.exists() and meta.exists()):
        return None
    return TemplateFiles(
        cluster_id=cluster_id,
        scaffold_gbnf=scaffold.read_text(encoding="utf-8"),
        prefix=prefix.read_text(encoding="utf-8"),
        meta=json.loads(meta.read_text(encoding="utf-8")),
    )


__all__ = [
    "ENV_TEMPLATES_DIR",
    "DEFAULT_TAU",
    "SPEC_MIN_SUPPORT",
    "SlotSpec",
    "MinedTemplate",
    "TemplateFiles",
    "templates_dir",
    "mine_cluster",
    "mine_templates",
    "write_templates",
    "load_template",
]
