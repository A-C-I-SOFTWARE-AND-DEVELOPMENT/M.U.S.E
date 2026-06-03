"""End-to-end tests for the cockpit Evidence Engine API.

Hermetic: a real stdlib server on a random loopback port with a tmp
HERMES_HOME (so the Research Vault + Memory Tree are isolated) and a known
token, driven with ``urllib``. No network, no third-party deps.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve
from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def seeded_vault(home: Path) -> ResearchVault:
    vault = ResearchVault()  # honors HERMES_HOME
    vault.add(
        "vLLM continuous batching",
        "https://docs.vllm.ai/serving",
        source_type=SourceType.OFFICIAL_DOC,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="vLLM uses continuous batching to improve serving throughput.",
        citation_anchors=("serving.md:12",),
    )
    return vault


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get(server, path: str):
    req = urllib.request.Request(_url(server, path), method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(server, path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_evidence_list(server, seeded_vault) -> None:
    status, payload = _get(server, "/v1/cockpit/evidence")
    assert status == 200
    items = payload["items"]
    assert any(i["title"] == "vLLM continuous batching" for i in items)
    item = items[0]
    assert item["trust"] in ("primary", "owner", "official_doc", "reputable", "community", "unverified")
    assert "checksum" in item and "citation_anchors" in item


def test_evidence_search_returns_hits(server, seeded_vault) -> None:
    status, payload = _get(server, "/v1/cockpit/evidence?q=continuous+batching")
    assert status == 200
    assert payload["hits"], "expected ranked hits"
    assert payload["hits"][0]["trust"] == "primary"


def test_evidence_detail(server, seeded_vault) -> None:
    _, listing = _get(server, "/v1/cockpit/evidence")
    art_id = listing["items"][0]["id"]
    status, payload = _get(server, f"/v1/cockpit/evidence/{art_id}")
    assert status == 200
    assert payload["item"]["id"] == art_id


def test_evidence_verify(server, seeded_vault) -> None:
    status, payload = _post(
        server,
        "/v1/cockpit/evidence/verify",
        {"claims": ["vLLM uses continuous batching", "Mars has two moons"]},
    )
    assert status == 200
    assert "Mars has two moons" in payload["uncertain"]
    assert any(c["supported"] for c in payload["citations"])


def test_evidence_promote_requires_owner_for_low_confidence(server, home) -> None:
    vault = ResearchVault()
    weak = vault.add(
        "Forum rumor",
        "https://forum.example/post",
        evidence_strength=EvidenceStrength.WEAK,
        excerpt="Someone says X is true.",
    )
    status, payload = _post(server, f"/v1/cockpit/evidence/{weak.id}/promote", {})
    assert status == 422
    assert payload["promoted"] is False


def test_evidence_promote_owner_approved(server, seeded_vault) -> None:
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    art_id = next(iter(seeded_vault.artifacts))
    status, payload = _post(
        server,
        f"/v1/cockpit/evidence/{art_id}/promote",
        {"authorization": AUTHORIZATION_PHRASE},
    )
    assert status == 201
    assert payload["promoted"] is True
