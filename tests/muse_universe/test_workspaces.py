from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from plugins.muse_universe.authorization import AuthorizationError
from plugins.muse_universe.preview_signing import PreviewSigner, PreviewTokenError
from plugins.muse_universe.workspaces import WorkspaceBroker


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git", "-C", str(repo), "-c", "user.name=Test", "-c",
            "user.email=test@example.invalid", "commit", "-m", "initial",
        ],
        check=True,
        capture_output=True,
    )
    return repo


def test_local_lease_is_isolated_and_checkpointed(tmp_path: Path, git_repo: Path) -> None:
    broker = WorkspaceBroker(root=tmp_path / "leases")
    lease = broker.create(provider="local", project_root=git_repo, actor_id="ply_1")
    assert Path(lease.workspace) != git_repo
    assert lease.status == "ready"
    (Path(lease.workspace) / "change.txt").write_text("change", encoding="utf-8")
    checkpoint = broker.checkpoint(lease.id, "before visual edit")
    assert checkpoint.commit
    signer = PreviewSigner(secret=b"s" * 32)
    token = broker.signed_preview(lease.id, signer, "/preview/", ttl_seconds=60)
    assert signer.verify(token, "/preview/index.html").lease_id == lease.id
    broker.sleep(lease.id)
    assert broker.get(lease.id).status == "sleeping"
    broker.resume(lease.id)
    assert broker.get(lease.id).status == "ready"
    broker.destroy(lease.id)
    assert broker.get(lease.id).status == "destroyed"


def test_preview_signature_expires_and_is_path_and_origin_bound() -> None:
    signer = PreviewSigner(secret=b"s" * 32)
    token = signer.issue("lease_1", "/preview/", ttl_seconds=60, now=100)
    assert signer.verify(token, "/preview/index.html", now=120).lease_id == "lease_1"
    with pytest.raises(PreviewTokenError):
        signer.verify(token, "/admin", now=120)
    with pytest.raises(PreviewTokenError, match="origin"):
        signer.verify(token, "/preview/index.html", now=120, origin="https://example.invalid")
    with pytest.raises(PreviewTokenError, match="expired"):
        signer.verify(token, "/preview/index.html", now=161)


def test_external_lease_requires_owner_approval(tmp_path: Path, git_repo: Path) -> None:
    broker = WorkspaceBroker(root=tmp_path / "leases")
    with pytest.raises(AuthorizationError):
        broker.create(provider="modal", project_root=git_repo, actor_id="ply_1", workload="gpu")


def test_unavailable_external_provider_is_typed_and_secret_free(
    tmp_path: Path, git_repo: Path
) -> None:
    broker = WorkspaceBroker(
        root=tmp_path / "leases",
        approval_verifier=lambda approval, actor, provider, cost: approval == "apr_1",
    )
    lease = broker.create(
        provider="daytona",
        project_root=git_repo,
        actor_id="ply_1",
        approval_id="apr_1",
    )
    assert lease.status == "unavailable"
    events = [
        json.loads(line)
        for line in (tmp_path / "leases" / "workspace-events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert events[-1]["status"] == "unavailable"
    assert "token" not in json.dumps(events).lower()
