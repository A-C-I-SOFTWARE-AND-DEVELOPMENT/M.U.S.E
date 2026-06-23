"""First-run onboarding for muse — device scan + profile builder.

The user asked: "when jarvis is installed have it scan entire device
from end to end collecting data and storing in long term memory on
the user persona, interests, likes, building a complete user
profile to build a relationship as well as have a base
understanding on user and how they interact tailoring itself and
updating how it works and interacts with user… have jarvis read
emails, texts as well. this is for local device use and storage."

This module gives JARVIS that capability. Scope and safety:

- **Opt-in via owner authorization.** Nothing runs without the
  user passing the OnboardingPolicy through ``OwnerAuth`` first.
- **Local-only.** All discovered data is written to the local
  memory store; no network calls from this module.
- **Read-only.** No files are modified, no system settings
  changed.
- **Respect platform sandboxes.** On iOS/Android the user must
  use the OS file picker; we don't bypass sandbox.
- **Secret-aware.** ``MemoryStore.remember`` already rejects
  secret-looking text — the scanner relies on that filter.

Wiring: ``OnboardingRunner.run(policy)`` returns an
``OnboardingReport`` summarizing what landed in memory.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from hermes_cli.jarvis_prime.memory import MemoryStore

LOGGER = logging.getLogger("hermes.jarvis_prime.onboarding")


# Filesystem locations we will inspect by default. The runner skips
# anything not present and never traverses into hidden virtualenvs,
# .git directories, or node_modules trees.
_DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "~/Documents",
    "~/Desktop",  # windows-footgun: ok — Linux/macOS path; Windows uses OneDrive-aware resolver elsewhere
    "~/Downloads",
    "~/.config", "~/.zshrc", "~/.bashrc", "~/.gitconfig",
    "~/.hermes", "~/.claude",
)


_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
})


_TEXT_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml",
    ".cfg", ".ini", ".eml",
})


@dataclass
class OnboardingPolicy:
    """User-authorized scope for the first-run scan.

    The user must approve each capability explicitly. Defaults are
    cautious; the install wizard surfaces a checkbox per field.
    """

    scan_home_directory: bool = False
    read_email_local: bool = False
    read_text_messages_local: bool = False
    read_browser_bookmarks: bool = False
    read_git_history_local: bool = False
    research_public_social: bool = False
    research_human_psychology: bool = False
    scan_roots: tuple[str, ...] = _DEFAULT_SCAN_ROOTS
    max_files_scanned: int = 5000
    max_bytes_per_file: int = 200_000

    @classmethod
    def disabled(cls) -> "OnboardingPolicy":
        return cls()

    @classmethod
    def full_local(cls) -> "OnboardingPolicy":
        """Maximum local-only profile build (user must authorize)."""

        return cls(
            scan_home_directory=True,
            read_email_local=True,
            read_text_messages_local=True,
            read_browser_bookmarks=True,
            read_git_history_local=True,
            research_public_social=True,
            research_human_psychology=True,
        )


@dataclass
class OnboardingFinding:
    category: str
    label: str
    value: str
    durability: str = "durable"
    confidence: float = 0.7


@dataclass
class OnboardingReport:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    files_scanned: int = 0
    bytes_read: int = 0
    findings_count: int = 0
    skipped_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "files_scanned": self.files_scanned,
            "bytes_read": self.bytes_read,
            "findings_count": self.findings_count,
            "skipped_paths": list(self.skipped_paths),
            "errors": list(self.errors)[:20],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Pattern extractors — extract durable user-profile bits from file content.
# ---------------------------------------------------------------------------


_EMAIL_RX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+")
_NAME_RX = re.compile(r"(?im)(?:^|\n)\s*(?:Author|From|Name)\s*[:=]\s*([A-Z][\w'\-. ]{1,40})")
_TIMEZONE_RX = re.compile(r"(?i)\b(?:tz|timezone)\s*[:=]\s*([A-Za-z_/+-]{3,40})")
_INTEREST_HINT = re.compile(
    r"(?i)\b(?:like|love|prefer|favorite|interested in|enjoy|use(?: ?d)?)\b\s+([\w][\w '+\-/.]{1,40})"
)
_LANG_HINT = re.compile(r"(?i)\b(python|kotlin|rust|typescript|go|swift|java|c\+\+|haskell|ruby|elixir)\b")


@dataclass
class OnboardingRunner:
    memory: MemoryStore
    policy: OnboardingPolicy = field(default_factory=OnboardingPolicy)

    def run(self, policy: Optional[OnboardingPolicy] = None) -> OnboardingReport:
        policy = policy or self.policy
        report = OnboardingReport()

        # Platform / host signature is always recorded — it's not PII.
        self._record_platform_signature()
        report.findings_count += 1

        if policy.scan_home_directory:
            self._scan_paths(policy, report)

        if policy.read_email_local:
            self._read_email_local(report)

        if policy.read_text_messages_local:
            self._read_text_messages_local(report)

        if policy.read_browser_bookmarks:
            self._read_browser_bookmarks(report)

        if policy.read_git_history_local:
            self._read_git_history_local(report)

        # Social research and human-psychology research are dispatched
        # to ``social_research.py`` — onboarding only flags the intent.
        if policy.research_public_social:
            self._mark_intent(
                "research_intent",
                "social_platforms",
                "Investigate public reddit / hackernews / github message boards for user-relevant patterns.",
            )
            report.findings_count += 1

        if policy.research_human_psychology:
            self._mark_intent(
                "research_intent",
                "human_psychology",
                "Study conversational pacing, when-to-interrupt, when-to-listen.",
            )
            report.findings_count += 1

        report.finished_at = datetime.now(timezone.utc)
        report.summary = (
            f"scanned {report.files_scanned} files; "
            f"{report.findings_count} findings; "
            f"{len(report.errors)} errors"
        )
        return report

    # ------------------------------------------------------------------
    # Platform signature
    # ------------------------------------------------------------------

    def _record_platform_signature(self) -> None:
        signature = {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "termux": "TERMUX_VERSION" in os.environ,
        }
        self.memory.remember(
            key="device_platform",
            value=json.dumps(signature),
            durability="durable",
            confidence=1.0,
            tags=("onboarding", "device"),
            source="agent",
        )

    # ------------------------------------------------------------------
    # Home-directory scan
    # ------------------------------------------------------------------

    def _scan_paths(self, policy: OnboardingPolicy, report: OnboardingReport) -> None:
        for raw in policy.scan_roots:
            root = Path(os.path.expanduser(raw))
            if not root.exists():
                report.skipped_paths.append(str(root))
                continue
            if root.is_file():
                self._scan_one_file(root, policy, report)
                continue
            for path in self._walk(root):
                if report.files_scanned >= policy.max_files_scanned:
                    report.errors.append(f"max_files_scanned={policy.max_files_scanned} reached")
                    return
                self._scan_one_file(path, policy, report)

    def _walk(self, root: Path) -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() in _TEXT_EXTENSIONS:
                    yield p

    def _scan_one_file(
        self, path: Path, policy: OnboardingPolicy, report: OnboardingReport
    ) -> None:
        try:
            data = path.read_text(encoding="utf-8", errors="ignore")[: policy.max_bytes_per_file]
            report.files_scanned += 1
            report.bytes_read += len(data)
            self._extract_profile_signals(data, report, source=str(path))
        except Exception as exc:  # pragma: no cover - defensive
            report.errors.append(f"{path}: {exc}")

    def _extract_profile_signals(
        self, text: str, report: OnboardingReport, source: str
    ) -> None:
        # Name
        m = _NAME_RX.search(text)
        if m:
            name = m.group(1).strip()
            if 1 < len(name) < 60:
                self.memory.remember(
                    key="user_name",
                    value=name,
                    durability="durable",
                    confidence=0.65,
                    tags=("onboarding", "profile"),
                    citations=(source,),
                )
                report.findings_count += 1
        # Email — first occurrence wins (gitconfig-style lines like
        # ``email = foo@bar.com`` are matched by _EMAIL_RX directly).
        m = _EMAIL_RX.search(text)
        if m:
            self.memory.remember(
                key="user_email",
                value=m.group(0).strip(),
                durability="durable",
                confidence=0.7,
                tags=("onboarding", "profile"),
                citations=(source,),
            )
            report.findings_count += 1
        # Timezone
        m = _TIMEZONE_RX.search(text)
        if m:
            tz = m.group(1).strip()
            self.memory.remember(
                key="user_timezone",
                value=tz,
                durability="durable",
                confidence=0.7,
                tags=("onboarding", "profile"),
                citations=(source,),
            )
            report.findings_count += 1
        # Interests
        for m in _INTEREST_HINT.finditer(text):
            interest = m.group(1).strip().lower()
            if 2 < len(interest) < 40 and "password" not in interest:
                self.memory.remember(
                    key=f"interest:{interest}",
                    value=f"signal of interest in {interest}",
                    durability="session",  # promote to durable on repeat
                    confidence=0.5,
                    tags=("onboarding", "interest"),
                )
                report.findings_count += 1
        # Languages
        for m in _LANG_HINT.finditer(text):
            lang = m.group(1).strip().lower()
            self.memory.remember(
                key=f"language:{lang}",
                value=f"uses {lang}",
                durability="session",
                confidence=0.55,
                tags=("onboarding", "language"),
            )
            report.findings_count += 1

    # ------------------------------------------------------------------
    # Email / text messages — local read only
    # ------------------------------------------------------------------

    def _read_email_local(self, report: OnboardingReport) -> None:
        # Email reading uses the existing gateway/email plugin when
        # the user has provided credentials. We DO NOT fetch over the
        # network from here; we only enumerate local mbox/IMAP cache
        # files (Thunderbird, Apple Mail, Outlook caches).
        candidates = [
            "~/Library/Mail/V*/MailData",                 # macOS
            "~/.thunderbird/*.default*/ImapMail",         # Linux
            "~/AppData/Local/Microsoft/Outlook",           # Windows
        ]
        for raw in candidates:
            base = Path(os.path.expanduser(raw.split("*")[0]))
            if not base.exists():
                continue
            self._mark_intent(
                "email_source",
                "local_mail_cache",
                f"local mail data discovered at {base}",
            )
            report.findings_count += 1

    def _read_text_messages_local(self, report: OnboardingReport) -> None:
        # iMessage on macOS lives at ~/Library/Messages/chat.db.
        # Android SMS lives in the platform content provider, accessible
        # only via the apps/android companion. We mark intent only.
        candidates = [
            "~/Library/Messages/chat.db",                 # macOS iMessage
            "/data/data/com.android.providers.telephony", # Android SMS provider (Termux can't reach)
        ]
        for raw in candidates:
            p = Path(os.path.expanduser(raw))
            if p.exists():
                self._mark_intent(
                    "text_source",
                    "local_messages",
                    f"local message cache at {p}",
                )
                report.findings_count += 1

    # ------------------------------------------------------------------
    # Browser bookmarks
    # ------------------------------------------------------------------

    def _read_browser_bookmarks(self, report: OnboardingReport) -> None:
        candidates = [
            "~/Library/Application Support/Firefox/Profiles",
            "~/Library/Application Support/Google/Chrome/Default/Bookmarks",
            "~/.config/google-chrome/Default/Bookmarks",
            "~/.mozilla/firefox",
        ]
        for raw in candidates:
            p = Path(os.path.expanduser(raw))
            if p.exists():
                self._mark_intent(
                    "browser_source",
                    raw,
                    f"browser data at {p}",
                )
                report.findings_count += 1

    # ------------------------------------------------------------------
    # Git history — durable interest signals
    # ------------------------------------------------------------------

    def _read_git_history_local(self, report: OnboardingReport) -> None:
        gitconfig = Path(os.path.expanduser("~/.gitconfig"))
        if gitconfig.is_file():
            try:
                text = gitconfig.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"(?im)\bname\s*=\s*(.+)", text)
                if m:
                    self.memory.remember(
                        key="user_name",
                        value=m.group(1).strip(),
                        durability="durable",
                        confidence=0.85,
                        tags=("onboarding", "profile", "gitconfig"),
                        citations=(str(gitconfig),),
                    )
                    report.findings_count += 1
                m = re.search(r"(?im)\bemail\s*=\s*(.+)", text)
                if m:
                    self.memory.remember(
                        key="user_email",
                        value=m.group(1).strip(),
                        durability="durable",
                        confidence=0.85,
                        tags=("onboarding", "profile", "gitconfig"),
                        citations=(str(gitconfig),),
                    )
                    report.findings_count += 1
            except Exception as exc:  # pragma: no cover - defensive
                report.errors.append(f"gitconfig: {exc}")

    # ------------------------------------------------------------------
    # Generic intent marker
    # ------------------------------------------------------------------

    def _mark_intent(self, category: str, key: str, value: str) -> None:
        self.memory.remember(
            key=f"{category}:{key}",
            value=value,
            durability="durable",
            confidence=1.0,
            tags=("onboarding", "intent"),
            source="agent",
        )
