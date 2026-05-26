"""Tests for hermes_cli.jarvis_prime.onboarding — first-run device scan."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.onboarding import (
    OnboardingPolicy,
    OnboardingRunner,
)


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    # Build a tiny fake home with a gitconfig + a few docs.
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Documents" / "notes.md").write_text(
        "I love python and rust. Author: Jeremiah Echerd.\nTZ: America/Toronto\n",
        encoding="utf-8",
    )
    (tmp_path / ".gitconfig").write_text(
        "[user]\n    name = Jeremiah Echerd\n    email = echerd27@gmail.com\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(journal_path=tmp_path / "memory.jsonl")


def test_policy_disabled_only_records_platform(store: MemoryStore) -> None:
    runner = OnboardingRunner(memory=store, policy=OnboardingPolicy.disabled())
    report = runner.run()
    assert report.files_scanned == 0
    # Platform signature is always recorded.
    keys = {r.key for r in store.durable}
    assert "device_platform" in keys


def test_full_local_policy_scans_documents(
    fake_home: Path, store: MemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _read_git_history_local resolves ``~/.gitconfig`` via
    # os.path.expanduser, so point HOME at the fixture's fake home for
    # the duration of this test — otherwise the test reads whatever
    # gitconfig happens to exist on the CI runner.
    monkeypatch.setenv("HOME", str(fake_home))
    policy = OnboardingPolicy.full_local()
    policy = OnboardingPolicy(
        scan_home_directory=policy.scan_home_directory,
        read_email_local=False,
        read_text_messages_local=False,
        read_browser_bookmarks=False,
        read_git_history_local=True,
        research_public_social=False,
        research_human_psychology=False,
        scan_roots=(str(fake_home / "Documents"), str(fake_home / ".gitconfig")),
    )
    runner = OnboardingRunner(memory=store, policy=policy)
    report = runner.run()
    assert report.files_scanned >= 1
    keys = {r.key for r in store.durable}
    assert "user_name" in keys
    assert "user_email" in keys


def test_secret_in_scanned_file_is_rejected(tmp_path: Path, store: MemoryStore) -> None:
    secret_file = tmp_path / "secret.md"
    secret_file.write_text(
        "Author: NotARealPerson\napi_key = sk-abcdefghij1234567890abcdefghij1234567890\n",
        encoding="utf-8",
    )
    policy = OnboardingPolicy(
        scan_home_directory=True,
        scan_roots=(str(secret_file),),
    )
    runner = OnboardingRunner(memory=store, policy=policy)
    runner.run()
    # The MemoryStore filter should have rejected secret-laden records.
    all_values = " ".join(r.value for r in store.durable + store.session)
    assert "sk-abcdefghij" not in all_values


def test_max_files_bound_respected(tmp_path: Path, store: MemoryStore) -> None:
    docs = tmp_path / "many"
    docs.mkdir()
    for i in range(50):
        (docs / f"note{i}.md").write_text("hello", encoding="utf-8")
    policy = OnboardingPolicy(
        scan_home_directory=True,
        scan_roots=(str(docs),),
        max_files_scanned=10,
    )
    runner = OnboardingRunner(memory=store, policy=policy)
    report = runner.run()
    assert report.files_scanned <= 10


def test_interests_extracted_to_session_memory(fake_home: Path, store: MemoryStore) -> None:
    policy = OnboardingPolicy(
        scan_home_directory=True,
        scan_roots=(str(fake_home / "Documents"),),
    )
    runner = OnboardingRunner(memory=store, policy=policy)
    runner.run()
    interest_keys = {r.key for r in store.session if r.key.startswith("interest:")}
    # "I love python and rust" should land at least one interest signal.
    assert len(interest_keys) >= 1


def test_report_serializes_to_dict(store: MemoryStore) -> None:
    runner = OnboardingRunner(memory=store, policy=OnboardingPolicy.disabled())
    report = runner.run()
    payload = report.to_dict()
    assert "started_at" in payload
    assert "finished_at" in payload
    assert "files_scanned" in payload


def test_intent_markers_for_social_and_psychology(store: MemoryStore) -> None:
    policy = OnboardingPolicy(
        research_public_social=True,
        research_human_psychology=True,
    )
    runner = OnboardingRunner(memory=store, policy=policy)
    runner.run()
    keys = {r.key for r in store.durable}
    assert "research_intent:social_platforms" in keys
    assert "research_intent:human_psychology" in keys


def test_skipped_paths_recorded(store: MemoryStore) -> None:
    policy = OnboardingPolicy(
        scan_home_directory=True,
        scan_roots=("/nonexistent/path/abc",),
    )
    runner = OnboardingRunner(memory=store, policy=policy)
    report = runner.run()
    assert any("/nonexistent" in p for p in report.skipped_paths)
