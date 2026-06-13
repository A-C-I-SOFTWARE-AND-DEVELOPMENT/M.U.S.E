"""Guard: the `muse sync` target set must stay in sync between the CLI's
``VALID_TARGETS`` and the ``sync-main-to-releases`` workflow's ``targets`` input
options. These live in different files and drift silently otherwise (add a
channel in one place, forget the other) — the AOS audit flagged this. This
locks them together.
"""

from pathlib import Path

import yaml

from hermes_cli.sync_releases import VALID_TARGETS

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "sync-main-to-releases.yml"
)


def _workflow_target_options() -> list[str]:
    doc = yaml.safe_load(WORKFLOW.read_text())
    # PyYAML parses the bare `on:` key as the boolean True on some versions.
    on = doc.get("on", doc.get(True))
    return on["workflow_dispatch"]["inputs"]["targets"]["options"]


def test_workflow_options_match_valid_targets():
    assert set(_workflow_target_options()) == set(VALID_TARGETS)


def test_valid_targets_is_canonical_set():
    # Pins the constant so an accidental edit to VALID_TARGETS is caught even if
    # someone updates the workflow to match. "all" must remain a member (the
    # CLI default and the fan-out-to-everything sentinel).
    assert set(VALID_TARGETS) == {"all", "android", "desktop", "source"}
    assert "all" in VALID_TARGETS
