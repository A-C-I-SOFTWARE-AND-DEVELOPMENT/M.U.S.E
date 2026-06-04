"""Tests for hermes_cli.nlp_training — dataset validation + Together dispatch.

These tests never touch the network or require the ``together`` SDK: the SDK is
lazily imported and the paid-job gate is enforced before any client call.
"""

from __future__ import annotations

import json

import pytest

from hermes_cli import nlp_training as nt


def _write_jsonl(path, rows) -> str:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(path)


def _convo(user: str, assistant: str, system: str | None = None) -> dict:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    msgs.append({"role": "assistant", "content": assistant})
    return {"messages": msgs}


def test_valid_conversational_passes(tmp_path):
    rows = [_convo(f"question {i}?", f"a specific, complete answer number {i}.")
            for i in range(12)]
    res = nt.validate_dataset(_write_jsonl(tmp_path / "train.jsonl", rows))
    assert res.ok, res.blocking_errors
    assert res.detected_format == "conversational"
    assert res.estimated_trainable_examples == 12


def test_malformed_jsonl_fails(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"messages": [bad json\n{"messages": []}\n', encoding="utf-8")
    res = nt.validate_dataset(str(p))
    assert not res.ok
    assert any("invalid JSON" in e for e in res.blocking_errors)


def test_prompt_only_not_approved_for_sft(tmp_path, monkeypatch):
    monkeypatch.setattr(nt, "QUALITY_REPORT_PATH", tmp_path / "quality.json")
    rows = [{"prompt": f"do task {i} with full detail and context"} for i in range(20)]
    res = nt.approve(_write_jsonl(tmp_path / "prompts.jsonl", rows))
    assert res.detected_format == "prompt"
    assert res.approved_for_training is False
    assert any("prompt-only" in e for e in res.blocking_errors)
    assert res.estimated_trainable_examples == 0


def test_tool_call_arguments_validated_as_json(tmp_path):
    good = {"messages": [
        {"role": "user", "content": "look up the weather"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_weather", "arguments": "{\"city\": \"SF\"}"}}]},
    ]}
    bad = {"messages": [
        {"role": "user", "content": "look up the weather"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_weather", "arguments": "{not json"}}]},
    ]}
    res_good = nt.validate_dataset(_write_jsonl(tmp_path / "g.jsonl", [good] * 12))
    assert res_good.ok, res_good.blocking_errors
    assert res_good.detected_format == "tool_call"

    res_bad = nt.validate_dataset(_write_jsonl(tmp_path / "b.jsonl", [bad] * 12))
    assert not res_bad.ok
    assert any("not valid JSON" in e for e in res_bad.blocking_errors)


def test_secrets_are_blocked_and_not_leaked(tmp_path):
    leak = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd"
    rows = [_convo("hi", "hello")] * 12
    rows.append(_convo("here is my key", f"your key is {leak}"))
    p = _write_jsonl(tmp_path / "leak.jsonl", rows)
    res = nt.validate_dataset(p)
    assert not res.ok
    assert any("secret" in e for e in res.blocking_errors)
    # The secret VALUE must never appear in the report (labels only).
    blob = json.dumps(res.to_dict())
    assert leak not in blob
    assert "openai_key" in blob


def test_duplicate_rate_reported(tmp_path):
    rows = [_convo("same", "same answer")] * 20
    res = nt.validate_dataset(_write_jsonl(tmp_path / "dups.jsonl", rows))
    assert res.duplicate_rate > 0.5
    assert any("duplicate" in w for w in res.warnings)


def test_create_job_refuses_without_flag(tmp_path, monkeypatch):
    # No network/SDK needed: the paid gate fires before any client call.
    monkeypatch.setattr(nt, "JOBS_PATH", tmp_path / "jobs.json")
    rows = [_convo(f"q{i}", f"a complete answer {i}") for i in range(12)]
    p = _write_jsonl(tmp_path / "train.jsonl", rows)
    with pytest.raises(nt.TrainingError) as exc:
        nt.together_create_job(p, yes_start_paid_training=False)
    assert "--yes-start-paid-training" in str(exc.value)


def test_create_job_rejects_unknown_file_id(tmp_path, monkeypatch):
    # A bare file id with no recorded validated upload must be refused before
    # any network call (otherwise a paid job would skip the quality gates).
    monkeypatch.setattr(nt, "JOBS_PATH", tmp_path / "jobs.json")
    with pytest.raises(nt.TrainingError) as exc:
        nt.together_create_job("file-unknown-123", yes_start_paid_training=True)
    assert "unknown training file id" in str(exc.value)


def test_existing_job_for_matches_exact_remote_file(tmp_path, monkeypatch):
    monkeypatch.setattr(nt, "JOBS_PATH", tmp_path / "jobs.json")
    nt._save_jobs_state({
        "uploads": [{"file_id": "file-A", "sha256": "a"},
                    {"file_id": "file-B", "sha256": "b"}],
        "jobs": [],
    })

    class _Remote:
        def __init__(self, jid, tf):
            self.id, self.training_file = jid, tf

    class _Client:
        class fine_tuning:  # noqa: N801
            @staticmethod
            def list():
                return [_Remote("job-A", "file-A")]

    client = _Client()
    # A different file we're about to train must NOT be flagged as a duplicate
    # just because some other file already has a remote job.
    assert nt._existing_job_for("b", "hp", file_id="file-B", client=client) is None
    # The exact file with a remote job IS a duplicate.
    assert nt._existing_job_for("a", "hp", file_id="file-A", client=client) == "job-A"


def test_missing_api_key_fails_cleanly(monkeypatch):
    monkeypatch.setattr(nt, "_load_env", lambda: None)
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    with pytest.raises(nt.TrainingError) as exc:
        nt._require_api_key()
    assert "TOGETHER_API_KEY" in str(exc.value)


def test_no_secret_in_logs(tmp_path, capsys, monkeypatch):
    # A bad key in the environment must never be echoed by the CLI.
    secret = "sk-proj-SECRETVALUE0123456789ABCDEFGHIJ"
    monkeypatch.setenv("TOGETHER_API_KEY", secret)
    monkeypatch.setattr(nt, "JOBS_PATH", tmp_path / "jobs.json")
    rows = [_convo(f"q{i}", f"answer {i}") for i in range(12)]
    p = _write_jsonl(tmp_path / "t.jsonl", rows)
    rc = nt.main(["together-create-job", p])  # no flag -> clean refusal
    out = capsys.readouterr()
    assert rc == 2
    assert secret not in out.out
    assert secret not in out.err


def test_convert_trajectories_sharegpt(tmp_path, monkeypatch):
    rows = [
        {"conversations": [
            {"from": "human", "value": f"task {i}"},
            {"from": "gpt", "value": f"done {i}"}]}
        for i in range(12)
    ]
    src = _write_jsonl(tmp_path / "trajectories.jsonl", rows)
    approved_dir = tmp_path / "approved"
    monkeypatch.setattr(nt, "APPROVED_DIR", approved_dir)
    out = nt.convert_trajectories(src, allow_partial=False)
    assert out["converted"] == 12
    train = (approved_dir / "together_train.jsonl").read_text(encoding="utf-8")
    first = json.loads(train.splitlines()[0])
    assert first["messages"][0]["role"] == "user"
    assert first["messages"][1]["role"] == "assistant"


def test_failed_trajectories_skipped_unless_allowed(tmp_path, monkeypatch):
    rows = [
        {"messages": [{"role": "user", "content": "ok"},
                      {"role": "assistant", "content": "fine"}], "success": True},
        {"messages": [{"role": "user", "content": "bad"},
                      {"role": "assistant", "content": "x"}], "success": False},
    ]
    src = _write_jsonl(tmp_path / "trajectories.jsonl", rows)
    monkeypatch.setattr(nt, "APPROVED_DIR", tmp_path / "approved")
    out = nt.convert_trajectories(src, allow_partial=False)
    assert out["converted"] == 1 and out["skipped"] == 1


def test_scan_writes_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(nt, "INVENTORY_PATH", tmp_path / "inv.json")
    (tmp_path / "data").mkdir()
    _write_jsonl(tmp_path / "data" / "owner_approved_train.jsonl",
                 [_convo("q", "a")] * 3)
    inv = nt.scan(root=tmp_path)
    assert inv["count"] >= 1
    assert (tmp_path / "inv.json").exists()
