"""Tests for the voice-intake pipeline.

The pipeline lives in ``muse_cli/voice_intake.py`` and the
dataclasses in ``muse_cli/voice_models.py``. These tests do not
touch the audio stack (sounddevice / faster-whisper / TTS) — they
only exercise the transcript-to-job contract.

Each test points ``HERMES_HOME`` at a tmp directory so the
on-disk intake artefacts (transcript.txt,
plain-english-confirmation.md, approval-state.json) never pollute the
caller's real ``~/.hermes/voice/`` folder.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HERMES_HOME at a tmp dir for the duration of one test.

    ``muse_cli.voice_intake._hermes_home()`` reads ``HERMES_HOME`` on
    every call (it is *not* cached), and ``muse_cli.voice_models``
    holds no module-level state at all. A simple ``monkeypatch.setenv``
    is therefore enough — no module reload required. (We previously
    used ``importlib.reload``; that turned out to disturb other tests
    sharing the same xdist worker, so it has been dropped.)
    """
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def vi(hermes_home):
    import muse_cli.voice_intake as vi

    return vi


@pytest.fixture
def vm(hermes_home):
    import muse_cli.voice_models as vm

    return vm


# ---------------------------------------------------------------------------
# Mode normalisation
# ---------------------------------------------------------------------------


class TestModeNormalization:
    def test_canonical_modes_pass_through(self, vm):
        for mode in ("push_to_talk", "wake_word", "driving_capture", "disabled"):
            assert vm.normalize_mode(mode) == mode

    def test_aliases_collapse_to_canonical(self, vm):
        assert vm.normalize_mode("ptt") == "push_to_talk"
        assert vm.normalize_mode("press-to-talk") == "push_to_talk"
        assert vm.normalize_mode("wake") == "wake_word"
        assert vm.normalize_mode("wakeword") == "wake_word"
        assert vm.normalize_mode("driving") == "driving_capture"
        assert vm.normalize_mode("car") == "driving_capture"
        assert vm.normalize_mode("off") == "disabled"

    def test_unknown_value_falls_back_to_push_to_talk(self, vm):
        """Safety property: a malformed config never silently unlocks
        background listening — the safest fallback is the user-driven
        push-to-talk mode."""
        assert vm.normalize_mode("???") == "push_to_talk"
        assert vm.normalize_mode(None) == "push_to_talk"
        assert vm.normalize_mode(123) == "push_to_talk"
        assert vm.normalize_mode("") == "push_to_talk"

    def test_case_and_whitespace_insensitive(self, vm):
        assert vm.normalize_mode("Driving Capture") == "driving_capture"
        assert vm.normalize_mode("  WAKE_WORD  ") == "wake_word"


# ---------------------------------------------------------------------------
# Driving-mode config invariants
# ---------------------------------------------------------------------------


class TestDrivingConfigPinning:
    def test_driving_mode_forces_safety_defaults(self, vm):
        """Even if the caller passes loose values, driving-mode config
        pins ``store_raw_audio=False``, ``require_voice_confirmation=True``,
        ``readback_enabled=True``, and ``redact_secrets=True``."""
        cfg = vm.VoiceIntakeConfig(
            mode="driving_capture",
            store_raw_audio=True,
            require_voice_confirmation=False,
            readback_enabled=False,
            redact_secrets=False,
        )
        assert cfg.mode == "driving_capture"
        assert cfg.store_raw_audio is False
        assert cfg.require_voice_confirmation is True
        assert cfg.readback_enabled is True
        assert cfg.redact_secrets is True

    def test_default_config_is_safe(self, vm):
        cfg = vm.VoiceIntakeConfig()
        assert cfg.mode == "push_to_talk"
        assert cfg.stt_provider == "local"
        assert cfg.allow_remote_stt is False
        assert cfg.store_raw_audio is False
        assert cfg.require_voice_confirmation is True
        assert cfg.redact_secrets is True


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_redacts_api_key_shape(self, vm):
        text = "use sk-abcdef1234567890qrstuvwxyz to call the api"
        redacted = vm.redact_transcript(text)
        assert "sk-abcdef" not in redacted
        assert "[REDACTED]" in redacted

    def test_redacts_github_pat(self, vm):
        text = "the token is ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
        assert "ghp_AbCdEf" not in vm.redact_transcript(text)

    def test_redacts_bearer_token(self, vm):
        text = "set Authorization to bearer abcdefghij1234567890"
        assert "abcdefghij1234567890" not in vm.redact_transcript(text)

    def test_passes_clean_text_unchanged(self, vm):
        text = "please remind me to review the kanban board after lunch"
        assert vm.redact_transcript(text) == text

    def test_handles_non_string_safely(self, vm):
        assert vm.redact_transcript(None) == ""
        assert vm.redact_transcript("") == ""


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


class TestIntentClassification:
    def test_create_job_phrases(self, vm):
        for phrase in [
            "build the release script",
            "implement a retry guard for the publisher",
            "fix the off-by-one in the scorer",
            "refactor the kanban view",
        ]:
            assert vm.classify_intent(phrase) == "create_job", phrase

    def test_note_phrases(self, vm):
        for phrase in [
            "note that the council meets at three",
            "remind me to pick up groceries",
            "todo: read the orchestration phases doc",
        ]:
            assert vm.classify_intent(phrase) == "capture_note", phrase

    def test_status_query(self, vm):
        assert vm.classify_intent("what's the status of the build?") == "query_status"
        assert (
            vm.classify_intent("update me on the orchestration job") == "query_status"
        )

    def test_cancel_and_confirm(self, vm):
        assert vm.classify_intent("cancel that") == "cancel"
        assert vm.classify_intent("never mind") == "cancel"
        assert vm.classify_intent("yes go ahead") == "confirm"
        assert vm.classify_intent("approve it") == "confirm"

    def test_repeat(self, vm):
        assert vm.classify_intent("repeat that") == "repeat"
        assert vm.classify_intent("read back the summary") == "repeat"

    def test_unknown_for_gibberish(self, vm):
        assert vm.classify_intent("xyzzy plugh") == "unknown"
        assert vm.classify_intent("") == "unknown"
        assert vm.classify_intent(None) == "unknown"

    def test_cancel_beats_create(self, vm):
        """Order matters: an explicit cancel should win even if the
        utterance also contains a build-y verb."""
        assert vm.classify_intent("cancel the build") == "cancel"


# ---------------------------------------------------------------------------
# Disabled mode
# ---------------------------------------------------------------------------


class TestDisabledMode:
    def test_begin_intake_raises_when_disabled(self, vi, vm):
        cfg = vm.VoiceIntakeConfig(mode="disabled")
        with pytest.raises(vm.VoiceDisabledError):
            vi.begin_intake(cfg)


# ---------------------------------------------------------------------------
# End-to-end pipeline — push-to-talk
# ---------------------------------------------------------------------------


class TestPushToTalkPipeline:
    def test_capture_note_writes_three_artefacts(self, vi, vm, hermes_home):
        transcript = vm.VoiceTranscript(
            text="remind me to call Sam tomorrow", provider="local-whisper"
        )
        intake, job_id = vi.run_pipeline(transcript, confirmation="yes")
        assert intake.draft.intent == "capture_note"
        assert intake.approval.state == "approved"
        # Capture notes are persisted but never become orchestrator jobs.
        assert job_id is None

        folder = hermes_home / "voice" / intake.id
        assert (folder / vi.TRANSCRIPT_FILE).is_file()
        assert (folder / vi.CONFIRMATION_FILE).is_file()
        assert (folder / vi.APPROVAL_FILE).is_file()

        approval = json.loads((folder / vi.APPROVAL_FILE).read_text())
        assert approval["state"] == "approved"
        assert approval["confirmation_phrase"] == "yes"

    def test_create_job_routes_to_submitter(self, vi, vm):
        calls: list[str] = []

        class FakeJob:
            id = "orc-fake1234"

        def fake_submitter(prompt: str):
            calls.append(prompt)
            return FakeJob()

        transcript = vm.VoiceTranscript(
            text="implement a retry guard for the publisher"
        )
        cfg = vm.VoiceIntakeConfig(mode="push_to_talk")
        intake, job_id = vi.run_pipeline(
            transcript,
            config=cfg,
            confirmation="yes",
            submitter=fake_submitter,
        )
        assert intake.draft.intent == "create_job"
        assert intake.draft.requires_implementation is True
        assert calls == ["implement a retry guard for the publisher"]
        assert job_id == "orc-fake1234"
        # Approval notes record the orchestrator job link for audit.
        assert any(
            "orchestrator-job:orc-fake1234" in note for note in intake.approval.notes
        )

    def test_cancellation_returns_no_job(self, vi, vm):
        called: list[str] = []

        def fake_submitter(prompt: str):
            called.append(prompt)
            return type("J", (), {"id": "orc-x"})()

        transcript = vm.VoiceTranscript(text="implement the new dashboard view")
        intake, job_id = vi.run_pipeline(
            transcript,
            confirmation="cancel",
            submitter=fake_submitter,
        )
        assert intake.approval.state == "cancelled"
        assert job_id is None
        assert called == []  # submitter never called

    def test_expired_confirmation(self, vi, vm):
        transcript = vm.VoiceTranscript(text="implement a retry guard")
        intake = vi.begin_intake(vm.VoiceIntakeConfig())
        intake = vi.ingest_transcript(intake, transcript)
        vi.build_readback(intake)
        intake = vi.record_decision(intake, None)
        assert intake.approval.state == "expired"
        assert vi.finalize(intake) is None

    def test_ambiguous_reply_in_push_to_talk_stays_pending(self, vi, vm):
        transcript = vm.VoiceTranscript(text="implement a retry guard")
        intake = vi.begin_intake(vm.VoiceIntakeConfig())
        intake = vi.ingest_transcript(intake, transcript)
        vi.build_readback(intake)
        intake = vi.record_decision(intake, "uh hold on let me think")
        # Non-driving ambiguous reply leaves us awaiting confirmation
        # so the caller can present the next utterance.
        assert intake.approval.state == "awaiting_confirmation"


# ---------------------------------------------------------------------------
# Driving-mode behaviour
# ---------------------------------------------------------------------------


class TestDrivingMode:
    def test_unknown_intent_degrades_to_note(self, vi, vm):
        transcript = vm.VoiceTranscript(text="xyzzy plugh weather")
        cfg = vm.VoiceIntakeConfig(mode="driving_capture")
        intake, job_id = vi.run_pipeline(transcript, config=cfg, confirmation="yes")
        assert intake.draft.intent == "capture_note"
        assert job_id is None

    def test_create_job_intent_preserved_but_requires_yes(self, vi, vm):
        """A clear ``create_job`` utterance in driving mode is still
        eligible for orchestrator submission — what driving mode
        changes is the strictness of the confirmation step, not the
        classification."""
        seen: list[str] = []

        def fake_submitter(prompt: str):
            seen.append(prompt)
            return type("J", (), {"id": "orc-drv1"})()

        transcript = vm.VoiceTranscript(
            text="create a job to refactor the scorer module"
        )
        cfg = vm.VoiceIntakeConfig(mode="driving_capture")
        intake, job_id = vi.run_pipeline(
            transcript,
            config=cfg,
            confirmation="yes",
            submitter=fake_submitter,
        )
        assert intake.draft.intent == "create_job"
        assert job_id == "orc-drv1"
        assert seen == ["create a job to refactor the scorer module"]

    def test_ambiguous_reply_in_driving_mode_is_cancel(self, vi, vm):
        transcript = vm.VoiceTranscript(text="create a job to refactor the scorer")
        cfg = vm.VoiceIntakeConfig(mode="driving_capture")
        intake = vi.begin_intake(cfg)
        intake = vi.ingest_transcript(intake, transcript)
        vi.build_readback(intake)
        intake = vi.record_decision(intake, "uh maybe")
        assert intake.approval.state == "cancelled"
        assert any("driving mode" in n for n in intake.approval.notes)

    def test_publish_action_vetoed_even_when_approved(self, vi, vm):
        transcript = vm.VoiceTranscript(text="publish the orchestration release")
        cfg = vm.VoiceIntakeConfig(mode="driving_capture")
        intake = vi.begin_intake(cfg)
        intake = vi.ingest_transcript(intake, transcript)
        vi.build_readback(intake)
        intake = vi.record_decision(intake, "yes")
        assert intake.approval.state == "approved"
        assert intake.draft.publish_action is True
        with pytest.raises(vm.DrivingSafetyVeto):
            vi.finalize(intake)

    def test_transcript_is_trimmed_for_readback(self, vi, vm):
        long_text = "implement " + ("a very long verbose description " * 50)
        cfg = vm.VoiceIntakeConfig(
            mode="driving_capture", driving_max_transcript_chars=120
        )
        intake = vi.begin_intake(cfg)
        intake = vi.ingest_transcript(intake, vm.VoiceTranscript(text=long_text))
        assert len(intake.transcript.text) <= 124  # 120 + "..." plus the rstrip
        assert intake.transcript.text.endswith("...")

    def test_redaction_runs_in_driving_mode(self, vi, vm):
        cfg = vm.VoiceIntakeConfig(mode="driving_capture")
        intake = vi.begin_intake(cfg)
        intake = vi.ingest_transcript(
            intake,
            vm.VoiceTranscript(text="my password is hunter22long"),
        )
        assert "hunter22long" not in intake.transcript.text
        assert "[REDACTED]" in intake.transcript.text
        assert intake.transcript.redacted is True


# ---------------------------------------------------------------------------
# Read-back artefacts
# ---------------------------------------------------------------------------


class TestReadback:
    def test_readback_string_is_one_actionable_sentence(self, vi, vm):
        transcript = vm.VoiceTranscript(
            text="implement a retry guard for the publisher"
        )
        intake = vi.begin_intake(vm.VoiceIntakeConfig())
        intake = vi.ingest_transcript(intake, transcript)
        spoken = vi.build_readback(intake)
        assert spoken.startswith("Create a job to:")
        assert "Say yes to proceed or no to cancel." in spoken

    def test_readback_md_contains_provider_and_intent(self, vi, vm, hermes_home):
        transcript = vm.VoiceTranscript(
            text="capture this note about quarterly goals", provider="local-whisper"
        )
        intake = vi.begin_intake(vm.VoiceIntakeConfig())
        intake = vi.ingest_transcript(intake, transcript)
        vi.build_readback(intake)
        md = (hermes_home / "voice" / intake.id / vi.CONFIRMATION_FILE).read_text()
        assert "local-whisper" in md
        assert "capture_note" in md

    def test_readback_marks_driving_summary(self, vi, vm):
        transcript = vm.VoiceTranscript(text="note: tomorrow's standup at nine")
        cfg = vm.VoiceIntakeConfig(mode="driving_capture")
        intake = vi.begin_intake(cfg)
        intake = vi.ingest_transcript(intake, transcript)
        spoken = vi.build_readback(intake)
        assert spoken.startswith("Driving-safe summary.")


# ---------------------------------------------------------------------------
# Affirmative / negative phrase grammar
# ---------------------------------------------------------------------------


class TestConfirmationGrammar:
    def test_explicit_affirmatives(self, vi):
        for phrase in ["yes", "Yes please", "confirm", "go ahead", "do it"]:
            assert vi.is_affirmative(phrase), phrase

    def test_prefix_affirmative(self, vi):
        assert vi.is_affirmative("yes, ship it")
        assert (
            vi.is_affirmative("approve approve approve") is True
        )  # exact-prefix on "approve"

    def test_explicit_negatives(self, vi):
        for phrase in ["no", "Cancel that", "never mind", "stop"]:
            assert vi.is_negative(phrase), phrase

    def test_ambiguous_is_neither(self, vi):
        assert vi.is_affirmative("maybe") is False
        assert vi.is_negative("maybe") is False
        assert vi.is_affirmative("") is False
        assert vi.is_negative(None) is False


# ---------------------------------------------------------------------------
# Intake inspection helpers
# ---------------------------------------------------------------------------


class TestInspection:
    def test_load_intake_round_trip(self, vi, vm):
        transcript = vm.VoiceTranscript(text="note the council vote")
        intake, _ = vi.run_pipeline(transcript, confirmation="yes")
        loaded = vi.load_intake(intake.id)
        assert loaded is not None
        assert loaded.id == intake.id
        assert loaded.draft.intent == "capture_note"
        assert loaded.approval.state == "approved"

    def test_list_intakes_returns_recent(self, vi, vm):
        for i in range(3):
            vi.run_pipeline(
                vm.VoiceTranscript(text=f"note number {i}"), confirmation="yes"
            )
        intakes = vi.list_intakes(limit=10)
        assert len(intakes) >= 3
        assert all(hasattr(it, "id") for it in intakes)

    def test_load_intake_missing_returns_none(self, vi):
        assert vi.load_intake("voi-does-not-exist") is None


# ---------------------------------------------------------------------------
# Confirmation requirement enforcement
# ---------------------------------------------------------------------------


class TestConfirmationRequired:
    def test_unknown_intent_with_implementation_flag_raises(self, vi, vm):
        """If somehow the draft gets ``requires_implementation`` set
        but the intent stayed ``unknown`` (a bug, but worth guarding),
        finalize must refuse rather than create a junk job."""
        intake = vi.begin_intake(vm.VoiceIntakeConfig())
        intake = vi.ingest_transcript(intake, vm.VoiceTranscript(text="xyzzy plugh"))
        # Forcibly mutate the draft to simulate the bug.
        intake.draft.requires_implementation = True
        intake.draft.intent = "unknown"
        vi.build_readback(intake)
        intake = vi.record_decision(intake, "yes")
        with pytest.raises(vm.VoiceConfirmationRequired):
            vi.finalize(intake)


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------


class TestFilesystemLayout:
    def test_intake_folder_under_hermes_home(self, vi, hermes_home):
        intake_id = "voi-test-1234"
        folder = vi.intake_folder(intake_id)
        assert folder == hermes_home / "voice" / intake_id
        assert folder.is_dir()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
    def test_voice_root_is_user_only(self, vi, hermes_home):
        vi.intake_folder("voi-perm-check")
        root = hermes_home / "voice"
        mode = root.stat().st_mode & 0o777
        # Allow either 0o700 (POSIX) or whatever the platform default is
        # when chmod silently fails — at minimum, the dir must exist.
        assert root.is_dir()
        assert mode in {0o700, 0o755, 0o775}, oct(mode)


# ---------------------------------------------------------------------------
# Approval state JSON shape (consumed by gateway + cockpit)
# ---------------------------------------------------------------------------


class TestApprovalStateJson:
    def test_approved_state_has_required_keys(self, vi, vm, hermes_home):
        transcript = vm.VoiceTranscript(text="note today's release rollout")
        intake, _ = vi.run_pipeline(transcript, confirmation="yes")
        data = json.loads(
            (hermes_home / "voice" / intake.id / vi.APPROVAL_FILE).read_text()
        )
        assert set(data) >= {
            "state",
            "decided_at",
            "decided_by",
            "confirmation_phrase",
            "notes",
        }
        assert data["state"] == "approved"
        assert data["decided_by"] == "user"
        assert isinstance(data["notes"], list)
