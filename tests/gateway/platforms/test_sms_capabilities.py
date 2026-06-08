"""Tests for the SMS adapter capability/health describe surface.

Covers the additive ``capabilities()`` / ``health()`` describe methods on
``gateway.platforms.sms.SmsAdapter`` (grain g-gateway-parity / FU-19):

  - dict shape, key set, and value types are stable;
  - ``health()`` is honest and safe to call without live credentials, a
    webhook URL, or network access (degrades to ``healthy: False`` + reason);
  - the describe surface never raises and performs no I/O;
  - existing entry points (``format_message`` / ``truncate_message``) are
    unchanged — purely additive.
"""

import os
from unittest.mock import patch

import pytest

from gateway.config import Platform, PlatformConfig


# ── Adapter construction helpers ────────────────────────────────────


# Credentials sufficient to *construct* the adapter (SmsAdapter.__init__
# reads TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN from os.environ). The
# describe surface must still degrade honestly when the *operational*
# config (from-number, webhook URL) is missing.
_CTOR_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest",
    "TWILIO_AUTH_TOKEN": "tok",
}


def _make_adapter(env_extra=None):
    """Construct an SmsAdapter via its real __init__ with a controlled env.

    ``env_extra`` overlays additional env vars (e.g. a from-number or webhook
    URL) on top of the minimal constructor credentials.
    """
    from gateway.platforms.sms import SmsAdapter

    env = dict(_CTOR_ENV)
    if env_extra:
        env.update(env_extra)
    # clear=True so absent keys (TWILIO_PHONE_NUMBER, SMS_WEBHOOK_URL,
    # SMS_INSECURE_NO_SIGNATURE) are genuinely unset for the honesty checks.
    with patch.dict(os.environ, env, clear=True):
        pc = PlatformConfig(enabled=True, api_key="tok")
        return SmsAdapter(pc)


# ── capabilities() ──────────────────────────────────────────────────


class TestSmsCapabilities:
    def test_shape_keys_and_types(self):
        adapter = _make_adapter()
        caps = adapter.capabilities()

        assert isinstance(caps, dict)
        assert set(caps.keys()) == {
            "platform",
            "supports_media",
            "supports_threads",
            "supports_draft_streaming",
        }
        assert isinstance(caps["platform"], str)
        assert isinstance(caps["supports_media"], bool)
        assert isinstance(caps["supports_threads"], bool)
        assert isinstance(caps["supports_draft_streaming"], bool)

    def test_values_match_what_sms_actually_supports(self):
        adapter = _make_adapter()
        caps = adapter.capabilities()

        assert caps["platform"] == Platform.SMS.value == "sms"
        # SMS does not override send_image/send_image_file -> no real MMS.
        assert caps["supports_media"] is False
        # Each phone number is a flat DM; SMS has no thread concept.
        assert caps["supports_threads"] is False

    def test_draft_streaming_mirrors_base_hook(self):
        adapter = _make_adapter()
        caps = adapter.capabilities()
        # Mirrors BasePlatformAdapter.supports_draft_streaming (False for SMS).
        assert caps["supports_draft_streaming"] == adapter.supports_draft_streaming()
        assert caps["supports_draft_streaming"] is False

    def test_capabilities_is_stable_across_calls(self):
        adapter = _make_adapter()
        assert adapter.capabilities() == adapter.capabilities()


# ── health() ────────────────────────────────────────────────────────


class TestSmsHealth:
    def test_shape_keys_and_types(self):
        adapter = _make_adapter()
        h = adapter.health()

        assert isinstance(h, dict)
        assert set(h.keys()) == {"platform", "healthy", "detail", "running"}
        assert h["platform"] == "sms"
        assert isinstance(h["healthy"], bool)
        assert isinstance(h["detail"], str)
        assert isinstance(h["running"], bool)

    def test_unhealthy_without_from_number_or_webhook(self):
        # Only constructor creds present: no from-number, no webhook URL.
        adapter = _make_adapter()
        h = adapter.health()

        assert h["healthy"] is False
        assert h["detail"]  # non-empty, human-readable reason
        assert "TWILIO_PHONE_NUMBER" in h["detail"]
        assert "SMS_WEBHOOK_URL" in h["detail"]
        # Not connected -> not running.
        assert h["running"] is False

    def test_missing_from_number_reported(self):
        # Webhook URL present, from-number still missing.
        adapter = _make_adapter({"SMS_WEBHOOK_URL": "https://example.com/webhooks/twilio"})
        h = adapter.health()

        assert h["healthy"] is False
        assert "TWILIO_PHONE_NUMBER" in h["detail"]
        assert "SMS_WEBHOOK_URL" not in h["detail"]

    def test_healthy_when_from_number_and_webhook_present(self):
        adapter = _make_adapter(
            {
                "TWILIO_PHONE_NUMBER": "+15550001111",
                "SMS_WEBHOOK_URL": "https://example.com/webhooks/twilio",
            }
        )
        h = adapter.health()

        assert h["healthy"] is True
        assert h["detail"] == "ready"

    def test_insecure_no_signature_waives_webhook_requirement(self):
        # Dev escape hatch: no webhook URL but signature validation disabled.
        # health() reads SMS_INSECURE_NO_SIGNATURE live (mirroring connect()),
        # so the env override must be active when health() is called.
        from gateway.platforms.sms import SmsAdapter

        env = dict(_CTOR_ENV)
        env.update(
            {
                "TWILIO_PHONE_NUMBER": "+15550001111",
                "SMS_INSECURE_NO_SIGNATURE": "true",
            }
        )
        with patch.dict(os.environ, env, clear=True):
            adapter = SmsAdapter(PlatformConfig(enabled=True, api_key="tok"))
            h = adapter.health()

        assert h["healthy"] is True
        assert "SMS_WEBHOOK_URL" not in h["detail"]

    def test_health_does_no_network_io(self):
        # If health() tried to reach Twilio it would go through aiohttp's
        # ClientSession; patch it to explode so any network attempt fails loudly.
        adapter = _make_adapter()
        import aiohttp

        with patch.object(
            aiohttp, "ClientSession", side_effect=AssertionError("network at describe time")
        ):
            h = adapter.health()
        assert isinstance(h, dict)
        assert h["healthy"] is False

    def test_health_never_raises_on_bare_instance(self):
        # Even on a partially-constructed adapter (no __init__ attrs at all),
        # health()/capabilities() must degrade rather than raise.
        from gateway.platforms.sms import SmsAdapter

        bare = object.__new__(SmsAdapter)
        with patch.dict(os.environ, {}, clear=True):
            h = bare.health()
            caps = bare.capabilities()

        assert h["platform"] == "sms"
        assert h["healthy"] is False
        assert h["running"] is False
        assert caps["platform"] == "sms"
        assert caps["supports_media"] is False

    def test_health_stable_across_calls(self):
        adapter = _make_adapter()
        assert adapter.health() == adapter.health()


# ── No behavior regression on existing entry points ─────────────────


class TestSmsNoRegression:
    def test_format_message_still_strips_markdown(self):
        adapter = _make_adapter()
        assert adapter.format_message("**hello**") == "hello"

    def test_truncate_message_unchanged(self):
        adapter = _make_adapter()
        # A short message is returned as a single chunk, unmodified.
        chunks = adapter.truncate_message("hi there")
        assert chunks == ["hi there"]

    def test_max_message_length_constant_unchanged(self):
        from gateway.platforms.sms import MAX_SMS_LENGTH

        adapter = _make_adapter()
        assert adapter.MAX_MESSAGE_LENGTH == MAX_SMS_LENGTH == 1600


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
