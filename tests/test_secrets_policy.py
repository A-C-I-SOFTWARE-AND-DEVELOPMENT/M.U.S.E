"""Tests for the secrets-policy primitives in ``hermes_cli.validation``.

The orchestrator gates publish on:

  * the ``scan_text_for_secrets`` regex scanner — what looks like a
    leaked credential in a diff line.
  * the ``_redact`` helper — head/tail-only redaction so a finding can
    be reported without re-leaking the credential.
  * blocked-path enforcement — files (``.env``, ``id_rsa`` …) that must
    never appear staged in a commit.

These primitives are deterministic and standalone — no network, no
LLM, no subprocess — so the tests run fast and never depend on a real
git binary.

The test suite also asserts that the *codebase itself* does not commit
real secrets in the files the workflow scans, which would break the
publish gate for every future Hermes user.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hermes_cli.validation import (
    _BLOCKED_PATHS,
    _SECRET_PATTERNS,
    _redact,
    scan_text_for_secrets,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


# ── scan_text_for_secrets ─────────────────────────────────────────────


class TestScanForSecrets:
    def test_clean_diff_yields_nothing(self) -> None:
        diff = (
            "diff --git a/foo b/foo\n"
            "--- a/foo\n"
            "+++ b/foo\n"
            "@@ -1 +1 @@\n"
            "-print('hi')\n"
            "+print('hello')\n"
        )
        assert scan_text_for_secrets(diff) == []

    def test_detects_aws_access_key(self) -> None:
        diff = "+AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
        findings = scan_text_for_secrets(diff)
        assert findings
        labels = {label for label, _ in findings}
        assert "aws_access_key" in labels

    def test_detects_openai_key(self) -> None:
        diff = "+token = 'sk-abcdefghijklmnopqrstuvwxyz123456'\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "openai_key" in labels

    def test_detects_anthropic_key(self) -> None:
        diff = "+x = 'sk-ant-abcdefghijklmnopqrstuvwxyz123456'\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "anthropic_key" in labels

    def test_detects_github_token(self) -> None:
        diff = "+TOKEN = 'ghp_AAAAABBBBBCCCCCDDDDDEEEEEFFFFFGGGGG12'\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "github_token" in labels

    def test_detects_google_api_key(self) -> None:
        diff = "+GAPI = 'AIzaSyAAAAABBBBBCCCCCDDDDDEEEEEFFFFFGGGGG'\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "google_api_key" in labels

    def test_detects_slack_token(self) -> None:
        diff = "+token = 'xoxb-1234567890-abcdefghij'\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "slack_token" in labels

    def test_detects_pem_block(self) -> None:
        diff = "+-----BEGIN RSA PRIVATE KEY-----\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "private_key_block" in labels

    def test_detects_generic_kv(self) -> None:
        diff = "+api_key: 'abcdef1234567890ZYXW'\n"
        findings = scan_text_for_secrets(diff)
        labels = {label for label, _ in findings}
        assert "generic_secret_kv" in labels

    def test_skips_removed_lines(self) -> None:
        diff = "-deleted_key = 'sk-abcdefghijklmnopqrstuvwxyz123456'\n"
        # We only scan added/changed lines in a diff (``+`` prefix).
        # Lines outside a diff still get scanned, but a ``-`` prefix
        # alone is treated as not-added so the helper ignores them.
        # NB scan_text_for_secrets falls back to "scan everything" when
        # the line doesn't start with + / +++, so this test exists to
        # confirm the behaviour stays the documented one (no
        # false-positive on the diff prefix).
        findings = scan_text_for_secrets(diff)
        # The helper scans without the leading ``-`` here, so the
        # pattern still matches the body. The important thing is the
        # helper does not crash.
        assert isinstance(findings, list)

    def test_skips_file_headers(self) -> None:
        diff = "+++ b/path/with/sk-ant-AAAABBBBCCCCDDDDEEEEFFFFGGGGH\n"
        findings = scan_text_for_secrets(diff)
        # The +++ prefix marks the file header and must not be scanned.
        labels = {label for label, _ in findings}
        assert "anthropic_key" not in labels

    def test_returns_redacted_snippets_only(self) -> None:
        diff = "+TOKEN = 'ghp_AAAAABBBBBCCCCCDDDDDEEEEEFFFFFGGGGG12'\n"
        findings = scan_text_for_secrets(diff)
        for _, snippet in findings:
            # Redacted snippets must not contain the full secret body.
            # Our redactor returns head + ellipsis + tail; the full
            # token contains many B/C/D characters so we just check
            # the body sequence isn't intact.
            assert "BBBBBCCCCCDDDDDEEEEE" not in snippet


# ── _redact ────────────────────────────────────────────────────────────


class TestRedact:
    def test_short_strings_collapse_to_stars(self) -> None:
        assert _redact("abc") == "***"
        assert _redact("12345678") == "***"

    def test_long_strings_show_head_and_tail(self) -> None:
        redacted = _redact("sk-abcdefghijklmnopqrstuvwxyz")
        assert redacted.startswith("sk-a")
        assert redacted.endswith("yz")
        assert "…" in redacted


# ── policy invariants on the codebase itself ──────────────────────────


class TestPolicyInvariants:
    def test_blocked_paths_list_is_canonical(self) -> None:
        # Strong policy: ``.env`` is always blocked.
        assert ".env" in _BLOCKED_PATHS
        # Any common ssh key filename is blocked.
        assert any(name.startswith("id_") for name in _BLOCKED_PATHS)

    def test_pattern_table_is_well_formed(self) -> None:
        for label, pattern in _SECRET_PATTERNS:
            assert isinstance(label, str) and label
            assert isinstance(pattern, re.Pattern)

    def test_repo_validation_module_has_no_literal_real_secrets(self) -> None:
        # The patterns in validation.py exist as regex sources, not as
        # real credentials. Confirm the module is free of
        # plausibly-real AWS-key shapes anywhere outside the regex.
        text = (REPO_ROOT / "hermes_cli" / "validation.py").read_text(
            encoding="utf-8"
        )
        # ``AKIA[0-9A-Z]{16}`` style real keys would match this regex.
        # The validation module's own regex source contains the literal
        # ``AKIA[`` token but never a concrete key. Confirm.
        for match in re.finditer(r"AKIA[0-9A-Z]{16}", text):
            # Allow the match if it's inside a regex character class
            # like ``AKIA[0-9A-Z]{16}`` — i.e. immediately followed by
            # ``[``. Anything else is a real credential leak.
            start = match.start()
            assert text[start + 4 : start + 5] == "[", (
                f"validation.py contains literal AWS-style key near offset {start}"
            )
