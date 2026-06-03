"""End-to-end tests for the cockpit voice-intake endpoints.

These exercise the additive routes that expose the canonical
``hermes_cli.voice_intake`` pipeline to the Android cockpit:

* ``POST /v1/cockpit/voice/intake``      — transcript -> read-back + draft
* ``POST /v1/cockpit/voice/{id}/decide`` — explicit phrase -> terminal state

The harness mirrors ``test_cockpit_api.py``: a real stdlib server on a
random loopback port with a tmp HERMES_HOME and a known token, driven
with ``urllib``. No network, no third-party deps. The point of these
tests is that the *backend* owns read-back / classification / the
driving-mode safety veto — the app never reimplements them.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _post(server, path: str, body: dict, token: str | None = TOKEN):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read())


def _intake(server, transcript: str, mode: str | None = None):
    body: dict = {"transcript": transcript}
    if mode is not None:
        body["mode"] = mode
    return _post(server, "/v1/cockpit/voice/intake", body)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_intake_requires_auth(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/intake", {"transcript": "hi"}, token=None)
    assert exc.value.code == 401


def test_intake_requires_transcript(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/intake", {"transcript": "  "})
    assert exc.value.code == 400


def test_intake_returns_readback_and_draft(server) -> None:
    status, payload = _intake(server, "remember to water the plants")
    assert status == 201
    assert payload["id"].startswith("voi-")
    assert payload["mode"] == "push_to_talk"
    assert payload["readback"]  # non-empty spoken string
    draft = payload["draft"]
    assert draft["intent"] == "capture_note"
    assert draft["publish_action"] is False


def test_unknown_mode_collapses_to_push_to_talk(server) -> None:
    # A typo'd / hostile mode must never silently land the user in driving.
    _, payload = _intake(server, "note this", mode="not-a-real-mode")
    assert payload["mode"] == "push_to_talk"


def test_publish_action_is_flagged(server) -> None:
    _, payload = _intake(server, "deploy the web app to production")
    assert payload["draft"]["publish_action"] is True


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------


def test_decide_unknown_id_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/voi-deadbeef/decide", {"phrase": "yes"})
    assert exc.value.code == 404


def test_decide_affirmative_creates_job(server) -> None:
    _, created = _intake(server, "create a job to fix the failing test")
    vid = created["id"]
    status, payload = _post(server, f"/v1/cockpit/voice/{vid}/decide", {"phrase": "yes go ahead"})
    assert status == 200
    assert payload["state"] == "approved"
    assert payload["job_id"]  # a real queue entry was created


def test_decide_ambiguous_does_not_approve(server) -> None:
    # An ambiguous (non-affirmative, non-negative) reply in push-to-talk
    # leaves the intake awaiting confirmation — never approved.
    _, created = _intake(server, "create a job to refactor the parser")
    vid = created["id"]
    status, payload = _post(
        server, f"/v1/cockpit/voice/{vid}/decide", {"phrase": "hmm maybe later"}
    )
    assert status == 200
    assert payload["state"] != "approved"
    assert payload["job_id"] is None


def test_decide_silence_expires(server) -> None:
    _, created = _intake(server, "create a job to bump the version")
    vid = created["id"]
    status, payload = _post(server, f"/v1/cockpit/voice/{vid}/decide", {"phrase": None})
    assert status == 200
    assert payload["state"] == "expired"
    assert payload["job_id"] is None


def test_driving_publish_is_vetoed(server) -> None:
    # Driving mode + an approved publish must raise the safety veto, not
    # silently ship. The action queues for a non-driving confirmation.
    _, created = _intake(server, "deploy the release now", mode="driving_capture")
    vid = created["id"]
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/voice/{vid}/decide", {"phrase": "yes ship it"})
    assert exc.value.code == 409
    body = json.loads(exc.value.read())
    assert body["veto"] == "driving_safety"
