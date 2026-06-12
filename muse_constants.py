"""Shared constants for Hermes Agent.

Import-safe module with no dependencies — can be imported from anywhere
without risk of circular imports.
"""

import os
import sysconfig
from contextvars import ContextVar, Token
from pathlib import Path


_profile_fallback_warned: bool = False
_legacy_home_env_warned: bool = False
_UNSET = object()
_HERMES_HOME_OVERRIDE: ContextVar[str | object] = ContextVar(
    "_HERMES_HOME_OVERRIDE", default=_UNSET
)


def env_first(new: str, old: str) -> str | None:
    """Read an env var under its canonical MUSE_* name, then the legacy
    HERMES_* name.

    Returns the first non-empty value (empty/whitespace counts as unset,
    matching the ``.strip()`` convention used throughout). Both names are
    supported forever; this helper is the pattern for any future
    MUSE_*/HERMES_* pair.
    """
    for key in (new, old):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


def _warn_legacy_home_env_once() -> None:
    """One-shot DeprecationWarning when only the legacy HERMES_HOME is set."""
    global _legacy_home_env_warned
    if _legacy_home_env_warned:
        return
    _legacy_home_env_warned = True
    import warnings

    warnings.warn(
        "HERMES_HOME is deprecated; set MUSE_HOME instead "
        "(both names are honored forever; MUSE_HOME wins when both are set)",
        DeprecationWarning,
        stacklevel=3,
    )


def _sync_legacy_env_aliases() -> None:
    """Mirror MUSE_* values onto the legacy HERMES_* names (one-way).

    Many modules and standalone scripts read ``HERMES_HOME`` /
    ``HERMES_QUIET`` from the environment directly. When a user configures
    only the canonical MUSE_* names, mirroring them onto the legacy names at
    import time keeps every such reader working without touching ~90 call
    sites. The mirror is deliberately one-way (new -> old, setdefault only):
    mirroring old -> new would freeze a stale MUSE_HOME ahead of later
    HERMES_HOME changes (e.g. per-test monkeypatching) and invert precedence.
    """
    for new, old in (("MUSE_HOME", "HERMES_HOME"), ("MUSE_QUIET", "HERMES_QUIET")):
        val = os.environ.get(new, "").strip()
        if val:
            os.environ.setdefault(old, val)


_sync_legacy_env_aliases()


def _default_native_home() -> Path:
    """Default state dir: ``~/.muse`` (canonical), ``~/.hermes`` (legacy).

    Resolution: an existing ``~/.muse`` wins; otherwise an existing legacy
    ``~/.hermes`` is used (pre-migration installs); fresh installs get
    ``~/.muse``. Deterministic whether or not the one-shot migration has
    run in this process.
    """
    home = Path.home()
    muse = home / ".muse"
    if muse.exists():
        return muse
    hermes = home / ".hermes"
    if hermes.exists():
        return hermes
    return muse


_legacy_home_migrated: bool = False


def ensure_legacy_home_symlink() -> None:
    """Backfill the ``~/.hermes`` → ``~/.muse`` compat symlink when missing.

    Fresh installs create only ``~/.muse``; a long tail of standalone
    scripts, plugins and external tooling still reads ``~/.hermes``
    directly. Keeping a symlink there means every such reader resolves to
    the same state dir forever. No-op when env-configured, when ``~/.muse``
    doesn't exist, or when anything already occupies ``~/.hermes``.
    """
    if get_hermes_home_override() or env_first("MUSE_HOME", "HERMES_HOME"):
        return
    home = Path.home()
    new_home = home / ".muse"
    old_home = home / ".hermes"
    if not new_home.is_dir():
        return
    if old_home.exists() or old_home.is_symlink():
        return
    try:
        os.symlink(new_home, old_home, target_is_directory=True)
    except OSError:
        pass


def migrate_legacy_home_once() -> Path | None:
    """One-shot, idempotent ``~/.hermes`` → ``~/.muse`` state-dir migration.

    Called from process entry points (CLI main, agent runner, ACP entry, MCP
    server) and from ``ensure_hermes_home()``. Strategy: atomic ``os.rename``
    of the real directory to ``~/.muse``, write a ``.migrated_from_hermes``
    breadcrumb, then leave a compat symlink at ``~/.hermes`` so legacy
    scripts, docs and container mounts keep resolving. Never copies, never
    clobbers an existing ``~/.muse``, and never runs when an explicit
    MUSE_HOME/HERMES_HOME (or context override) is in effect or the install
    is package-managed. Concurrency-safe: ``os.rename`` is atomic and the
    loser of a race finds ``~/.muse`` already present.

    Returns the new path when a migration actually happened, else ``None``.
    """
    global _legacy_home_migrated
    if _legacy_home_migrated:
        return None
    _legacy_home_migrated = True

    # Explicit configuration opts out — the configured dir is authoritative.
    if get_hermes_home_override() or env_first("MUSE_HOME", "HERMES_HOME"):
        return None
    if env_first("MUSE_MANAGED", "HERMES_MANAGED"):
        return None

    home = Path.home()
    new_home = home / ".muse"
    old_home = home / ".hermes"
    if new_home.exists() or new_home.is_symlink():
        # Never clobber; but backfill the legacy compat symlink when nothing
        # occupies ~/.hermes (fresh installs that never had a Hermes home).
        ensure_legacy_home_symlink()
        return None
    if old_home.is_symlink() or not old_home.is_dir():
        return None  # nothing to migrate (or already a compat symlink)
    if (old_home / ".managed").exists():
        return None  # package-manager-owned layout (NixOS/Homebrew)

    try:
        os.rename(old_home, new_home)
    except OSError:
        return None  # permissions / concurrent migration — keep using ~/.hermes

    try:
        from datetime import datetime, timezone

        (new_home / ".migrated_from_hermes").write_text(
            "migrated from ~/.hermes at "
            f"{datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )
    except OSError:
        pass

    try:
        os.symlink(new_home, old_home, target_is_directory=True)
    except OSError:
        pass  # legacy path stays absent; _default_native_home finds ~/.muse

    return new_home


def set_hermes_home_override(path: str | Path | None) -> Token:
    """Set a context-local Hermes home override and return its reset token.

    This is for in-process, per-task scoping.  It deliberately does not mutate
    ``os.environ`` because that is shared by every thread in the process.
    """
    value: str | object = _UNSET if path is None else str(path)
    return _HERMES_HOME_OVERRIDE.set(value)


def reset_hermes_home_override(token: Token) -> None:
    """Restore the previous context-local Hermes home override."""
    _HERMES_HOME_OVERRIDE.reset(token)


def get_hermes_home_override() -> str | None:
    """Return the active context-local Hermes home override, if any."""
    override = _HERMES_HOME_OVERRIDE.get()
    if override is _UNSET or not override:
        return None
    return str(override)


def get_hermes_home() -> Path:
    """Return the MUSE home directory (default: ~/.hermes).

    Reads the MUSE_HOME env var first, then the legacy HERMES_HOME, then
    falls back to ~/.hermes. Both env names are honored forever; MUSE_HOME
    wins when both are set. ``get_muse_home`` is the canonical alias.
    This is the single source of truth — all other copies should import this.

    When ``HERMES_HOME`` is unset but an ``active_profile`` file indicates
    a non-default profile is active, logs a loud one-shot warning to
    ``errors.log`` so cross-profile data corruption is diagnosable instead
    of silent.  Behavior is unchanged otherwise — we still return
    ``~/.hermes`` — because raising here would brick 30+ module-level
    callers that import this at load time.  Subprocess spawners are
    expected to propagate ``HERMES_HOME`` explicitly (see the systemd
    template in ``muse_cli/gateway.py`` and the kanban dispatcher in
    ``muse_cli/kanban_db.py``).  See https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/issues/18594.
    """
    override = get_hermes_home_override()
    if override:
        return Path(override)

    val = os.environ.get("MUSE_HOME", "").strip()
    if val:
        return Path(val)

    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        _warn_legacy_home_env_once()
        return Path(val)

    # Guard: if a non-default profile is sticky-active, warn once that
    # the fallback to the default profile is almost certainly wrong.
    global _profile_fallback_warned
    if not _profile_fallback_warned:
        try:
            # Inline the default-root resolution from get_default_hermes_root()
            # to stay import-safe (this function is called from module scope
            # in 30+ files; we cannot afford to trigger logging setup here).
            active_path = _default_native_home() / "active_profile"
            active = active_path.read_text().strip() if active_path.exists() else ""
        except (UnicodeDecodeError, OSError):
            active = ""
        if active and active != "default":
            _profile_fallback_warned = True
            # Write directly to stderr.  We intentionally do NOT route this
            # through ``logging`` because (a) this function is called at
            # module-import time from 30+ sites, often before logging is
            # configured, and (b) root-logger propagation would double-emit
            # on consoles where a StreamHandler is already attached.
            import sys
            msg = (
                f"[HERMES_HOME fallback] HERMES_HOME is unset but active "
                f"profile is {active!r}. Falling back to ~/.hermes, which "
                f"is the DEFAULT profile — not {active!r}. Any data this "
                f"process writes will land in the wrong profile. The "
                f"subprocess spawner should pass HERMES_HOME explicitly "
                f"(see issue #18594)."
            )
            try:
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
            except Exception:
                pass

    return _default_native_home()


def get_default_hermes_root() -> Path:
    """Return the root Hermes directory for profile-level operations.

    In standard deployments this is ``~/.hermes``.

    In Docker or custom deployments where ``HERMES_HOME`` points outside
    ``~/.hermes`` (e.g. ``/opt/data``), returns ``HERMES_HOME`` directly
    — that IS the root.

    In profile mode where ``HERMES_HOME`` is ``<root>/profiles/<name>``,
    returns ``<root>`` so that ``profile list`` can see all profiles.
    Works both for standard (``~/.hermes/profiles/coder``) and Docker
    (``/opt/data/profiles/coder``) layouts.

    Import-safe — no dependencies beyond stdlib.
    """
    native_home = _default_native_home()
    env_home = env_first("MUSE_HOME", "HERMES_HOME") or ""
    if not env_home:
        return native_home
    env_path = Path(env_home)
    try:
        env_path.resolve().relative_to(native_home.resolve())
        # HERMES_HOME is under ~/.hermes (normal or profile mode)
        return native_home
    except ValueError:
        pass

    # Docker / custom deployment.
    # Check if this is a profile path: <root>/profiles/<name>
    # If the immediate parent dir is named "profiles", the root is
    # the grandparent — this covers Docker profiles correctly.
    if env_path.parent.name == "profiles":
        return env_path.parent.parent

    # Not a profile path — HERMES_HOME itself is the root
    return env_path


def _get_packaged_data_dir(name: str) -> Path | None:
    """Return an installed data-files directory if one exists.

    Used to discover bundled skills/optional-skills when Hermes is installed
    from a wheel that emitted them via setuptools data_files.
    """
    candidates = []
    for scheme in ("data", "purelib", "platlib"):
        raw = sysconfig.get_path(scheme)
        if raw:
            candidates.append(Path(raw) / name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_optional_skills_dir(default: Path | None = None) -> Path:
    """Return the optional-skills directory, honoring package-manager wrappers.

    Packaged installs may ship ``optional-skills`` outside the Python package
    tree and expose it via ``HERMES_OPTIONAL_SKILLS``.
    """
    override = os.getenv("HERMES_OPTIONAL_SKILLS", "").strip()
    if override:
        return Path(override)
    packaged = _get_packaged_data_dir("optional-skills")
    if packaged is not None:
        return packaged
    if default is not None:
        return default
    return get_hermes_home() / "optional-skills"


def get_optional_mcps_dir(default: Path | None = None) -> Path:
    """Return the optional-mcps directory, honoring package-manager wrappers.

    Mirrors :func:`get_optional_skills_dir` for the MCP catalog (Nous-approved
    Model Context Protocol servers shipped with the repo but disabled by
    default). Packaged installs may ship ``optional-mcps`` outside the Python
    package tree and expose it via ``HERMES_OPTIONAL_MCPS``.
    """
    override = os.getenv("HERMES_OPTIONAL_MCPS", "").strip()
    if override:
        return Path(override)
    packaged = _get_packaged_data_dir("optional-mcps")
    if packaged is not None:
        return packaged
    if default is not None:
        return default
    return get_hermes_home() / "optional-mcps"


def get_bundled_skills_dir(default: Path | None = None) -> Path:
    """Return the bundled skills directory for source and packaged installs.

    Resolution order:
        1. ``HERMES_BUNDLED_SKILLS`` env var (Nix wrapper / explicit override)
        2. Wheel-installed ``<sysconfig data>/skills`` (pip install path)
        3. Caller-supplied ``default`` (typically the source-checkout path)
        4. ``<HERMES_HOME>/skills`` last-resort
    """
    override = os.getenv("HERMES_BUNDLED_SKILLS", "").strip()
    if override:
        return Path(override)
    packaged = _get_packaged_data_dir("skills")
    if packaged is not None:
        return packaged
    if default is not None:
        return default
    return get_hermes_home() / "skills"


def get_hermes_dir(new_subpath: str, old_name: str) -> Path:
    """Resolve a Hermes subdirectory with backward compatibility.

    New installs get the consolidated layout (e.g. ``cache/images``).
    Existing installs that already have the old path (e.g. ``image_cache``)
    keep using it — no migration required.

    Args:
        new_subpath: Preferred path relative to HERMES_HOME (e.g. ``"cache/images"``).
        old_name: Legacy path relative to HERMES_HOME (e.g. ``"image_cache"``).

    Returns:
        Absolute ``Path`` — old location if it exists on disk, otherwise the new one.
    """
    home = get_hermes_home()
    old_path = home / old_name
    if old_path.exists():
        return old_path
    return home / new_subpath


def display_hermes_home() -> str:
    """Return a user-friendly display string for the current HERMES_HOME.

    Uses ``~/`` shorthand for readability::

        default:  ``~/.hermes``
        profile:  ``~/.hermes/profiles/coder``
        custom:   ``/opt/hermes-custom``

    Use this in **user-facing** print/log messages instead of hardcoding
    ``~/.hermes``.  For code that needs a real ``Path``, use
    :func:`get_hermes_home` instead.
    """
    home = get_hermes_home()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)


def secure_parent_dir(path: Path) -> None:
    """Chmod ``0o700`` on the parent directory of *path*, but only if safe.

    Refuses to chmod ``/`` or any top-level directory (resolved parent with
    fewer than 3 parts, i.e. ``/`` or any direct child like ``/usr``) to
    prevent catastrophic host bricking when ``HERMES_HOME`` or other path
    env vars resolve to an unexpected location.

    See https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/issues/25821.
    """
    parent = path.parent.resolve()
    # Refuse root and its direct children (/usr, /home, /var, /tmp, …).
    if parent == Path("/") or len(parent.parts) < 3:
        return
    try:
        os.chmod(parent, 0o700)
    except OSError:
        pass


def get_subprocess_home() -> str | None:
    """Return a per-profile HOME directory for subprocesses, or None.

    When ``{HERMES_HOME}/home/`` exists on disk, subprocesses should use it
    as ``HOME`` so system tools (git, ssh, gh, npm …) write their configs
    inside the Hermes data directory instead of the OS-level ``/root`` or
    ``~/``.  This provides:

    * **Docker persistence** — tool configs land inside the persistent volume.
    * **Profile isolation** — each profile gets its own git identity, SSH
      keys, gh tokens, etc.

    The Python process's own ``os.environ["HOME"]`` and ``Path.home()`` are
    **never** modified — only subprocess environments should inject this value.
    Activation is directory-based: if the ``home/`` subdirectory doesn't
    exist, returns ``None`` and behavior is unchanged.
    """
    hermes_home = get_hermes_home_override() or env_first("MUSE_HOME", "HERMES_HOME")
    if not hermes_home:
        return None
    profile_home = os.path.join(hermes_home, "home")
    if os.path.isdir(profile_home):
        return profile_home
    return None


VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")


def parse_reasoning_effort(effort: str) -> dict | None:
    """Parse a reasoning effort level into a config dict.

    Valid levels: "none", "minimal", "low", "medium", "high", "xhigh".
    Returns None when the input is empty or unrecognized (caller uses default).
    Returns {"enabled": False} for "none".
    Returns {"enabled": True, "effort": <level>} for valid effort levels.
    """
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None


def is_termux() -> bool:
    """Return True when running inside a Termux (Android) environment.

    Checks ``TERMUX_VERSION`` (set by Termux) or the Termux-specific
    ``PREFIX`` path.  Import-safe — no heavy deps.
    """
    prefix = os.getenv("PREFIX", "")
    return bool(os.getenv("TERMUX_VERSION") or "com.termux/files/usr" in prefix)


_wsl_detected: bool | None = None


def is_wsl() -> bool:
    """Return True when running inside WSL (Windows Subsystem for Linux).

    Checks ``/proc/version`` for the ``microsoft`` marker that both WSL1
    and WSL2 inject.  Result is cached for the process lifetime.
    Import-safe — no heavy deps.
    """
    global _wsl_detected
    if _wsl_detected is not None:
        return _wsl_detected
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            _wsl_detected = "microsoft" in f.read().lower()
    except Exception:
        _wsl_detected = False
    return _wsl_detected


_container_detected: bool | None = None


def is_container() -> bool:
    """Return True when running inside a Docker/Podman container.

    Checks ``/.dockerenv`` (Docker), ``/run/.containerenv`` (Podman),
    and ``/proc/1/cgroup`` for container runtime markers.  Result is
    cached for the process lifetime.  Import-safe — no heavy deps.
    """
    global _container_detected
    if _container_detected is not None:
        return _container_detected
    if os.path.exists("/.dockerenv"):
        _container_detected = True
        return True
    if os.path.exists("/run/.containerenv"):
        _container_detected = True
        return True
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8") as f:
            cgroup = f.read()
            if "docker" in cgroup or "podman" in cgroup or "/lxc/" in cgroup:
                _container_detected = True
                return True
    except OSError:
        pass
    _container_detected = False
    return False


# ─── Well-Known Paths ─────────────────────────────────────────────────────────


def get_config_path() -> Path:
    """Return the path to ``config.yaml`` under HERMES_HOME.

    Replaces the ``get_hermes_home() / "config.yaml"`` pattern repeated
    in 7+ files (skill_utils.py, muse_logging.py, muse_time.py, etc.).
    """
    return get_hermes_home() / "config.yaml"


def get_skills_dir() -> Path:
    """Return the path to the skills directory under HERMES_HOME."""
    return get_hermes_home() / "skills"



def get_env_path() -> Path:
    """Return the path to the ``.env`` file under HERMES_HOME."""
    return get_hermes_home() / ".env"


# ─── Network Preferences ─────────────────────────────────────────────────────


def apply_ipv4_preference(force: bool = False) -> None:
    """Monkey-patch ``socket.getaddrinfo`` to prefer IPv4 connections.

    On servers with broken or unreachable IPv6, Python tries AAAA records
    first and hangs for the full TCP timeout before falling back to IPv4.
    This affects httpx, requests, urllib, the OpenAI SDK — everything that
    uses ``socket.getaddrinfo``.

    When *force* is True, patches ``getaddrinfo`` so that calls with
    ``family=AF_UNSPEC`` (the default) resolve as ``AF_INET`` instead,
    skipping IPv6 entirely.  If no A record exists, falls back to the
    original unfiltered resolution so pure-IPv6 hosts still work.

    Safe to call multiple times — only patches once.
    Set ``network.force_ipv4: true`` in ``config.yaml`` to enable.
    """
    if not force:
        return

    import socket

    # Guard against double-patching
    if getattr(socket.getaddrinfo, "_hermes_ipv4_patched", False):
        return

    _original_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0:  # AF_UNSPEC — caller didn't request a specific family
            try:
                return _original_getaddrinfo(
                    host, port, socket.AF_INET, type, proto, flags
                )
            except socket.gaierror:
                # No A record — fall back to full resolution (pure-IPv6 hosts)
                return _original_getaddrinfo(host, port, family, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    _ipv4_getaddrinfo._hermes_ipv4_patched = True  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    socket.getaddrinfo = _ipv4_getaddrinfo  # type: ignore[assignment]  # ty: ignore[invalid-assignment]


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"

AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"


# ─── Canonical MUSE aliases ──────────────────────────────────────────────────
# `muse` is the canonical identity; the hermes-named functions above are kept
# forever for compatibility (imported from hundreds of sites and patched by
# string in tests). New code should prefer these names.

get_muse_home = get_hermes_home
get_muse_home_override = get_hermes_home_override
set_muse_home_override = set_hermes_home_override
reset_muse_home_override = reset_hermes_home_override
get_default_muse_root = get_default_hermes_root
get_muse_dir = get_hermes_dir
display_muse_home = display_hermes_home
