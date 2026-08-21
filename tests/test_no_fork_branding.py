"""Guard against tranches that re-introduce downstream-fork branding.

This repository is pristine upstream ``NousResearch/hermes-agent`` with a
downstream fork being ported in tranche by tranche and de-branded on the way.
Two leaks already made it through hand review alone -- ``tools/security``
shipped a package docstring naming the fork as the owning product -- so hand
review is not the control. This file is.

THE TRAP THIS FILE EXISTS TO AVOID
----------------------------------
The obvious gate, ``git grep -i muse``, is catastrophically wrong here: upstream
itself contains "muse" in dozens of files, and every one of them is legitimate.

  * **Muse Spark** is Meta Superintelligence Labs' model family and ``muse`` is a
    live provider alias (``plugins/model-providers/meta-ai``).
  * **Muse Code** is a third-party coding agent whose worktree-isolation flag
    upstream credits as prior art.
  * **Muse 2 / Muse S** are EEG headbands driving the neuroskill-bci skill.
  * **singularity** (181 hits) is the Singularity/Apptainer container runtime, a
    first-class terminal backend beside docker/modal/ssh/daytona.
  * **caduceus** is Hermes's own staff -- ``HERMES_CADUCEUS`` is *upstream's*
    branding; deleting it would strip the project's identity, not the fork's.
  * **hey_jarvis** is openWakeWord's built-in wake word. The fork's module is
    specifically ``jarvis_prime``; bare "jarvis" is not a marker.
  * ``MEMUSED`` (vendored sqlite3.h), ``museum``, ``randomuser``,
    ``SpectrumUser``, ``FromUserName`` are substring accidents.
  * ``prime`` is saturated upstream (PrimeIntellect credits, "prime the cache",
    ``web-search-prime``) and the glyph U+25C9 is upstream's own status badge.

Every marker below is therefore judged by what the string *means*, never by
substring, and every one was measured over the whole tree: apart from the known
leaks it exists to catch, each has zero occurrences. That is what makes a hit
actionable -- it cannot be an upstream false positive.

TWO SPELLINGS ARE DELIBERATELY NOT GATED
----------------------------------------
  * title-case ``Muse`` alone -- 35 upstream lines in 18 files (Muse Spark, Muse
    Code, Muse 2/S). Ungateable without wrecking the provider plugin.
  * lowercase ``muse`` alone -- the provider alias tuple, the EEG device name,
    and the English noun in desktop intro copy ("The muse is patched in").

All-caps ``MUSE`` *is* gated: its only upstream occurrence is the model id
``MUSE-SPARK-1.2-CONTRIBUTOR``, which one lookahead spares. So a de-branding
that leaves ``DEFAULT_SKIN = "muse"`` or ``app_name = "Muse"`` behind is a KNOWN
RESIDUAL GAP that only review catches. Do not "fix" it by widening to bare muse:
``test_markers_spare_upstream_strings`` will stop you, and it is right to.

SCOPE
-----
Every file git tracks, minus known-binary suffixes, minus ``docs/consolidation``
(the port ledger names the fork on purpose). ``git ls-files`` rather than a
suffix allowlist is load-bearing twice over:

  * later tranches bring file types no allowlist anticipated. T12 is 426
    ``jarvis_prime`` files; T13 brings Android (``build.gradle``, ``.kt``,
    ``strings.xml``, ``com.muse.*``) and installers. A closed suffix list is a
    silent hole in exactly the tranches this guard exists to police -- and it
    already misses live files here: ``cli-config.yaml.example``, ``.mailmap``,
    ``plugins/kanban/systemd/*.service``, ``scripts/hermes-gateway``,
    ``docker/s6-rc.d/*/run``, ``LICENSE``.
  * gitignored working-tree junk stays out, which is what makes the home-dir
    marker safe to widen. ``test_durations.json`` is a gitignored pytest cache
    holding 19 lines of the fork author's ``C:\\Users\\Echer\\AppData\\...``,
    and a developer's local ``.env`` may well carry ``MUSE_*``. Neither ships,
    so neither may redden the gate.

Both the file's **path** and its **contents** are scanned. The path half is not
redundant: ``contributors/emails/<address>`` stores identity in the *filename*
and has no content to grep, and a ``hermes_cli/jarvis_prime/`` package can be
perfectly de-branded inside every file while the directory still ships the
fork's name.

Pure filesystem scan -- nothing is imported, so it has no side effects. About
3s over ~10,100 files / 121 MB: a lowercased-bytes prefilter (memmem, not a
bytes regex -- measured 2.0s vs 7.5s) leaves ~195 candidate files, and
per-marker tokens then narrow which regexes touch each one (0.95s vs 5.1s for
running all of them).

See docs/consolidation/PORT-LEDGER.md for the port this guards.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The port ledger discusses the fork by name on purpose -- that is its job.
SKIP_RELDIRS = ("docs/consolidation",)

# Suffixes that cannot carry a reviewable leak. A *denylist*: anything not named
# here is scanned, so a text format arriving with a later tranche is covered by
# default rather than silently exempt.
BINARY_SUFFIXES = {
    ".7z", ".bin", ".bmp", ".bz2", ".class", ".db", ".dll", ".dylib", ".eot",
    ".exe", ".gguf", ".gif", ".gz", ".ico", ".icns", ".idx", ".jar", ".jpeg",
    ".jpg", ".mov", ".mp3", ".mp4", ".odt", ".ogg", ".onnx", ".otf", ".pack",
    ".pdb", ".pdf", ".png", ".pt", ".pth", ".pyc", ".pyd", ".safetensors",
    ".so", ".sqlite", ".sqlite3", ".tar", ".tflite", ".tif", ".tiff", ".ttf",
    ".wav", ".webm", ".webp", ".whl", ".woff", ".woff2", ".xz", ".zip", ".zst",
}

# Only used by the no-git fallback (source tarball, vendored copy). With git
# present, .gitignore already excludes all of these.
SKIP_DIRS = {
    ".git", "venv", ".venv", "node_modules", "__pycache__", "build", "dist",
    "site-packages", "third_party", ".tanstack", ".mypy_cache", ".pytest_cache",
    ".pytest-cache", ".ruff_cache", ".next", "coverage", "hermes_agent.egg-info",
}

# Gitignored build artefacts that are not source in any checkout. Applied
# always, not just in the fallback, so the two paths agree: without it the
# fallback reports 19 false positives from test_durations.json, a pytest
# duration cache full of the fork author's own absolute paths.
SKIP_NAMES = {"test_durations.json"}

# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
# Whole-file exemptions. An allowlist entry is a standing permission for
# branding to ship, so it is only ever correct for a file whose *purpose* is to
# enumerate fork markers. Keep this at three entries.
ALLOWLIST: dict[str, str] = {
    # The port classifier. Its BRANDING_SUBS table is *supposed* to name every
    # fork marker and FORK_WORKTREE is *supposed* to hold the fork checkout
    # path. Gating it would permanently red-flag the tool that de-brands.
    "scripts/consolidation/triage_shared_files.py":
        "port classifier; its rewrite table must name every fork marker",
    # The legacy-environment shim, expected from a later tranche. Its whole
    # reason to exist is a table mapping every legacy MUSE_* env var onto its
    # HERMES_* replacement, so it must be allowed to spell them.
    "hermes_cli/env_compat.py":
        "legacy env shim; its table must spell every legacy MUSE_ name",
    # This file. Markers, samples and negative controls are literal fork
    # branding by construction; without this entry the guard fails on itself.
    "tests/test_no_fork_branding.py":
        "the guard itself; markers and controls are literal by construction",
}

# Allowlisted paths that do not exist yet. Everything else in ALLOWLIST must be
# a real file -- a dead entry weakens the guard silently. When the env shim
# lands, drop it from here (not from ALLOWLIST).
PENDING_PATHS = {"hermes_cli/env_compat.py"}

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
# U+25C9 is upstream's own status glyph ("<glyph> focus", "<glyph> STT", the
# "<glyph>_<glyph>" kaomoji), so it is never gated on alone -- only the
# two-token agent badge is a fork marker. JSON and .jsonl fixtures spell the
# glyph as a six-character escape, so the badge accepts both forms, and the gap
# admits the non-breaking space a copy-paste from a rendered TUI leaves behind.
BADGE_GLYPH = chr(0x25C9)
BADGE_ESCAPED = re.escape(chr(92) + "u25c9")
BADGE_EITHER = "(?:" + BADGE_GLYPH + "|" + BADGE_ESCAPED + ")"
BADGE_GAP = "[ \t" + chr(0x00A0) + "]*"


class Marker(NamedTuple):
    name: str
    # Lowercase ASCII prefilter tokens. At least one MUST appear in any string
    # the regex can match, or the scan skips the file and the marker is
    # silently dead. test_every_marker_matches_its_own_sample pins this.
    tokens: tuple[bytes, ...]
    rx: re.Pattern[str]
    sample: str          # a real leak this must catch (positive control)
    fix: str
    content: bool = True   # apply to the file's bytes
    paths: bool = True     # apply to the file's repo-relative path


MARKERS: tuple[Marker, ...] = (
    Marker(
        "M.U.S.E.",
        # NOT b"muse": the dotted product name has no "muse" substring. Both
        # known leaks are only reachable today because those same lines happen
        # to also say "Work Packet" -- exactly how such a hole hides.
        (b"m.u.s.e",),
        re.compile(r"M\.U\.S\.E", re.IGNORECASE),
        '"""Security utilities for M.U.S.E.',
        "name the product Hermes Agent",
    ),
    Marker(
        "MUSE product name",
        (b"muse",),
        # All-caps only. Its sole upstream occurrence is the Meta model id
        # "MUSE-SPARK-1.2-CONTRIBUTOR" (a case-insensitivity fixture at
        # tests/hermes_cli/test_model_data_policy_guard.py:38), which the
        # lookahead spares. Title-case and lowercase "muse" are NOT gated.
        re.compile(r"\bMUSE\b(?!-SPARK)"),
        'BANNER = "Welcome to MUSE"',
        "the product is Hermes Agent",
    ),
    Marker(
        "muse_ env/config prefix",
        (b"muse",),
        # Case-INsensitive on purpose: the fork ships MUSE_HOME, and a port that
        # lowercases it (env_prefix="muse_", "muse_home:" in YAML) is the same
        # leak. The \b spares MEMUSED and "test_muse_launcher" alike -- both
        # have a word character before the m.
        re.compile(r"\bmuse_", re.IGNORECASE),
        "os.environ['MUSE_HOME']",
        "rename the variable to its HERMES_ equivalent",
    ),
    Marker(
        "jarvis_prime",
        (b"jarvis",),
        # The exact fork module only. Bare "jarvis" is openWakeWord's wake word
        # and bare "prime" is PrimeIntellect / "prime the cache".
        re.compile(r"\bjarvis[_-]prime\b", re.IGNORECASE),
        "from hermes_cli.jarvis_prime import tokenjuice",
        "the de-branded module name is hermes_cli.prime",
    ),
    Marker(
        "fork owner handle",
        (b"echer",),
        re.compile(r"echerd27", re.IGNORECASE),
        '- "echerd27-design/hermes-agent"',
        "use NousResearch/hermes-agent or a neutral placeholder (octo/cat)",
    ),
    Marker(
        "MuseHQ org",
        (b"muse",),
        re.compile(r"\bMuse[ _-]?HQ\b", re.IGNORECASE),
        "https://github.com/MuseHQ/agent",
        "point at NousResearch",
    ),
    Marker(
        "muse-sync service",
        (b"muse",),
        re.compile(r"\bmuse[-_]sync\b", re.IGNORECASE),
        "systemctl start muse-sync",
        "use the upstream service name",
    ),
    Marker(
        "com.muse app id",
        (b"muse",),
        # No trailing dot required: an Android applicationId may be bare
        # "com.muse". Upstream's is com.nousresearch.hermes.
        re.compile(r"\bcom\.muse\b", re.IGNORECASE),
        '"appId": "com.muse.desktop"',
        "the upstream appId is com.nousresearch.hermes",
    ),
    Marker(
        "muse.exe binary",
        (b"muse",),
        re.compile(r"\bmuse\.exe\b", re.IGNORECASE),
        "spawn('muse.exe', args)",
        "the upstream binary is hermes",
    ),
    Marker(
        "muse-tip worktree",
        (b"muse",),
        re.compile(r"\bmuse-tip\b", re.IGNORECASE),
        r'Path(r"C:\Users\Dev\refs\muse-tip")',
        "a fork checkout path must not be baked into shipped source",
    ),
    Marker(
        "agent-name badge",
        (b"muse",),
        re.compile(BADGE_EITHER + BADGE_GAP + r"muse\b", re.IGNORECASE),
        BADGE_GLYPH + " muse",
        "the agent badge reads hermes",
        True,
        False,   # a path cannot carry the glyph meaningfully
    ),
    Marker(
        "/jp slash command",
        (b"/jp",),
        # Delimiter-anchored so it cannot fire on a path segment ("docs/jp/"),
        # on the Azure region prefix "ap./apac./jp." (model_setup_flows.py:76),
        # or on the "Noto Sans KR/SC/JP" font subset that makes a bare \bJP\b
        # unusable. KNOWN RISK: a future Japanese route spelled href="/jp" would
        # match. If one lands, pin it in UPSTREAM_LEGITIMATE and drop the quote
        # characters from the delimiter class -- do not delete the marker.
        re.compile(r"""(?:^|[\s"'`(\[|>])/jp\b""", re.IGNORECASE),
        'register_slash_command("/jp")',
        "the fork's slash command has no upstream counterpart; remove it",
        True,
        False,   # "/jp" leading a path is a locale directory, not a command
    ),
    Marker(
        "Work Packet doc ref",
        (b"work packet", b"work-packet", b"work_packet"),
        # Case-INsensitive, and verified safe: the leading \b is what spares the
        # only near-miss in the tree, "Network packet processing pipelines"
        # (optional-skills/creative/concept-diagrams/examples/
        # cpu-ooo-microarchitecture.md:234) -- there is no word boundary between
        # "Net" and "work". Same for "Rework packets" and "framework packet".
        # Fork provenance rather than product identity, but it travels on the
        # same line as both M.U.S.E. leaks, so it is the same seam.
        re.compile(r"\bwork[ _-]packet\b", re.IGNORECASE),
        "Credential scanner - Work Packet 9.2, 4.1, Appendix A.",
        "cite a document that exists in this repo, or drop the citation",
    ),
    Marker(
        "fork author home dir",
        (b"echer",),
        # Both separators, the doubled backslash a JSON or source literal leaves
        # behind ("C:\\\\Users\\\\Echer"), and the POSIX home. Safe to widen
        # this far only because gitignored junk is out of scope --
        # test_durations.json carries 19 such lines.
        re.compile(r"users[\\/]{1,2}echer\b|/home/echer\b", re.IGNORECASE),
        r"C:\Users\Echer\hermes-agent",
        "no absolute path from the fork author's machine may ship",
    ),
    Marker(
        "muse path segment",
        (b"muse",),
        # Path-shaped only: a directory or file literally named "muse".
        # Deliberately does not match "muse-spark.json" or "musehq". Not applied
        # to content, where a bare line "muse" is ordinary English.
        re.compile(r"(?:^|/)muse(?:/|\.[A-Za-z0-9]+$|$)", re.IGNORECASE),
        "assets/muse/logo.svg",
        "rename the path to its hermes equivalent",
        False,
        True,
    ),
)

# Union of the marker tokens. A file whose lowercased bytes contain none of
# these cannot match any marker, so it is never decoded.
PREFILTER_TOKENS: tuple[bytes, ...] = tuple(
    sorted({t for m in MARKERS for t in m.tokens})
)


def _present_tokens(raw: bytes) -> set[bytes]:
    lowered = raw.lower()
    return {token for token in PREFILTER_TOKENS if token in lowered}


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------
# Real upstream lines, one per trap the naive gate falls into. Every marker must
# stay silent on all of them. This is the executable form of "judge the meaning,
# not the substring".
UPSTREAM_LEGITIMATE: tuple[tuple[str, str], ...] = (
    ('aliases=("meta", "muse", "muse-spark", "model-api", "msl"),',
     "Meta Muse Spark: 'muse' is a live provider alias"),
    ('"id": "meta/muse-spark-1.2"', "Meta Muse Spark model id"),
    ('assert data_training_warning("MUSE-SPARK-1.2-CONTRIBUTOR") is not None',
     "uppercase Muse Spark in a case-insensitivity fixture"),
    ('default_aux_model="muse-spark-1.2-contributor",',
     "lowercase Muse Spark contributor tier"),
    ("description: Meta Model API - Muse Spark family (Meta Superintelligence Labs)",
     "Muse Spark provider plugin description"),
    ("hermes chat --provider meta-ai --model muse-spark-1.2",
     "documented Muse Spark invocation"),
    ("Inspired by Muse Code's ``--subagent-worktree-isolation`` (Meta, Aug 2026):",
     "Muse Code prior-art credit; capitalised 'Muse' standing alone"),
    ("(https://dev.meta.ai/docs/muse-code/extending#multi-agent); no Muse Code",
     "Muse Code documentation URL"),
    ("- **BCI hardware**: Muse 2, Muse S, or OpenBCI (4-channel EEG + PPG + IMU via BLE)",
     "Muse EEG headband hardware"),
    ('"name": "Muse-A1B2",', "Muse EEG device name"),
    ('{"event": "muse-status"}', "Muse EEG websocket event"),
    ('{"personality":"creative","headline":"The muse is patched in"}',
     "the ordinary English noun, upstream desktop intro copy"),
    ("#: Meta Model API (Muse): minimal..xhigh; rejects ``none``.",
     "bare title-case Muse as the Meta family shorthand"),
    ("The Louvre museum is in", "'museum' substring"),
    ("SQLITE_STATUS_MEMUSED", "MEMUSED substring in vendored sqlite3.h"),
    ("randomuser2026x@proton.me", "'randomuser' substring"),
    ("class SpectrumUser(TypedDict):", "'SpectrumUser' substring"),
    ('body["FromUserName"]', "'FromUserName' substring"),
    ("class TestVacuumUsesPassive:", "'VacuumUses' substring"),
    ("def test_muse_launcher_x():",
     "'muse' after a word char: the \\b must not hold, or MEMUSED falls too"),
    ("CONTAINER_TERMINAL_BACKENDS = new Set(['docker','ssh','singularity','modal'])",
     "Singularity/Apptainer container runtime, an upstream terminal backend"),
    ("'terminal.singularity_image': singularityImage,", "Singularity image setting"),
    ("HERMES_CADUCEUS = CADUCEUS_ART",
     "the caduceus is Hermes's own staff: upstream branding"),
    ("export const caduceus = CADUCEUS_ART;", "upstream TUI banner art"),
    ('wake_word: "hey_jarvis"', "openWakeWord built-in wake word"),
    ("setApiRequestProfile('jarvis')", "arbitrary desktop test profile fixture"),
    ("@jarvis_bot", "Telegram bot-handle example"),
    ("PrimeIntellect-ai/prime-agent", "'prime' in an upstream port credit"),
    ("# prime the cache before the first turn", "'prime' as a verb"),
    ('toolset = "web-search-prime"', "'prime' in an upstream toolset name"),
    ("from hermes_cli.prime.tokenjuice import squeeze",
     "'prime' is the *de-branded* module name and must not be flagged"),
    ("- Network packet processing pipelines",
     "'work packet' inside 'Network packet' -- the real upstream near-miss"),
    ("Rework packets are re-queued", "'work packet' inside 'Rework packets'"),
    ("framework packet loss budget", "'work packet' inside 'framework packet'"),
    ('"ap./apac./jp. profile spellings"', "Azure region prefix, not the /jp command"),
    ("- Noto Sans KR/SC/JP", "font subset: why a bare \\bJP\\b is unusable"),
    (BADGE_GLYPH + " focus", "upstream focus-mode status badge"),
    (BADGE_GLYPH + " STT", "upstream speech-to-text status badge"),
    ("faces = ['" + BADGE_GLYPH + "_" + BADGE_GLYPH + "']", "upstream kaomoji"),
    ("reviewed as a class: recovered-agent-sources/", "generic archive-path heuristic"),
    ("hermes-places-plugin/1.0 (+https://github.com/NousResearch/hermes-agent)",
     "already-de-branded plugin User-Agent"),
    ('"allowed_repositories": ["octo/cat"]', "the neutral GitHub placeholder"),
)

# Paths that must not trip the path half of the scan.
UPSTREAM_LEGITIMATE_PATHS: tuple[tuple[str, str], ...] = (
    ("plugins/model-providers/meta-ai/__init__.py", "the Muse Spark provider plugin"),
    ("plugins/model-providers/meta-ai/muse-spark.json",
     "a hypothetical Muse Spark data file: 'muse' must need its own segment"),
    ("optional-skills/health/neuroskill-bci/SKILL.md", "the Muse EEG skill"),
    ("tools/wakewords/hey_hermes.onnx", "wake-word asset beside hey_jarvis"),
    ("hermes_cli/prime/tokenjuice.py", "the de-branded prime module"),
    ("website/docs/reference/cli-symbols.md", "upstream glyph reference"),
    ("contributors/emails/randomuser2026x@proton.me", "a contributor filename"),
    ("locales/ja/jp.json", "a locale path, not the /jp command"),
    ("tests/tools/test_subagent_worktree.py", "Muse Code prior-art test"),
)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def _git_tracked() -> list[str] | None:
    """Paths git tracks, POSIX-relative. None when git is unavailable (a source
    tarball, a vendored copy), which drops us to the os.walk fallback."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    paths = [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]
    return paths or None


def _walked() -> list[str]:
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(REPO_ROOT).as_posix()
        prefix = "" if rel_dir == "." else rel_dir + "/"
        paths.extend(prefix + name for name in filenames)
    return paths


def _in_scope(rel: str) -> bool:
    if rel in ALLOWLIST:
        return False
    if any(rel == skip or rel.startswith(skip + "/") for skip in SKIP_RELDIRS):
        return False
    name = rel.rsplit("/", 1)[-1]
    if name in SKIP_NAMES:
        return False
    return Path(rel).suffix.lower() not in BINARY_SUFFIXES


def _decode(raw: bytes) -> str | None:
    """Text of a file, or None when it is binary. UTF-16 is decoded rather than
    skipped: a scanner that only sniffs for NUL would let a UTF-16 leak past in
    silence, and Windows tooling emits UTF-16 readily."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")


def _ascii(text: str) -> str:
    """Excerpts land in a pytest message that may be written to a cp1252
    console. Keep them printable so the guard can never fail to report."""
    return text.encode("ascii", "replace").decode("ascii")


def _scan() -> list[tuple[str, int, str, str]]:
    """Return (relpath, lineno, marker name, excerpt), sorted. Line 0 means the
    branding is in the path itself, or spans lines."""
    offences: list[tuple[str, int, str, str]] = []
    for rel in _git_tracked() or _walked():
        if not _in_scope(rel):
            continue

        for marker in MARKERS:
            if marker.paths and marker.rx.search(rel):
                offences.append((rel, 0, marker.name, _ascii("<path> " + rel)))

        try:
            raw = (REPO_ROOT / rel).read_bytes()
        except OSError:
            continue  # tracked but absent (sparse checkout) or unreadable
        present = _present_tokens(raw)
        if not present:
            continue
        candidates = [
            m for m in MARKERS
            if m.content and any(t in present for t in m.tokens)
        ]
        if not candidates:
            continue
        text = _decode(raw)
        if text is None:
            continue
        hot = [m for m in candidates if m.rx.search(text)]
        if not hot:
            continue
        lines = text.splitlines()
        for marker in hot:
            seen = False
            for lineno, line in enumerate(lines, 1):
                if marker.rx.search(line):
                    seen = True
                    offences.append(
                        (rel, lineno, marker.name, _ascii(line.strip()[:120]))
                    )
            if not seen:
                # Matched the file but no single line: a multi-line match. Still
                # a leak; never let it fall off the report.
                offences.append((rel, 0, marker.name, "<spans multiple lines>"))
    offences.sort()
    return offences


@pytest.fixture(scope="module")
def branding_scan() -> list[tuple[str, int, str, str]]:
    return _scan()


def test_no_fork_branding(branding_scan):
    offences = branding_scan
    fired = sorted({name for _p, _l, name, _x in offences})
    legend = "\n".join(f"  {m.name}: {m.fix}" for m in MARKERS if m.name in fired)
    listing = "\n".join(
        f"  {p}:{ln}: [{name}] {excerpt}" for p, ln, name, excerpt in offences
    )
    assert not offences, (
        f"{len(offences)} line(s) carry downstream-fork branding.\n"
        "Every marker here has zero occurrences at the pristine upstream tip, so "
        "a hit is a real leak -- it cannot be Meta's Muse Spark, the Muse EEG "
        "skill, the Singularity/Apptainer backend, HERMES_CADUCEUS or "
        "openWakeWord's hey_jarvis. Those are pinned as negative controls in "
        "test_markers_spare_upstream_strings.\n"
        "A line number of 0 means the file's PATH carries the branding: rename "
        "the file or directory.\n"
        "Fix the source. Do NOT widen ALLOWLIST to make this pass: an allowlist "
        "entry is a standing permission for branding to ship, and is only ever "
        "correct for a file whose purpose is to enumerate fork markers.\n\n"
        f"{listing}\n\nHow to de-brand each marker:\n{legend}"
    )


def test_every_marker_matches_its_own_sample():
    """A marker that does not match the leak it documents is decoration, and a
    marker whose prefilter tokens are absent from its own matches is worse: the
    scan skips the file and the marker is silently dead. Both are pinned here
    because both nearly happened -- "M.U.S.E." contains no "muse" substring, and
    its two known leaks are reachable only because those same lines also happen
    to say "Work Packet"."""
    broken: list[str] = []
    for marker in MARKERS:
        if not marker.rx.search(marker.sample):
            broken.append(f"{marker.name}: regex does not match its own sample")
            continue
        sample_bytes = marker.sample.encode("utf-8", "replace").lower()
        if not any(token in sample_bytes for token in marker.tokens):
            broken.append(
                f"{marker.name}: none of its prefilter tokens {marker.tokens!r} "
                f"appear in the sample it must catch -- the scan would never "
                f"decode the file"
            )
    assert not broken, (
        "Marker definitions are internally inconsistent; the scan would miss "
        "real leaks:\n" + "\n".join(f"  {b}" for b in broken)
    )


@pytest.mark.parametrize(
    "text,why", UPSTREAM_LEGITIMATE, ids=[why for _text, why in UPSTREAM_LEGITIMATE]
)
def test_markers_spare_upstream_strings(text, why):
    """Upstream legitimately ships "muse", "singularity", "caduceus", "jarvis"
    and U+25C9. If a marker starts eating them the guard becomes noise and
    someone will delete it -- or worse, "fix" upstream code to appease it."""
    hits = [m.name for m in MARKERS if m.content and m.rx.search(text)]
    assert not hits, (
        f"Marker(s) {hits} fire on an upstream-legitimate string.\n"
        f"  string: {_ascii(text)}\n"
        f"  why it is legitimate: {why}\n"
        "Narrow the marker. A branding guard that flags upstream's own strings "
        "is worse than no guard."
    )


@pytest.mark.parametrize(
    "relpath,why", UPSTREAM_LEGITIMATE_PATHS,
    ids=[why for _p, why in UPSTREAM_LEGITIMATE_PATHS],
)
def test_path_markers_spare_upstream_paths(relpath, why):
    """The path half of the scan has its own false-positive surface: a path is a
    much shorter string, so a loose marker bites harder there."""
    hits = [m.name for m in MARKERS if m.paths and m.rx.search(relpath)]
    assert not hits, (
        f"Marker(s) {hits} fire on an upstream-legitimate path.\n"
        f"  path: {relpath}\n  why it is legitimate: {why}\n"
        "Narrow the marker, or set paths=False on it."
    )


def test_allowlist_has_no_dead_entries():
    """A whole-file allowlist entry pointing at nothing allowlists nothing, and
    hides that the file it was written for moved or was renamed."""
    missing = [
        f"{path} ({reason})"
        for path, reason in sorted(ALLOWLIST.items())
        if path not in PENDING_PATHS and not (REPO_ROOT / path).is_file()
    ]
    assert not missing, (
        "ALLOWLIST names files that do not exist. Delete the entry, or correct "
        "the path if the file moved:\n" + "\n".join(f"  {m}" for m in missing)
    )
