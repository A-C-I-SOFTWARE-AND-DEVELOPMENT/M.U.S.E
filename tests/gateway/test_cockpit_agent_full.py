"""Tests for the cockpit full-agent chat lane (gateway/cockpit/agent_full).

Hermetic (tmp HERMES_HOME, no network, no model): the AIAgent is replaced by
a fake injected via ``agent_factory`` (unit layer) or by monkeypatching
``agent_full._create_agent`` (HTTP layer). What's under test is OUR wiring:

* the additive chunk constructors (``body_delta`` / ``approval``);
* the responder's chunk choreography (thinking → phases → tool_call
  START/OK → body_delta stream → FINAL → authoritative body → done);
* the owner-approval bridge (notify → ``approval`` chunk; resolve via
  ``resolve_approval`` unblocks the queue);
* the interrupt registry;
* the HTTP surface: /v1/agent/chat streams NDJSON in full mode, answers
  409 in default jarvis mode, /v1/health advertises the mode, and the
  companion routes validate input.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest  # ty: ignore[unresolved-import]

from gateway.cockpit import agent_full
from gateway.cockpit.server import serve
from gateway.jarvis_local_http import approval as approval_chunk
from gateway.jarvis_local_http import body_delta

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class FakeAgent:
    """Callback-faithful stand-in for run_agent.AIAgent."""

    def __init__(
        self,
        *,
        session_id=None,
        gateway_session_key=None,
        stream_delta_callback=None,
        tool_start_callback=None,
        tool_complete_callback=None,
        final_response="The answer is 42.",
        fail=False,
        block_for_approval=False,
    ):
        # No-op fallbacks so the callbacks are always callable (the real
        # responder always supplies them; direct-construction tests may not).
        self.session_id = session_id
        self.gateway_session_key = gateway_session_key
        self._stream = stream_delta_callback or (lambda _d: None)
        self._tool_start = tool_start_callback or (lambda *_a: None)
        self._tool_complete = tool_complete_callback or (lambda *_a: None)
        self._final = final_response
        self._fail = fail
        self._block_for_approval = block_for_approval
        self.interrupted = False

    def interrupt(self, message=None):
        self.interrupted = True

    def run_conversation(self, user_message, conversation_history=None, task_id=None):
        if self._fail:
            return {"failed": True, "error": "model exploded", "final_response": ""}
        args = {"command": "python -c 'print(6*7)'"}
        self._tool_start("call-1", "terminal", args)
        self._tool_complete("call-1", "terminal", args, "42\n")
        if self._block_for_approval:
            # Mirror tools/approval.py's gateway branch: enqueue an entry,
            # fire the registered notify, then block until resolved.
            from tools.approval import (
                _ApprovalEntry,
                _gateway_notify_cbs,
                _gateway_queues,
                _lock,
            )

            data = {"command": "rm -rf /tmp/x", "description": "dangerous delete"}
            entry = _ApprovalEntry(data)
            key = str(self.gateway_session_key)
            with _lock:
                queue = _gateway_queues.get(key)
                if queue is None:
                    queue = []
                    _gateway_queues[key] = queue
                queue.append(entry)
                notify = _gateway_notify_cbs.get(key)
            # Control-flow narrowing (an explicit raise) is understood by the
            # type checker; `notify` is non-None past this point.
            if notify is None:
                raise AssertionError("responder must register the notify bridge")
            notify(data)
            assert entry.event.wait(timeout=10), "approval never resolved"
        for piece in ("The answer ", "is 42."):
            self._stream(piece)
        return {"final_response": self._final, "completed": True}


def _drain(prompt="run it", history=None, **kwargs):
    return list(
        agent_full.full_agent_responder(prompt, history or [], **kwargs)
    )


# ---------------------------------------------------------------------------
# wire-contract constructors
# ---------------------------------------------------------------------------


def test_body_delta_shape() -> None:
    assert body_delta("abc") == {"type": "body_delta", "text": "abc"}


def test_approval_chunk_shape_and_choices() -> None:
    chunk = approval_chunk("ap-1", "sess-9", "delete a file", tool="terminal")
    assert chunk["type"] == "approval"
    assert chunk["id"] == "ap-1"
    assert chunk["sessionKey"] == "sess-9"
    assert chunk["tool"] == "terminal"
    assert chunk["choices"] == ["once", "session", "always", "deny"]


# ---------------------------------------------------------------------------
# responder choreography
# ---------------------------------------------------------------------------


def test_responder_streams_tools_deltas_and_final_body(home: Path) -> None:
    chunks = _drain(agent_factory=lambda **kw: FakeAgent(**kw))
    kinds = [c["type"] for c in chunks]

    assert kinds[0] == "thinking"
    assert kinds[-1] == "done"
    # Tool lifecycle rides the stream in order.
    tool_chunks = [c for c in chunks if c["type"] == "tool_call"]
    assert [t["status"] for t in tool_chunks] == ["START", "OK"]
    assert tool_chunks[0]["name"] == "terminal"
    # Streaming deltas arrive, then the authoritative accumulated body.
    deltas = [c["text"] for c in chunks if c["type"] == "body_delta"]
    assert "".join(deltas) == "The answer is 42."
    bodies = [c for c in chunks if c["type"] == "body"]
    assert bodies and bodies[-1]["text"] == "The answer is 42."
    # Phases include TOOL (from the tool start) and FINAL (before the body).
    phases = [c["phase"] for c in chunks if c["type"] == "phase"]
    assert "TOOL" in phases and "FINAL" in phases


def test_responder_surfaces_structured_failure_as_error(home: Path) -> None:
    chunks = _drain(agent_factory=lambda **kw: FakeAgent(**kw, fail=True))
    kinds = [c["type"] for c in chunks]
    assert "error" in kinds
    assert kinds[-1] == "done"
    err = next(c for c in chunks if c["type"] == "error")
    assert "model exploded" in err["message"]


def test_responder_never_raises_when_factory_explodes(home: Path) -> None:
    def _boom(**kw):
        raise RuntimeError("no model configured")

    chunks = _drain(agent_factory=_boom)
    kinds = [c["type"] for c in chunks]
    assert "error" in kinds and kinds[-1] == "done"


def test_approval_round_trip(home: Path) -> None:
    """A blocked tool surfaces an approval chunk; resolve unblocks the run."""
    skey = "sess-approve-1"
    seen: list[dict] = []
    finished = threading.Event()

    def _consume():
        for c in agent_full.full_agent_responder(
            "do something gated",
            [],
            session_key=skey,
            agent_factory=lambda **kw: FakeAgent(**kw, block_for_approval=True),
        ):
            seen.append(c)
        finished.set()

    t = threading.Thread(target=_consume, daemon=True)
    t.start()

    # Wait for the approval chunk to ride the stream.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if any(c["type"] == "approval" for c in seen):
            break
        time.sleep(0.05)
    approvals = [c for c in seen if c["type"] == "approval"]
    assert approvals, f"no approval chunk in {[c['type'] for c in seen]}"
    assert approvals[0]["sessionKey"] == skey
    assert not finished.is_set(), "stream must stay open while blocked"

    assert agent_full.resolve_approval(skey, "once") == 1
    assert finished.wait(timeout=10), "stream must complete after resolve"
    assert seen[-1]["type"] == "done"
    assert any(c["type"] == "body" and "42" in c["text"] for c in seen)


def test_resolve_approval_validates_choice(home: Path) -> None:
    with pytest.raises(ValueError):
        agent_full.resolve_approval("sess-x", "yolo")
    assert agent_full.resolve_approval("sess-without-pending", "once") == 0


def test_interrupt_run_registry(home: Path) -> None:
    agent = FakeAgent(
        stream_delta_callback=lambda d: None,
        tool_start_callback=lambda *a: None,
        tool_complete_callback=lambda *a: None,
    )
    assert agent_full._claim_active("sess-int", agent) is True
    try:
        assert agent_full.interrupt_run("sess-int") is True
        assert agent.interrupted is True
    finally:
        agent_full._unregister_active("sess-int", agent)
    assert agent_full.interrupt_run("sess-int") is False


def test_claim_active_refuses_second_run(home: Path) -> None:
    a1 = FakeAgent()
    a2 = FakeAgent()
    assert agent_full._claim_active("dup-key", a1) is True
    try:
        # A second claim for the same key is refused (busy guard).
        assert agent_full._claim_active("dup-key", a2) is False
    finally:
        agent_full._unregister_active("dup-key", a1)
    # After release, a new claim succeeds.
    assert agent_full._claim_active("dup-key", a2) is True
    agent_full._unregister_active("dup-key", a2)


def test_busy_session_is_refused_end_to_end(home: Path) -> None:
    """A second responder for an in-flight session key gets an error, not a
    clobbered run."""
    import threading as _t
    import time as _time

    skey = "busy-e2e"
    release = _t.Event()

    class SlowAgent(FakeAgent):
        def run_conversation(self, user_message, conversation_history=None, task_id=None):
            release.wait(timeout=10)
            return {"final_response": "done", "completed": True}

    started = _t.Event()

    def _run_first():
        for _ in agent_full.full_agent_responder(
            "first", [], session_key=skey, agent_factory=lambda **kw: SlowAgent(**kw)
        ):
            started.set()
        # drains to completion

    t = _t.Thread(target=_run_first, daemon=True)
    t.start()
    # Wait until the first run has claimed the session.
    deadline = _time.monotonic() + 5
    while _time.monotonic() < deadline and skey not in agent_full._active_agents:
        _time.sleep(0.02)

    second = list(
        agent_full.full_agent_responder(
            "second", [], session_key=skey, agent_factory=lambda **kw: FakeAgent(**kw)
        )
    )
    kinds = [c["type"] for c in second]
    assert "error" in kinds and kinds[-1] == "done"
    err = next(c for c in second if c["type"] == "error")
    assert "already in progress" in err["message"]
    release.set()
    t.join(timeout=10)


def test_clip_scrubs_before_truncation(home: Path) -> None:
    """A secret longer than the clip window is redacted, not half-leaked."""
    secret = "sk_live_" + ("A" * 700)
    clipped = agent_full._clip(secret)
    assert "sk_live_" + "A" * 40 not in clipped  # raw prefix must not survive


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _post_raw(server, path: str, body: dict, token: str | None = TOKEN):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return urllib.request.urlopen(req, timeout=30)


def _get_json(server, path: str):
    with urllib.request.urlopen(_url(server, path), timeout=10) as resp:
        return resp.status, json.loads(resp.read())


@pytest.fixture()
def full_server(home: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        agent_full, "_create_agent", lambda **kw: FakeAgent(**kw)
    )
    srv = serve(host="127.0.0.1", port=0, token=TOKEN, agent_mode="full")
    yield srv
    srv.shutdown()


@pytest.fixture()
def jarvis_server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


# NOTE: agent mode is process-global (one cockpit server per process, like
# _ALLOW_REMOTE_EXECUTE), so each test below uses exactly one server fixture.


def test_health_advertises_full_agent_mode(full_server) -> None:
    _, health = _get_json(full_server, "/v1/health")
    assert health["agent"] == "full"


def test_health_advertises_jarvis_agent_mode(jarvis_server) -> None:
    _, health = _get_json(jarvis_server, "/v1/health")
    assert health["agent"] == "jarvis"


def test_agent_chat_streams_ndjson_in_full_mode(full_server) -> None:
    with _post_raw(full_server, "/v1/agent/chat", {"prompt": "compute 6*7"}) as resp:
        assert resp.status == 200
        assert resp.headers.get("Content-Type") == "application/x-ndjson"
        lines = [json.loads(l) for l in resp.read().splitlines() if l.strip()]
    kinds = [c["type"] for c in lines]
    assert kinds[0] == "thinking" and kinds[-1] == "done"
    assert any(c["type"] == "tool_call" for c in lines)
    assert any(c["type"] == "body" and "42" in c["text"] for c in lines)


def test_agent_chat_409s_in_jarvis_mode(jarvis_server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post_raw(jarvis_server, "/v1/agent/chat", {"prompt": "hi"})
    assert exc_info.value.code == 409
    payload = json.loads(exc_info.value.read())
    assert "full agent mode" in payload["error"]


def test_agent_chat_requires_auth(full_server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post_raw(full_server, "/v1/agent/chat", {"prompt": "hi"}, token=None)
    assert exc_info.value.code == 401


def test_agent_companion_routes_validate(full_server) -> None:
    # Missing fields -> 400.
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post_raw(full_server, "/v1/agent/approvals", {})
    assert exc_info.value.code == 400
    # Nothing pending -> 404.
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post_raw(
            full_server,
            "/v1/agent/approvals",
            {"session_key": "nope", "choice": "once"},
        )
    assert exc_info.value.code == 404
    # No active run -> 404.
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post_raw(full_server, "/v1/agent/stop", {"session_key": "nope"})
    assert exc_info.value.code == 404


def test_full_agent_refused_on_non_loopback_bind(home: Path) -> None:
    """--agent full must not bind a network host (the lane runs code exec)."""
    with pytest.raises(ValueError, match="non-loopback"):
        serve(host="0.0.0.0", port=0, token=TOKEN, agent_mode="full",
              allow_external=True, allow_external_hosts=["0.0.0.0/0"])


def test_agent_companion_routes_refuse_in_jarvis_mode(jarvis_server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _post_raw(
            jarvis_server,
            "/v1/agent/approvals",
            {"session_key": "s", "choice": "once"},
        )
    assert exc_info.value.code == 409


def _get_authed(server, path: str):
    req = urllib.request.Request(_url(server, path))
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def test_channels_endpoint_reads_runtime_status(jarvis_server) -> None:
    status, data = _get_authed(jarvis_server, "/v1/cockpit/channels")
    assert status == 200
    assert isinstance(data.get("channels"), list)
    assert "connected_count" in data


def test_schedules_endpoint_lists_cron_jobs(jarvis_server) -> None:
    status, data = _get_authed(jarvis_server, "/v1/cockpit/schedules")
    assert status == 200
    assert isinstance(data.get("schedules"), list)
    assert "count" in data


def test_channels_requires_auth(jarvis_server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(_url(jarvis_server, "/v1/cockpit/channels"), timeout=10)
    assert exc_info.value.code == 401
