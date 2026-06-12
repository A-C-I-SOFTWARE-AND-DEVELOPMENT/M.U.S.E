"""Tests for the MUSE CLI subcommands added in the CLI lane.

Covers ``proposals {list,approve,reject}`` and ``handoff``. The existing
subcommands (``perceive``, ``classify``, ``gate``, ``handle``, ``tick``)
are owned by their respective subsystem lanes and are not retested here.

Each test invokes the CLI through ``subprocess.run`` against
``sys.executable -m muse_cli.jarvis_prime`` so the full argparse +
handler path is exercised end-to-end, including exit codes and stderr
messages.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = [sys.executable, "-m", "muse_cli.jarvis_prime"]


def _run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        CLI + args,
        cwd=REPO_ROOT,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _proposal_dict(
    *,
    kind: str = "skill_update",
    target_path: str = "skills/foo/SKILL.md",
    created_at: str = "2026-05-25T20:00:00+00:00",
    risk_class: str = "RC1",
) -> dict[str, object]:
    return {
        "kind": kind,
        "target_path": target_path,
        "rationale": "test rationale",
        "diff_intent": "test diff intent",
        "evidence": [],
        "risk_class": risk_class,
        "requires_owner_approval": True,
        "status": "proposed",
        "created_at": created_at,
        "resolved_at": None,
        "owner_decision_note": None,
    }


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fresh HERMES_HOME pointing at a tmp dir. Returns the dir."""

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Always start without the env-var version of the phrase so tests
    # opt in explicitly when they want to exercise that path.
    monkeypatch.delenv("JARVIS_OWNER_PHRASE", raising=False)
    return tmp_path


@pytest.fixture()
def proposals_jsonl(hermes_home: Path) -> Path:
    """Path to the per-test proposals JSONL store (file not yet created)."""

    return hermes_home / "jarvis_prime" / "proposals.jsonl"


def _seed(proposals_jsonl: Path, items: list[dict[str, object]]) -> None:
    proposals_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with proposals_jsonl.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item))
            fh.write("\n")


def _compute_id(prop: dict[str, object]) -> str:
    """Mirror the CLI's _proposal_id so tests don't import private symbols."""

    import hashlib

    raw = (
        f"{prop.get('kind', '')}|"
        f"{prop.get('target_path', '')}|"
        f"{prop.get('created_at', '')}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------------------
# proposals list
# ---------------------------------------------------------------------------


def test_proposals_list_empty_store(hermes_home: Path) -> None:
    result = _run(["proposals", "list"], env={"HERMES_HOME": str(hermes_home)})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "no pending proposals"


def test_proposals_list_populated(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [
        _proposal_dict(kind="skill_update", target_path="skills/a/SKILL.md"),
        _proposal_dict(
            kind="new_skill",
            target_path="skills/b/SKILL.md",
            created_at="2026-05-25T21:00:00+00:00",
            risk_class="RC2",
        ),
    ]
    _seed(proposals_jsonl, items)

    result = _run(["proposals", "list"], env={"HERMES_HOME": str(hermes_home)})
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert _compute_id(items[0]) in out
    assert _compute_id(items[1]) in out
    assert "skill_update @ skills/a/SKILL.md" in out
    assert "new_skill @ skills/b/SKILL.md" in out


def test_proposals_list_json_includes_id(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)

    result = _run(
        ["proposals", "list", "--json"], env={"HERMES_HOME": str(hermes_home)}
    )
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert len(parsed) == 1
    assert parsed[0]["id"] == _compute_id(items[0])
    assert parsed[0]["status"] == "proposed"


# ---------------------------------------------------------------------------
# proposals approve
# ---------------------------------------------------------------------------


def test_approve_without_phrase_refuses(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)
    pid = _compute_id(items[0])

    result = _run(
        ["proposals", "approve", pid], env={"HERMES_HOME": str(hermes_home)}
    )
    assert result.returncode == 1
    assert "owner authorization phrase required" in result.stderr

    # Status unchanged on disk.
    with proposals_jsonl.open("r", encoding="utf-8") as fh:
        line = fh.readline()
    assert json.loads(line)["status"] == "proposed"


def test_approve_with_wrong_phrase_refuses(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)
    pid = _compute_id(items[0])

    result = _run(
        ["proposals", "approve", pid, "--phrase", "yes with authorization"],
        env={"HERMES_HOME": str(hermes_home)},
    )
    assert result.returncode == 1
    assert "does not match" in result.stderr

    # Status unchanged.
    with proposals_jsonl.open("r", encoding="utf-8") as fh:
        line = fh.readline()
    assert json.loads(line)["status"] == "proposed"


def test_approve_with_exact_phrase_succeeds(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)
    pid = _compute_id(items[0])

    result = _run(
        ["proposals", "approve", pid, "--phrase", "Yes, with authorization."],
        env={"HERMES_HOME": str(hermes_home)},
    )
    assert result.returncode == 0, result.stderr
    assert pid in result.stdout
    assert "approved" in result.stdout

    # Status mutated on disk; resolved_at set; owner note recorded.
    with proposals_jsonl.open("r", encoding="utf-8") as fh:
        record = json.loads(fh.readline())
    assert record["status"] == "approved"
    assert record["resolved_at"] is not None
    assert record["owner_decision_note"] == "approved via CLI"


def test_approve_via_env_var(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)
    pid = _compute_id(items[0])

    result = _run(
        ["proposals", "approve", pid],
        env={
            "HERMES_HOME": str(hermes_home),
            "JARVIS_OWNER_PHRASE": "Yes, with authorization.",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "approved" in result.stdout

    with proposals_jsonl.open("r", encoding="utf-8") as fh:
        record = json.loads(fh.readline())
    assert record["status"] == "approved"


# ---------------------------------------------------------------------------
# proposals reject
# ---------------------------------------------------------------------------


def test_reject_does_not_require_phrase(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)
    pid = _compute_id(items[0])

    result = _run(
        ["proposals", "reject", pid], env={"HERMES_HOME": str(hermes_home)}
    )
    assert result.returncode == 0, result.stderr
    assert "rejected" in result.stdout

    with proposals_jsonl.open("r", encoding="utf-8") as fh:
        record = json.loads(fh.readline())
    assert record["status"] == "rejected"
    assert record["owner_decision_note"] == "rejected via CLI"


# ---------------------------------------------------------------------------
# unknown id failure mode
# ---------------------------------------------------------------------------


def test_unknown_proposal_id_fails(proposals_jsonl: Path, hermes_home: Path) -> None:
    items = [_proposal_dict()]
    _seed(proposals_jsonl, items)

    result = _run(
        [
            "proposals",
            "approve",
            "deadbeef00",
            "--phrase",
            "Yes, with authorization.",
        ],
        env={"HERMES_HOME": str(hermes_home)},
    )
    assert result.returncode == 1
    assert "unknown proposal" in result.stderr
    assert "deadbeef00" in result.stderr

    # Status of the real proposal unchanged.
    with proposals_jsonl.open("r", encoding="utf-8") as fh:
        record = json.loads(fh.readline())
    assert record["status"] == "proposed"


# ---------------------------------------------------------------------------
# proposals never execute owner-gated actions
# ---------------------------------------------------------------------------


def test_approve_does_not_execute_anything_external(
    proposals_jsonl: Path, hermes_home: Path, tmp_path: Path
) -> None:
    """Approve mutates the JSONL status field and nothing else.

    The lane charter forbids the CLI from executing owner-gated actions
    (deploys, merges, publishes, credential changes). This test asserts
    the file system outside the proposals store is untouched after an
    approve cycle.
    """

    items = [
        _proposal_dict(
            kind="self_runtime_update",
            target_path="muse_cli/jarvis_prime/awareness.py",
            risk_class="RC4",
        )
    ]
    _seed(proposals_jsonl, items)
    pid = _compute_id(items[0])

    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")

    result = _run(
        ["proposals", "approve", pid, "--phrase", "Yes, with authorization."],
        env={"HERMES_HOME": str(hermes_home)},
    )
    assert result.returncode == 0, result.stderr

    # Sentinel unchanged; no side effects on the repo tree.
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    # The target_path of the proposal was NOT modified by approval.
    target = REPO_ROOT / "muse_cli/jarvis_prime/awareness.py"
    before_mtime = target.stat().st_mtime
    # Approve again to be sure - it'll fail because the proposal is now
    # already approved but the underlying file must still not be touched.
    _run(
        ["proposals", "approve", pid, "--phrase", "Yes, with authorization."],
        env={"HERMES_HOME": str(hermes_home)},
    )
    assert target.stat().st_mtime == before_mtime


# ---------------------------------------------------------------------------
# handoff
# ---------------------------------------------------------------------------


def _write_packet(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "intent": "audit this repo",
                "owner_gated_actions": ["main_branch_merge"],
                "allowed_paths": ["docs/"],
                "non_goals": ["execute owner-gated actions"],
            }
        ),
        encoding="utf-8",
    )


def test_handoff_renders_safely(tmp_path: Path) -> None:
    packet = tmp_path / "packet.json"
    _write_packet(packet)

    result = _run(
        [
            "handoff",
            "--intent",
            "audit this repo",
            "--packet",
            str(packet),
            "--skip-perceive",
        ]
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Mission:" in out
    assert "Route selected:" in out
    assert "Owner gates:" in out
    assert "Result:" in out
    assert "Next step:" in out


def test_handoff_missing_packet_fails_cleanly(tmp_path: Path) -> None:
    nope = tmp_path / "nonexistent.json"
    result = _run(
        ["handoff", "--intent", "x", "--packet", str(nope), "--skip-perceive"]
    )
    assert result.returncode == 2
    assert "packet file not found" in result.stderr
    assert str(nope) in result.stderr


def test_handoff_invalid_json_fails_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json {", encoding="utf-8")

    result = _run(
        ["handoff", "--intent", "x", "--packet", str(bad), "--skip-perceive"]
    )
    assert result.returncode == 2
    assert "invalid JSON" in result.stderr
    assert str(bad) in result.stderr


def test_handoff_missing_intent_argparse_error(tmp_path: Path) -> None:
    packet = tmp_path / "packet.json"
    _write_packet(packet)

    result = _run(["handoff", "--packet", str(packet)])
    assert result.returncode == 2
    assert "--intent" in result.stderr


# ---------------------------------------------------------------------------
# Invalid JSONL in the proposals store fails cleanly
# ---------------------------------------------------------------------------


def test_proposals_list_invalid_jsonl_fails_cleanly(
    proposals_jsonl: Path, hermes_home: Path
) -> None:
    proposals_jsonl.parent.mkdir(parents=True, exist_ok=True)
    proposals_jsonl.write_text("this is not json\n", encoding="utf-8")

    result = _run(["proposals", "list"], env={"HERMES_HOME": str(hermes_home)})
    assert result.returncode == 2
    assert "invalid JSON" in result.stderr
