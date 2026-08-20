"""Tests for credential scrubbing of tool output."""

from tools.tokenjuice.scrub import scrub_credentials


def test_keyvalue_secret_redacted_keeps_prefix():
    out = scrub_credentials("export API_KEY=supersecretvalue12345")
    assert "supersecretvalue12345" not in out
    assert "[REDACTED]" in out
    assert "supe" in out  # 4-char prefix preserved for context


def test_quoted_secret_redacted():
    out = scrub_credentials('config: {"password": "hunter2hunter2"}')
    assert "hunter2hunter2" not in out
    assert "[REDACTED]" in out


def test_bearer_header_redacted():
    out = scrub_credentials("Authorization: Bearer abcdef1234567890token")
    assert "abcdef1234567890token" not in out
    assert "Bearer abcd" in out


def test_provider_key_shapes_redacted():
    for secret in ("sk-ABCDEFGH12345678", "ghp_ABCDEFGHIJKL1234", "xoxb-1234567890-abcdef"):
        out = scrub_credentials(f"token is {secret} ok")
        assert secret not in out, secret
        assert "[REDACTED]" in out


def test_pem_private_key_redacted():
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA1234567890abcdef\nmorebase64==\n"
        "-----END RSA PRIVATE KEY-----"
    )
    out = scrub_credentials(f"key:\n{pem}\n")
    assert "MIIEpAIBAAKCAQEA1234567890abcdef" not in out
    assert "[REDACTED]" in out


def test_non_secret_text_unchanged():
    text = "On branch main\nnothing to commit, working tree clean"
    assert scrub_credentials(text) == text


def test_empty_passthrough():
    assert scrub_credentials("") == ""
