"""Tests for live/autonomous wiring: outbound-message policy, integration sends,
background-learner live jobs, and the model-backed eval runner.

The autonomy switch is the existing `muse_cli/approval_policy.py`
(`HERMES_AUTONOMY`). Default (ASSISTED) keeps sends/live-jobs gated; AUTONOMOUS
auto-approves (audited). No real credentials are used — the model runner is
exercised with an injected fake client.
"""

import pytest

from muse_cli import approval_policy as ap
from muse_cli.integrations import (
    ActionRequest,
    build_live_registry,
    default_registry,
    make_gateway_transport,
)


# ── approval policy: outbound message action ─────────────────────────────────

def test_outbound_message_confirms_under_assisted(monkeypatch):
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    req = ap.ApprovalRequest(action=ap.Action.OUTBOUND_MESSAGE, summary="email.send")
    assert ap.evaluate(req).decision is ap.Decision.CONFIRM


def test_outbound_message_allowed_under_autonomous(monkeypatch):
    monkeypatch.setenv("HERMES_AUTONOMY", "autonomous")
    req = ap.ApprovalRequest(action=ap.Action.OUTBOUND_MESSAGE, summary="email.send")
    assert ap.evaluate(req).decision is ap.Decision.ALLOW


# ── integration registry honors autonomy for sends ───────────────────────────

def test_send_blocked_under_default_autonomy(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    calls = []
    reg = build_live_registry(email_sender=lambda p: calls.append(p) or "SENT")
    res = reg.execute(ActionRequest("email", "send", {"to": "x@y.z", "body": "hi"}))
    assert res.status == "needs_approval"
    assert calls == []  # nothing sent without approval/autonomy


def test_send_auto_approved_under_autonomous_calls_transport(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_AUTONOMY", "autonomous")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    calls = []
    reg = build_live_registry(email_sender=lambda p: calls.append(p) or "SENT")
    res = reg.execute(ActionRequest("email", "send", {"to": "x@y.z", "body": "hi"}))
    assert res.status == "ok"
    assert res.data == "SENT"
    assert calls and calls[0]["to"] == "x@y.z"


def test_explicit_approval_still_works_regardless_of_autonomy(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    calls = []
    reg = build_live_registry(sms_sender=lambda p: calls.append(p) or "OK")
    res = reg.execute(ActionRequest("sms", "send", {"to": "+15550000000"}), approved=True)
    assert res.status == "ok"
    assert len(calls) == 1


def test_make_gateway_transport_passes_payload():
    seen = {}
    t = make_gateway_transport(lambda p: seen.update(p) or "done")
    out = t(ActionRequest("email", "send", {"to": "a@b.c", "subject": "x"}))
    assert out == "done"
    assert seen["subject"] == "x"


def test_unwired_send_under_autonomy_is_ok_noop(monkeypatch, tmp_path):
    # default_registry wires no transport: autonomy approves but there's no
    # transport → declared-only "ok" with no side effect.
    monkeypatch.setenv("HERMES_AUTONOMY", "autonomous")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    res = default_registry().execute(ActionRequest("email", "send", {"to": "x@y.z"}))
    assert res.status == "ok"
    assert res.data is None


# ── background-learner live jobs honor autonomy ──────────────────────────────

def test_background_live_job_downgraded_by_default(monkeypatch):
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    from muse_cli.background_learner import JobQueue

    q = JobQueue()
    job = q.enqueue("scan_outdated_deps", dry_run=False)
    assert job.dry_run is True  # not authorized → downgraded


def test_background_live_job_authorized_under_autonomous(monkeypatch):
    monkeypatch.setenv("HERMES_AUTONOMY", "autonomous")
    from muse_cli.background_learner import JobQueue

    q = JobQueue()
    job = q.enqueue("scan_outdated_deps", dry_run=False)
    assert job.dry_run is False  # autonomy authorizes live run


def test_background_live_job_authorized_by_token(monkeypatch):
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    from muse_cli.background_learner import JobQueue

    q = JobQueue()
    job = q.enqueue("scan_outdated_deps", dry_run=False, approval_token="owner-ok")
    assert job.dry_run is False


# ── model-backed eval runner (fake client; no network) ───────────────────────

class _FakeFn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeFn(name, arguments)


class _FakeMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResp:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    def __init__(self, resp):
        self._resp = resp

    def create(self, **kwargs):
        return self._resp


class _FakeChat:
    def __init__(self, resp):
        self.completions = _FakeCompletions(resp)


class _FakeClient:
    def __init__(self, resp):
        self.chat = _FakeChat(resp)


def test_model_runner_parses_tool_call():
    from muse_cli.evals import build_model_runner

    resp = _FakeResp(_FakeMessage("", [_FakeToolCall("echo", '{"text": "hi"}')]))
    runner = build_model_runner(client=_FakeClient(resp), model="fake")
    out = runner("call echo")
    assert out["name"] == "echo"
    assert out["arguments"] == {"text": "hi"}


def test_model_runner_plain_text():
    from muse_cli.evals import build_model_runner

    resp = _FakeResp(_FakeMessage("just text"))
    runner = build_model_runner(client=_FakeClient(resp), model="fake")
    out = runner("hello")
    assert out["text"] == "just text"
    assert out["name"] is None


def test_model_runner_feeds_harness_tool_call_case():
    from muse_cli.evals import build_model_runner, run_suite

    resp = _FakeResp(_FakeMessage("", [_FakeToolCall("echo", '{"text": "hi"}')]))
    runner = build_model_runner(client=_FakeClient(resp), model="fake")
    report = run_suite("fake-worker", runner=runner)
    assert report.scores.get("tool_call_correctness") == 1.0


def test_model_runner_missing_key_errors_only_on_invoke(monkeypatch):
    from muse_cli.evals import build_model_runner

    monkeypatch.delenv("HERMES_EVAL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = build_model_runner(model="fake")  # building is safe
    with pytest.raises(RuntimeError):
        runner("hello")  # only errors when actually invoked without creds
