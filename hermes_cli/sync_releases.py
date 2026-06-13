"""``muse sync`` — push the current ``main`` to every release channel.

This is a thin, local-first trigger for the ``sync-main-to-releases`` GitHub
Actions workflow, which is the real engine (it holds the ``contents: write``
token and the build runners). Running ``muse sync`` dispatches that workflow
so the rolling release channels (``android-latest``, ``muse-desktop-latest``)
and the ``M.U.S.E`` source tag are refreshed to point at the current ``main``.

Design notes:
- We never hold release credentials locally; the workflow does the publish.
  This command only *asks* GitHub to run it (via ``gh workflow run``).
- If ``gh`` is missing or unauthenticated we degrade gracefully: print the
  exact command (and the Actions URL) the operator can run by hand instead of
  failing. That keeps the secret-free, local-first posture intact.
- ``--dry-run`` resolves the repo and prints what *would* be dispatched
  without touching anything — used by the unit tests and safe to run anywhere.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from hermes_cli.colors import Colors, color
from hermes_cli.github_publisher import PublisherError, get_repo_info

# The orchestrator workflow this command drives. Kept as a constant so the CLI,
# the tests, and the docs all reference one identifier.
WORKFLOW_FILE = "sync-main-to-releases.yml"

# Valid `--targets` values, mirrored by the workflow's `targets` input choices.
VALID_TARGETS = ("all", "android", "desktop", "source")


def _dispatch_command(slug: str, targets: str) -> list[str]:
    """The ``gh`` invocation that triggers the sync workflow on ``main``."""
    return [
        "gh",
        "workflow",
        "run",
        WORKFLOW_FILE,
        "--repo",
        slug,
        "--ref",
        "main",
        "-f",
        f"targets={targets}",
    ]


def cmd_sync(args) -> int:
    """Dispatch the ``sync-main-to-releases`` workflow.

    Returns a process exit code (0 = success / dry-run, non-zero = failure).
    """
    targets: str = getattr(args, "targets", "all") or "all"
    dry_run: bool = bool(getattr(args, "dry_run", False))

    if targets not in VALID_TARGETS:
        print(
            color(
                f"Unknown --targets '{targets}'. "
                f"Choose one of: {', '.join(VALID_TARGETS)}.",
                Colors.RED,
            )
        )
        return 2

    try:
        repo = get_repo_info()
    except PublisherError as exc:
        print(color(f"Cannot resolve git repository: {exc}", Colors.RED))
        return 1

    slug: Optional[str] = repo.slug
    if not slug:
        print(
            color(
                "origin is not a GitHub remote — cannot dispatch the sync "
                "workflow. Set a GitHub `origin` remote and retry.",
                Colors.RED,
            )
        )
        return 1

    cmd = _dispatch_command(slug, targets)
    printable = " ".join(cmd)
    actions_url = f"https://github.com/{slug}/actions/workflows/{WORKFLOW_FILE}"

    print(
        color("muse sync", Colors.CYAN)
        + f" → refresh release channels from main (targets: {targets})"
    )
    print(color(f"  repo:     {slug}", Colors.DIM))
    print(color(f"  workflow: {WORKFLOW_FILE} (ref: main)", Colors.DIM))

    if dry_run:
        print(color("  dry-run — would dispatch:", Colors.YELLOW))
        print(f"    {printable}")
        return 0

    if shutil.which("gh") is None:
        print(
            color(
                "  `gh` CLI not found. Trigger the sync by hand:",
                Colors.YELLOW,
            )
        )
        print(f"    {printable}")
        print(color(f"  …or from the Actions tab: {actions_url}", Colors.DIM))
        return 1

    try:
        subprocess.run(cmd, check=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(
            color(
                f"  `gh workflow run` failed (exit {exc.returncode}). "
                "If this is an auth error run `gh auth login`, or trigger it "
                f"from the Actions tab: {actions_url}",
                Colors.RED,
            )
        )
        return exc.returncode or 1

    print(
        color(
            "  dispatched ✓  watch it at:",
            Colors.GREEN,
        )
        + f" {actions_url}"
    )
    return 0
