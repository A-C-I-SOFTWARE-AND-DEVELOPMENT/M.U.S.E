"""End-to-end tests for the cockpit voice endpoints.

These exercise the additive routes that expose the canonical
``hermes_cli.voice_intake`` pipeline — and the server-side audio duplex —
to the Android cockpit:

* ``POST /v1/cockpit/voice/intake``      — transcript -> read-back + draft
* ``POST /v1/cockpit/voice/{id}/decide`` — explicit phrase -> terminal state
* ``POST /v1/cockpit/voice/transcribe``  — base64 audio -> redacted transcript
* ``POST /v1/cockpit/voice/responses``   — text -> base64 synthesized audio

The harness mirrors ``test_cockpit_api.py``: a real stdlib server on a
random loopback port with a tmp HERMES_HOME and a known token, driven
with ``urllib``. No network, no third-party deps. The point of these
tests is that the *backend* owns read-back / classification / the
driving-mode safety veto / STT+TTS — the app never reimplements them,
and audio is never retained on the server.
"""

from __future__ import annotations

import base64
import json
import os
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


# ---------------------------------------------------------------------------
# transcribe (audio in) — the server-side STT half of the audio duplex
# ---------------------------------------------------------------------------
#
# The STT/TTS providers are monkeypatched to deterministic fakes (no models,
# no network) so these assert the *handler contract*: auth, validation, secret
# redaction, honest degradation, and that audio is never retained on disk.


def test_transcribe_requires_auth(server) -> None:
    audio = base64.b64encode(b"RIFFfake").decode()
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/transcribe", {"audio_base64": audio}, token=None)
    assert exc.value.code == 401


def test_transcribe_requires_audio(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/transcribe", {"audio_base64": "   "})
    assert exc.value.code == 400


def test_transcribe_rejects_invalid_base64(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/transcribe", {"audio_base64": "!!!not base64!!!"})
    assert exc.value.code == 400


def test_transcribe_redacts_and_does_not_retain_audio(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake_transcribe(file_path: str, model=None):
        # The handler must have decoded our audio onto a real, supported file.
        seen["path"] = file_path
        seen["existed"] = os.path.exists(file_path)
        seen["bytes"] = Path(file_path).read_bytes()
        # Return a transcript that carries a secret-looking token.
        return {
            "success": True,
            "transcript": "my key is sk-ABCDEF1234567890ABCDEF1234567890",
            "provider": "fake-stt",
        }

    monkeypatch.setattr("tools.transcription_tools.transcribe_audio", fake_transcribe)

    raw = b"\x00\x01webm-audio-bytes\x02\x03"
    audio = base64.b64encode(raw).decode()
    status, payload = _post(
        server,
        "/v1/cockpit/voice/transcribe",
        {"audio_base64": audio, "mime": "audio/webm"},
    )
    assert status == 200
    # Provider received the exact bytes, on a webm-suffixed temp file.
    assert seen["existed"] is True
    assert seen["bytes"] == raw
    assert str(seen["path"]).endswith(".webm")
    # The secret is redacted out of the returned transcript.
    assert "sk-ABCDEF1234567890ABCDEF1234567890" not in payload["transcript"]
    assert payload["provider"] == "fake-stt"
    assert payload["audio_retained"] is False
    # Audio is not retained: the temp file is gone after the response.
    assert not os.path.exists(str(seen["path"]))


def test_transcribe_degrades_when_stt_unavailable(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tools.transcription_tools.transcribe_audio",
        lambda file_path, model=None: {
            "success": False,
            "transcript": "",
            "error": "STT is disabled in config.yaml",
        },
    )
    audio = base64.b64encode(b"audio").decode()
    status, payload = _post(
        server, "/v1/cockpit/voice/transcribe", {"audio_base64": audio}
    )
    # Honest empty result, not a crash.
    assert status == 200
    assert payload["transcript"] == ""
    assert "STT is disabled" in payload["error"]
    assert payload["audio_retained"] is False


# ---------------------------------------------------------------------------
# responses (audio out) — the server-side TTS half of the audio duplex
# ---------------------------------------------------------------------------


def test_responses_requires_text(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/voice/responses", {"text": "   "})
    assert exc.value.code == 400


def test_responses_returns_base64_audio_and_does_not_retain(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}
    audio_payload = b"ID3-fake-mp3-bytes-\x00\x01\x02"

    def fake_tts(text: str, output_path: str = "") -> str:
        seen["text"] = text
        seen["out"] = output_path
        Path(output_path).write_bytes(audio_payload)
        return json.dumps(
            {"success": True, "file_path": output_path, "provider": "fake-tts"}
        )

    monkeypatch.setattr("tools.tts_tool.text_to_speech_tool", fake_tts)

    status, payload = _post(
        server, "/v1/cockpit/voice/responses", {"text": "all systems nominal"}
    )
    assert status == 200
    assert seen["text"] == "all systems nominal"
    # The returned base64 decodes to exactly the synthesized bytes.
    assert base64.b64decode(payload["audio_base64"]) == audio_payload
    assert payload["provider"] == "fake-tts"
    assert payload["mime"] == "audio/mpeg"
    assert payload["chars"] == len("all systems nominal")
    assert payload["audio_retained"] is False
    # Not retained: the temp dir (and the file in it) is gone afterward.
    assert not os.path.exists(str(seen["out"]))
    assert not os.path.exists(os.path.dirname(str(seen["out"])))


def test_responses_degrades_when_tts_unavailable(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tools.tts_tool.text_to_speech_tool",
        lambda text, output_path=None: json.dumps(
            {"success": False, "error": "No TTS provider configured"}
        ),
    )
    status, payload = _post(
        server, "/v1/cockpit/voice/responses", {"text": "speak this"}
    )
    assert status == 200
    assert payload["audio_base64"] == ""
    assert "No TTS provider" in payload["error"]
    assert payload["audio_retained"] is False
