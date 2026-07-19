"""Structured decision ledger for Hermes.

A *decision ledger* is the externally-visible record of a single
non-trivial decision Hermes makes. It replaces hidden chain-of-thought
with an auditable markdown artefact that a human reviewer, a later
session, the enterprise Judge, or a peer agent can read, parse, and
challenge.

This module is the code-level companion to:

* ``docs/orchestration/decision-ledger.md`` — canonical template and
  field-by-field guidance,
* ``templates/orchestration/decision-ledger-template.md`` — the blank
  form,
* ``skills/decision-quality-gate/SKILL.md`` — when to produce one,
* ``skills/research-validator/SKILL.md`` — how to fill it honestly.

What lives here:

* :class:`DecisionLedger` — the dataclass that mirrors the 15 ledger
  sections, plus light metadata (session id, sequence, slug, created
  time).
* :func:`render_template` — produce a blank template ready for an LLM
  to fill in.
* :func:`parse_markdown` — read a markdown ledger back into the
  dataclass. Strict about the heading set: missing headings are
  reported, never silently invented.
* :func:`write_ledger` / :func:`read_ledger` / :func:`list_ledgers` —
  filesystem CRUD against the canonical layout
  ``$HERMES_HOME/decisions/<session_id>/<seq>-<slug>.md``.
* :func:`next_seq` — pick the next zero-padded sequence number for a
  session.
* :class:`LedgerValidationError` — raised when a ledger is missing
  sections, has unknown headings, or fails a field-specific rule
  (confidence value, approval phrasing, …).

The module owns *no network* and *no subprocesses* — pure data
shaping plus filesystem I/O under ``HERMES_HOME``. That makes it
trivially testable and safe to call from any context (CLI, gateway,
cron, worker, test).
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# The 15 H2 section headings, in the order they must appear. External
# tooling (the Judge, the curator, the ``/decisions`` slash command)
# parses ledgers by heading — do not rename or reorder these without
# updating every consumer.
SECTION_HEADINGS: tuple[str, ...] = (
    "Decision",
    "Plain English Summary",
    "Context",
    "Evidence Reviewed",
    "Options Considered",
    "Selected Model / Worker",
    "Why This Choice",
    "Rejected Alternatives",
    "Cost / Latency / Quality Tradeoff",
    "Validation Plan",
    "Approval Required",
    "Final Decision",
    "Confidence",
    "Open Risks",
    "Rollback Plan",
)

# Map each heading to the dataclass attribute that holds it.
_HEADING_TO_ATTR: dict[str, str] = {
    "Decision": "decision",
    "Plain English Summary": "plain_english_summary",
    "Context": "context",
    "Evidence Reviewed": "evidence_reviewed",
    "Options Considered": "options_considered",
    "Selected Model / Worker": "selected_model_worker",
    "Why This Choice": "why_this_choice",
    "Rejected Alternatives": "rejected_alternatives",
    "Cost / Latency / Quality Tradeoff": "cost_latency_quality_tradeoff",
    "Validation Plan": "validation_plan",
    "Approval Required": "approval_required",
    "Final Decision": "final_decision",
    "Confidence": "confidence",
    "Open Risks": "open_risks",
    "Rollback Plan": "rollback_plan",
}

_ATTR_TO_HEADING: dict[str, str] = {v: k for k, v in _HEADING_TO_ATTR.items()}

TITLE = "Decision Ledger"

CONFIDENCE_LEVELS: tuple[str, ...] = ("low", "medium", "high")

# A section that says only "N/A" is acceptable iff a one-sentence
# justification accompanies it (e.g. ``N/A — no rollback needed; flag is
# additive and defaults to off``). This regex matches the bare placeholder
# that callers should NOT leave behind.
_BARE_NA_RE = re.compile(r"^\s*(n/a|na|none)\s*\.?\s*$", re.IGNORECASE | re.MULTILINE)

# Heading detection. Matches ``## Heading`` at the start of a line.
_SECTION_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
# Matches the document title ``# Decision Ledger`` (or any H1).
_TITLE_HEADING_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LedgerError(RuntimeError):
    """Base class for decision-ledger errors."""


class LedgerValidationError(LedgerError):
    """Raised when a ledger fails its structural or field-level checks.

    The ``problems`` attribute is the full list; ``str(exc)`` summarises
    them for human display.
    """

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems: list[str] = list(problems)
        super().__init__("; ".join(self.problems) or "ledger validation failed")


class LedgerNotFoundError(LedgerError):
    """Raised when a ledger lookup by path/session/seq fails."""


# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------

_DECISIONS_DIR_NAME = "decisions"

# Slugs: lowercase ASCII, words separated by single hyphens, capped length.
_MAX_SLUG_LEN = 60
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _hermes_home() -> Path:
    """Return the active Hermes home directory.

    Imported lazily so tests that point ``HERMES_HOME`` at a tmpdir before
    importing this module still pick up the override.
    """
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def decisions_dir() -> Path:
    """Return ``$HERMES_HOME/decisions``, creating the directory if needed."""
    d = _hermes_home() / _DECISIONS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def session_dir(session_id: str) -> Path:
    """Return the per-session decisions directory."""
    sid = _safe_session_id(session_id)
    d = decisions_dir() / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_session_id(session_id: str) -> str:
    sid = (session_id or "").strip()
    if not sid:
        raise LedgerError("session_id must be a non-empty string")
    if any(c in sid for c in ("/", "\\", "..", "\0")):
        raise LedgerError(f"session_id contains illegal characters: {session_id!r}")
    return sid


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class DecisionLedger:
    """A structured decision ledger.

    Each ``str`` field is the free-text body of the corresponding markdown
    section. Empty strings mean "not yet filled" and will be flagged by
    :meth:`validate`.

    Metadata fields (``session_id``, ``seq``, ``slug``, ``created_at``,
    ``path``) are filled by :func:`write_ledger` and :func:`read_ledger`;
    a freshly-constructed ledger has empty metadata.
    """

    decision: str = ""
    plain_english_summary: str = ""
    context: str = ""
    evidence_reviewed: str = ""
    options_considered: str = ""
    selected_model_worker: str = ""
    why_this_choice: str = ""
    rejected_alternatives: str = ""
    cost_latency_quality_tradeoff: str = ""
    validation_plan: str = ""
    approval_required: str = ""
    final_decision: str = ""
    confidence: str = ""
    open_risks: str = ""
    rollback_plan: str = ""

    # Metadata (not serialised inside the markdown body).
    title: str = TITLE
    session_id: str = ""
    seq: int = 0
    slug: str = ""
    created_at: float = 0.0
    path: Optional[Path] = None

    # ── section helpers ───────────────────────────────────────────────

    def section(self, heading: str) -> str:
        """Return the body of a named section.

        Raises ``KeyError`` for unknown headings so typos surface
        immediately at the call site.
        """
        attr = _HEADING_TO_ATTR[heading]
        return getattr(self, attr)

    def set_section(self, heading: str, body: str) -> None:
        """Set the body of a named section."""
        attr = _HEADING_TO_ATTR[heading]
        setattr(self, attr, body)

    def sections(self) -> dict[str, str]:
        """Return all 15 sections as an ordered dict (insertion-ordered)."""
        return {h: getattr(self, _HEADING_TO_ATTR[h]) for h in SECTION_HEADINGS}

    # ── validation ────────────────────────────────────────────────────

    def missing_sections(self) -> list[str]:
        """Return the heading names whose body is empty or a bare placeholder.

        "Empty" means: no non-whitespace content, OR the only content is a
        bare ``N/A``/``none`` with no justification. A section that says
        ``N/A — <reason>`` passes this check.
        """
        missing: list[str] = []
        for heading in SECTION_HEADINGS:
            body = getattr(self, _HEADING_TO_ATTR[heading]) or ""
            if not body.strip():
                missing.append(heading)
                continue
            # Strip HTML comments so the template's <!-- prompts --> don't
            # count as filled content.
            stripped = _strip_html_comments(body).strip()
            if not stripped:
                missing.append(heading)
                continue
            if _BARE_NA_RE.match(stripped) and "\n" not in stripped:
                # A bare "N/A" with no justification is not acceptable.
                missing.append(heading)
        return missing

    def is_complete(self) -> bool:
        """True iff every section has non-placeholder content."""
        return not self.missing_sections()

    def validate(self) -> None:
        """Run all checks; raise :class:`LedgerValidationError` on failure.

        Checks:

        * No empty / bare-N/A sections.
        * ``Confidence`` starts with one of ``low`` / ``medium`` / ``high``.
        * ``Approval Required`` begins with a recognised verdict word
          (``yes``, ``no``, ``defer``) — keeps tooling able to filter
          for "needs approval" without re-parsing free text.
        """
        problems: list[str] = []

        missing = self.missing_sections()
        if missing:
            problems.append(
                "missing or empty sections: " + ", ".join(missing)
            )

        conf = (self.confidence or "").strip().lower()
        if conf:
            head = re.split(r"[\s.,;:—-]", conf, maxsplit=1)[0]
            if head not in CONFIDENCE_LEVELS:
                problems.append(
                    "Confidence must start with one of "
                    f"{CONFIDENCE_LEVELS!r}; got {conf!r}"
                )

        appr = (self.approval_required or "").strip().lower()
        if appr:
            head = re.split(r"[\s.,;:—-]", appr, maxsplit=1)[0]
            if head not in {"yes", "no", "defer"}:
                problems.append(
                    "Approval Required must start with 'yes', 'no', or "
                    f"'defer'; got {appr!r}"
                )

        if problems:
            raise LedgerValidationError(problems)

    # ── serialisation ─────────────────────────────────────────────────

    def to_markdown(self) -> str:
        """Render the ledger as markdown using the canonical heading set.

        Empty sections render as the heading followed by an empty body —
        this is the same shape :func:`render_template` produces, so a
        round-trip ``parse_markdown(ledger.to_markdown())`` is identity.
        """
        lines: list[str] = [f"# {self.title}", ""]
        for heading in SECTION_HEADINGS:
            body = getattr(self, _HEADING_TO_ATTR[heading]) or ""
            lines.append(f"## {heading}")
            body = body.rstrip("\n")
            if body:
                lines.append(body)
            lines.append("")
        # Strip trailing blanks, end with exactly one newline.
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Slugify / metadata helpers
# ---------------------------------------------------------------------------


def slugify(text: str, *, max_len: int = _MAX_SLUG_LEN) -> str:
    """Convert ``text`` into a filesystem-safe kebab-case slug.

    * Unicode is NFKD-normalised then stripped to ASCII.
    * Non-alphanumerics collapse to a single ``-``.
    * Leading/trailing hyphens are removed.
    * Result is capped at ``max_len`` characters.
    * If the result is empty (text was symbols only), returns ``"decision"``.
    """
    if not text:
        return "decision"
    # Take the first line so multi-line decisions slugify only their
    # first sentence-ish prefix.
    first_line = text.strip().splitlines()[0]
    norm = unicodedata.normalize("NFKD", first_line)
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = _SLUG_STRIP_RE.sub("-", lowered).strip("-")
    if not slug:
        return "decision"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-") or "decision"
    return slug


def next_seq(session_id: str) -> int:
    """Return the next 1-based sequence number for ``session_id``.

    Counts only files matching the ``NNNN-<slug>.md`` pattern, so any
    hand-dropped files in the session directory are ignored.
    """
    d = session_dir(session_id)
    used: list[int] = []
    for child in d.iterdir():
        if not child.is_file() or child.suffix != ".md":
            continue
        m = re.match(r"^(\d{4})-", child.name)
        if m:
            used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def _ledger_filename(seq: int, slug: str) -> str:
    return f"{int(seq):04d}-{slug}.md"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _strip_html_comments(text: str) -> str:
    """Remove ``<!-- ... -->`` blocks (including multi-line) from ``text``."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


_TEMPLATE_HEADER = f"# {TITLE}\n"


def render_template(prefill: Mapping[str, str] | None = None) -> str:
    """Render a blank decision-ledger markdown template.

    ``prefill`` is an optional mapping from heading → body text. Any
    section not in ``prefill`` renders with the standard placeholder
    HTML comment, so an LLM filling the template sees a guidance hint
    in each empty section.

    Unknown headings in ``prefill`` raise :class:`KeyError` immediately.
    """
    pre: dict[str, str] = {}
    if prefill:
        for k, v in prefill.items():
            if k not in _HEADING_TO_ATTR:
                raise KeyError(f"unknown ledger section: {k!r}")
            pre[k] = v

    lines: list[str] = [_TEMPLATE_HEADER.rstrip("\n"), ""]
    for heading in SECTION_HEADINGS:
        lines.append(f"## {heading}")
        if heading in pre:
            body = pre[heading].rstrip("\n")
            if body:
                lines.append(body)
        else:
            lines.append(_PLACEHOLDERS[heading])
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


# Short HTML-comment hints rendered inside each empty section. The hints
# are stripped by :meth:`DecisionLedger.missing_sections` so they do NOT
# count as "filled" content — they exist solely to tell a downstream
# agent (or human) what to put in each section.
_PLACEHOLDERS: dict[str, str] = {
    "Decision": (
        "<!-- One sentence, active voice. The change you propose to make,"
        " not the deliberation. -->"
    ),
    "Plain English Summary": (
        "<!-- One short paragraph a non-technical reader could understand."
        " No jargon, no internal acronyms. -->"
    ),
    "Context": (
        "<!-- What triggered this decision? Cite the upstream artefact:"
        " user message, cron schedule, webhook, parent task, prior"
        " ledger. -->"
    ),
    "Evidence Reviewed": (
        "<!-- Concrete artefacts only — file paths with line ranges,"
        " verbatim commands, doc URLs with sections, prior session ids."
        " 'I considered the codebase' is not evidence. -->"
    ),
    "Options Considered": (
        "<!-- At least two options. Each option: Pros / Cons / Risk /"
        " Validation. 'Defer' is always a legitimate option. -->"
    ),
    "Selected Model / Worker": (
        "<!-- Which muse worker, subagent profile, or model will"
        " execute this? Name it precisely (e.g."
        " `delegation` -> `anthropic/claude-sonnet-4-6`). -->"
    ),
    "Why This Choice": (
        "<!-- Why the selected model/worker beats the alternatives for"
        " THIS task. Tie back to the evidence above. -->"
    ),
    "Rejected Alternatives": (
        "<!-- For each option NOT picked, one short paragraph on why it"
        " lost. Include a fallback you would switch to if the primary"
        " choice fails. -->"
    ),
    "Cost / Latency / Quality Tradeoff": (
        "<!-- Estimated cost (USD or token budget), expected latency per"
        " turn, and the quality bar this choice clears. -->"
    ),
    "Validation Plan": (
        "<!-- Commands (runnable from a fresh shell), manual checks"
        " (specific human observations), success criteria (binary"
        " 'did it work?'). -->"
    ),
    "Approval Required": (
        "<!-- 'no - proceed', 'yes - <named approver>', or"
        " 'defer - <reason>'. State why if 'no'. -->"
    ),
    "Final Decision": (
        "<!-- Which option won, by name (Option A / Option B / Defer /"
        " Neither). -->"
    ),
    "Confidence": (
        "<!-- low / medium / high - plus one sentence of why. -->"
    ),
    "Open Risks": (
        "<!-- Anything the Validation Plan does not cover. Each risk gets"
        " a one-line mitigation or an honest 'accepting because...'. -->"
    ),
    "Rollback Plan": (
        "<!-- Exact recovery procedure if the decision turns out wrong."
        " 'I'll figure it out' is not acceptable. -->"
    ),
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_markdown(text: str) -> DecisionLedger:
    """Parse a markdown decision ledger into a :class:`DecisionLedger`.

    Permissive about title and content; strict about heading names.

    * Headings are matched case-sensitively against
      :data:`SECTION_HEADINGS`. An unknown ``##`` heading raises
      :class:`LedgerValidationError`.
    * Missing headings are tolerated — the corresponding field stays
      empty. Use :meth:`DecisionLedger.validate` afterwards to surface
      that gap.
    * Content before the first ``##`` heading is treated as the title
      block and discarded (other than capturing the H1, if present).
    * Duplicate headings raise :class:`LedgerValidationError` — a
      well-formed ledger has each heading exactly once.
    """
    if text is None:
        raise LedgerValidationError(["ledger text is None"])

    ledger = DecisionLedger()

    title_match = _TITLE_HEADING_RE.search(text)
    if title_match:
        ledger.title = title_match.group(1).strip() or TITLE

    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        # No section headings at all — return an empty ledger so the
        # caller's validate() surfaces a useful "missing sections" error.
        return ledger

    seen: set[str] = set()
    problems: list[str] = []

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].lstrip("\n").rstrip()

        if heading not in _HEADING_TO_ATTR:
            problems.append(f"unknown section heading: {heading!r}")
            continue

        if heading in seen:
            problems.append(f"duplicate section heading: {heading!r}")
            continue
        seen.add(heading)

        # Strip HTML comments so an unfilled template parses to an empty
        # body, not a body that looks filled with placeholder hints.
        without_hints = _strip_html_comments(body).strip()
        if without_hints:
            ledger.set_section(heading, body)
        # else: leave the field empty so missing_sections() flags it.

    if problems:
        raise LedgerValidationError(problems)

    return ledger


# ---------------------------------------------------------------------------
# Filesystem I/O
# ---------------------------------------------------------------------------


def write_ledger(
    ledger: DecisionLedger,
    *,
    session_id: str,
    seq: Optional[int] = None,
    slug: Optional[str] = None,
    validate: bool = True,
    overwrite: bool = False,
) -> Path:
    """Persist ``ledger`` to disk and return its path.

    Layout: ``$HERMES_HOME/decisions/<session_id>/<NNNN>-<slug>.md``.

    Parameters
    ----------
    ledger:
        The ledger to write. ``ledger.session_id``, ``seq``, ``slug``,
        ``created_at`` and ``path`` are populated on success.
    session_id:
        The session this ledger belongs to. Required even when
        ``ledger.session_id`` is already set, so callers cannot
        accidentally write into another session's directory.
    seq:
        Sequence number within the session. If ``None``, the next free
        number is chosen via :func:`next_seq`.
    slug:
        Filename slug. If ``None``, derived from the decision text via
        :func:`slugify`.
    validate:
        If True (default), :meth:`DecisionLedger.validate` is called
        before write — incomplete ledgers raise rather than persist a
        half-finished record. Pass ``False`` to write a work-in-progress
        ledger that will be filled in later.
    overwrite:
        If True, an existing file at the target path is overwritten;
        otherwise a collision raises :class:`LedgerError`.
    """
    if validate:
        ledger.validate()

    sid = _safe_session_id(session_id)
    target_seq = int(seq) if seq is not None else next_seq(sid)
    target_slug = slug or slugify(ledger.decision or "decision")

    target_dir = session_dir(sid)
    target_path = target_dir / _ledger_filename(target_seq, target_slug)

    if target_path.exists() and not overwrite:
        raise LedgerError(f"refusing to overwrite existing ledger: {target_path}")

    ledger.session_id = sid
    ledger.seq = target_seq
    ledger.slug = target_slug
    if not ledger.created_at:
        ledger.created_at = time.time()
    ledger.path = target_path

    _atomic_write_text(target_path, ledger.to_markdown())
    _chain_decision(ledger)
    return target_path


def _chain_decision(ledger: "DecisionLedger") -> None:
    """Soft hook: record the written decision on the axiom event chain.

    Filesystem-only (keeps this module's no-network/no-subprocess
    promise) and never raises into the host.
    """
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        bridge = get_bridge()
        if bridge.inert:
            return
        first_line = (ledger.decision or "").strip().splitlines()
        bridge.record_event(
            "decision.written",
            {
                "session_id": ledger.session_id,
                "seq": ledger.seq,
                "slug": ledger.slug,
                "path": str(ledger.path) if ledger.path else None,
                "decision": first_line[0] if first_line else "",
            },
        )
    except Exception:
        pass


def read_ledger(path: Path | str) -> DecisionLedger:
    """Read a ledger file back into a :class:`DecisionLedger`.

    Populates ``session_id``, ``seq``, ``slug``, ``created_at`` (from
    file mtime) and ``path`` from the on-disk metadata so the returned
    object can be edited and round-tripped via :func:`write_ledger`
    with ``overwrite=True``.

    Raises :class:`LedgerNotFoundError` if the file does not exist and
    :class:`LedgerValidationError` if its heading set is invalid. The
    *content* of the ledger is not validated here — callers that want a
    completeness check should call :meth:`DecisionLedger.validate`.
    """
    p = Path(path)
    if not p.is_file():
        raise LedgerNotFoundError(f"no ledger at {p}")

    text = p.read_text(encoding="utf-8")
    ledger = parse_markdown(text)
    ledger.path = p
    ledger.created_at = p.stat().st_mtime

    m = re.match(r"^(\d{4})-(.+)\.md$", p.name)
    if m:
        ledger.seq = int(m.group(1))
        ledger.slug = m.group(2)

    # The parent directory name is the session id, unless ``path`` was
    # passed in pointing somewhere unusual — in which case leave the
    # field empty rather than guessing.
    try:
        if p.parent.parent == decisions_dir():
            ledger.session_id = p.parent.name
    except Exception:
        pass

    return ledger


def list_ledgers(session_id: Optional[str] = None) -> list[Path]:
    """List ledger files on disk.

    With ``session_id``, list that session's ledgers in sequence order.
    Without, list every ledger under ``$HERMES_HOME/decisions``,
    grouped by session and sorted within each.
    """
    root = decisions_dir()
    if session_id is not None:
        sid = _safe_session_id(session_id)
        sdir = root / sid
        if not sdir.is_dir():
            return []
        return _sorted_ledger_files(sdir)

    out: list[Path] = []
    for sdir in sorted(p for p in root.iterdir() if p.is_dir()):
        out.extend(_sorted_ledger_files(sdir))
    return out


def _sorted_ledger_files(d: Path) -> list[Path]:
    """Return ``NNNN-<slug>.md`` files in ``d``, sorted by sequence."""
    keyed: list[tuple[int, Path]] = []
    for child in d.iterdir():
        if not child.is_file() or child.suffix != ".md":
            continue
        m = re.match(r"^(\d{4})-", child.name)
        if not m:
            continue
        keyed.append((int(m.group(1)), child))
    keyed.sort(key=lambda kv: kv[0])
    return [p for _, p in keyed]


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via rename so partial writes never appear."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


__all__ = [
    "CONFIDENCE_LEVELS",
    "DecisionLedger",
    "LedgerError",
    "LedgerNotFoundError",
    "LedgerValidationError",
    "SECTION_HEADINGS",
    "TITLE",
    "decisions_dir",
    "list_ledgers",
    "next_seq",
    "parse_markdown",
    "read_ledger",
    "render_template",
    "session_dir",
    "slugify",
    "write_ledger",
]
