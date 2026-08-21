"""Tests for the suppression builder.

The suppression file is an assertion about a human's judgement, so the code that
writes it has to be as testable as the scanner. These tests run against small
temporary trees, never the repository, so they stay fast.

Two of them guard against rot rather than bugs:
``test_hand_triaged_paths_still_exist`` fails if a hand-triaged file is moved or
deleted, and ``test_shipped_file_matches_the_recorded_triage_shape`` fails if
the shipped file drifts away from the recorded decisions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.security import build_suppressions as bs
from tools.security import secret_scan as ss

FAKE_AWS = "AKIA" + "NOTREALQ3M7XR2VB"
HIGH_ENTROPY = "7Zq3XvB9nKp2LdWs4TyH8mCe1RfJ6uGaX4pQ"


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "tests" / "test_client.py").write_text(
        f'TOKEN = "{FAKE_AWS}"\n', encoding="utf-8"
    )
    (root / "docs" / "setup.md").write_text(
        f'    api_key = "{HIGH_ENTROPY}"\n', encoding="utf-8"
    )
    (root / "app.py").write_text(f'api_key = "{HIGH_ENTROPY}"\n', encoding="utf-8")
    return root


def test_class_review_suppresses_and_unreviewed_does_not(tree: Path) -> None:
    doc, unresolved = bs.build(tree)
    paths = sorted(entry["path"] for entry in doc["suppressions"])
    assert paths == ["docs/setup.md", "tests/test_client.py"]
    assert unresolved == ["app.py:1 [generic_secret_assignment]"]

    buckets = {entry["path"]: entry["triage"] for entry in doc["suppressions"]}
    assert buckets["tests/test_client.py"] == "test_fixture"
    assert buckets["docs/setup.md"] == "doc_example"
    assert all(e["added_by"] == bs.BY_CLASS for e in doc["suppressions"])


def test_hand_entry_overrides_the_class_proposal(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(bs.HAND, "app.py:1", ("not_a_credential", "a sentinel"))
    doc, unresolved = bs.build(tree)
    assert unresolved == []
    entry = next(e for e in doc["suppressions"] if e["path"] == "app.py")
    assert entry["triage"] == "not_a_credential"
    assert entry["reason"] == "a sentinel"
    assert entry["added_by"] == bs.INDIVIDUAL


def test_hand_entry_keyed_by_path_alone(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Line-independent keys exist because line numbers drift as files change."""
    monkeypatch.setitem(bs.HAND, "app.py", ("doc_example", "a worked example"))
    (tree / "app.py").write_text(
        f'# a comment added above\n\napi_key = "{HIGH_ENTROPY}"\n', encoding="utf-8"
    )
    doc, unresolved = bs.build(tree)
    assert unresolved == []
    entry = next(e for e in doc["suppressions"] if e["path"] == "app.py")
    assert entry["triage"] == "doc_example"
    assert entry["added_by"] == bs.INDIVIDUAL


def test_generated_document_passes_the_loader(tree: Path, tmp_path: Path) -> None:
    doc, _ = bs.build(tree)
    path = tmp_path / "supp.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    suppressions = ss.load_suppressions(path)
    assert len(suppressions) == len(doc["suppressions"])
    assert all(s.reason and s.added_by for s in suppressions)


def test_generated_document_is_self_describing(tree: Path) -> None:
    doc, _ = bs.build(tree)
    assert doc["version"] == ss.SUPPRESSION_FILE_VERSION
    assert doc["scanner"] == f"{ss.SCANNER_NAME}@{ss.SCANNER_VERSION}"
    assert "TRIAGE AID" in doc["_comment"]
    assert "asserts nothing about the rest of the tree" in doc["_scope"]
    assert "not a credential oracle" in doc["_fingerprint"]
    assert doc["_rebuild"] == "python -m tools.security.build_suppressions"
    assert doc["total_locations"] == 3
    assert doc["scanned_files"] == 3


def test_unreviewed_can_never_be_class_suppressed() -> None:
    """The one bucket that must not have a class reason."""
    assert "unreviewed" not in bs.CLASS_REASON
    assert "true_positive" not in bs.CLASS_REASON
    assert all(triage in ss.TRIAGE_BUCKETS for triage in bs.CLASS_REASON)
    assert all(triage in ss.TRIAGE_BUCKETS for triage, _ in bs.HAND.values())
    assert all(triage != "true_positive" for triage, _ in bs.HAND.values())


def test_every_hand_entry_has_a_real_reason() -> None:
    for key, (triage, reason) in bs.HAND.items():
        assert len(reason) > 30, f"{key}: reason is too thin to audit"
        assert triage != "unreviewed", key


def test_hand_triaged_paths_still_exist() -> None:
    """A moved or deleted file must fail loudly, not silently stop being triaged."""
    for key in bs.HAND:
        relative = key.rsplit(":", 1)[0] if key.rsplit(":", 1)[-1].isdigit() else key
        assert (bs.REPO_ROOT / relative).is_file(), relative


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------


def test_check_detects_a_missing_entry(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc, _ = bs.build(tree)
    path = tmp_path / "supp.json"
    trimmed = dict(doc)
    trimmed["suppressions"] = doc["suppressions"][:-1]
    path.write_text(json.dumps(trimmed), encoding="utf-8")

    code = bs.main(["--root", str(tree), "--out", str(path), "--check"])
    assert code == 1
    assert "missing" in capsys.readouterr().err


def test_check_detects_a_stale_entry(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc, _ = bs.build(tree)
    path = tmp_path / "supp.json"
    doc["suppressions"] = list(doc["suppressions"]) + [
        {
            "fingerprint": "0" * 16,
            "rule": "aws_access_key_id",
            "path": "gone.py",
            "triage": "test_fixture",
            "reason": "a file that no longer exists",
            "added_at": "2026-01-01T00:00:00Z",
            "added_by": bs.INDIVIDUAL,
        }
    ]
    path.write_text(json.dumps(doc), encoding="utf-8")

    code = bs.main(["--root", str(tree), "--out", str(path), "--check"])
    assert code == 1
    assert "stale" in capsys.readouterr().err


def test_check_does_not_write(tree: Path, tmp_path: Path) -> None:
    path = tmp_path / "supp.json"
    assert bs.main(["--root", str(tree), "--out", str(path), "--check"]) == 1
    assert not path.exists()


def test_main_writes_and_reports_the_queue(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "supp.json"
    # app.py stays unreviewed, so the exit code is non-zero: the queue is open.
    assert bs.main(["--root", str(tree), "--out", str(path)]) == 1
    out = capsys.readouterr().out
    assert "NOT SUPPRESSED" in out
    assert "app.py:1" in out
    assert path.is_file()
    assert FAKE_AWS not in path.read_text(encoding="utf-8")
    assert HIGH_ENTROPY not in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The shipped file
# ---------------------------------------------------------------------------


def test_shipped_file_matches_the_recorded_triage_shape() -> None:
    doc = json.loads(bs.OUTPUT.read_text(encoding="utf-8"))
    individual = [e for e in doc["suppressions"] if e["added_by"] == bs.INDIVIDUAL]
    by_class = [e for e in doc["suppressions"] if e["added_by"] == bs.BY_CLASS]
    assert len(individual) + len(by_class) == len(doc["suppressions"])
    assert individual, "no entry claims to have been read individually"
    assert all(e["reason"] in {r for _, r in bs.HAND.values()} for e in individual)
    assert all(e["reason"] in set(bs.CLASS_REASON.values()) for e in by_class)
