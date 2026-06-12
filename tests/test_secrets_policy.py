"""Tests for ``muse_cli.secrets_policy``.

These tests cover the public surface only: secret-name classification,
the ``looks_like_secret`` heuristic, redaction (and its idempotence),
the scanners for text / files / diffs, and ``assert_not_committable``.

The module is dependency-free, so the tests are too — no fixtures
beyond ``tmp_path``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from muse_cli import secrets_policy as sp


# ---------------------------------------------------------------------------
# is_secret_name
# ---------------------------------------------------------------------------


class TestIsSecretName:
    @pytest.mark.parametrize(
        "name",
        [
            "OPENAI_API_KEY",
            "GITHUB_TOKEN",
            "ANTHROPIC_API_KEY",
            "FOO_TOKEN",
            "BAR_SECRET",
            "BAZ_PASSWORD",
            "QUX_PRIVATE_KEY",
            "AWS_SECRET_ACCESS_KEY",
            "VERCEL_TOKEN",
            "SUPABASE_SERVICE_ROLE_KEY",
        ],
    )
    def test_credential_shaped_names(self, name):
        assert sp.is_secret_name(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "PATH",
            "HOME",
            "USER",
            "MODEL",
            "HERMES_HOME",
            "TZ",
            "LANG",
            "",
        ],
    )
    def test_non_credential_names(self, name):
        assert sp.is_secret_name(name) is False

    def test_is_case_insensitive(self):
        assert sp.is_secret_name("openai_api_key") is True


# ---------------------------------------------------------------------------
# looks_like_secret
# ---------------------------------------------------------------------------


class TestLooksLikeSecret:
    def test_openai_prefix(self):
        token = "sk-" + "A" * 40
        assert sp.looks_like_secret(token) == "known_prefix"

    def test_anthropic_prefix(self):
        token = "sk-ant-" + "x" * 40
        assert sp.looks_like_secret(token) == "known_prefix"

    def test_github_pat(self):
        token = "ghp_" + "B" * 36
        assert sp.looks_like_secret(token) == "known_prefix"

    def test_aws_access_key_id(self):
        token = "AKIAIOSFODNN7EXAMPLE"
        assert sp.looks_like_secret(token) == "known_prefix"

    def test_google_api_key(self):
        token = "AIza" + "B" * 35
        assert sp.looks_like_secret(token) == "known_prefix"

    def test_pem_block(self):
        pem = textwrap.dedent(
            """\
            -----BEGIN RSA PRIVATE KEY-----
            MIIEowIBAAKCAQEAxxx
            -----END RSA PRIVATE KEY-----
            """
        )
        assert sp.looks_like_secret(pem) == "pem_block"

    def test_high_entropy_token(self):
        token = "aB3" + "x" * 30 + "Y9"  # ≥32 chars, mixed case + digit
        assert sp.looks_like_secret(token) == "high_entropy"

    def test_short_value_is_not_secret(self):
        assert sp.looks_like_secret("hello") is None
        assert sp.looks_like_secret("abc=123") is None

    def test_low_entropy_long_value_is_not_secret(self):
        # 40 lowercase letters, only one character class → not flagged.
        assert sp.looks_like_secret("a" * 40) is None

    def test_empty_string(self):
        assert sp.looks_like_secret("") is None


# ---------------------------------------------------------------------------
# redact / redact_env_dict
# ---------------------------------------------------------------------------


class TestRedact:
    def test_redacts_openai_key(self):
        text = "OPENAI_API_KEY=sk-" + "A" * 40
        out = sp.redact(text)
        assert "sk-" + "A" * 40 not in out
        assert "<redacted:openai>" in out

    def test_redacts_anthropic_key(self):
        token = "sk-ant-" + "Z" * 40
        out = sp.redact(f"key: {token}")
        assert token not in out
        assert "<redacted:anthropic>" in out

    def test_redacts_github_pat(self):
        token = "ghp_" + "C" * 36
        out = sp.redact(token)
        assert token not in out
        assert "<redacted:github_pat>" in out

    def test_redacts_pem_block(self):
        pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nfoobar\n-----END OPENSSH PRIVATE KEY-----"
        out = sp.redact(pem)
        assert "foobar" not in out
        assert "<redacted:private_key>" in out

    def test_redacts_high_entropy_token(self):
        token = "Ab3" + "kZ" * 16
        out = sp.redact(f"value={token}")
        assert token not in out

    def test_does_not_redact_low_entropy(self):
        text = "hello world this is a normal sentence"
        assert sp.redact(text) == text

    def test_empty_string(self):
        assert sp.redact("") == ""

    def test_idempotent(self):
        text = "OPENAI_API_KEY=sk-" + "A" * 40
        once = sp.redact(text)
        twice = sp.redact(once)
        assert once == twice

    def test_redact_env_dict_redacts_credential_names(self):
        env = {
            "OPENAI_API_KEY": "sk-" + "A" * 40,
            "PATH": "/usr/bin",
            "GH_TOKEN": "ghp_" + "B" * 36,
        }
        out = sp.redact_env_dict(env)
        assert out["OPENAI_API_KEY"] == "<redacted:OPENAI_API_KEY>"
        assert out["GH_TOKEN"] == "<redacted:GH_TOKEN>"
        assert out["PATH"] == "/usr/bin"

    def test_redact_env_dict_handles_empty_value(self):
        out = sp.redact_env_dict({"OPENAI_API_KEY": ""})
        assert out["OPENAI_API_KEY"] == ""


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------


class TestScanText:
    def test_empty_text_returns_no_findings(self):
        assert sp.scan_text("") == []

    def test_finds_env_assignment(self):
        findings = sp.scan_text("OPENAI_API_KEY=sk-1234\nOTHER=value\n")
        assert any(f.kind == "env_name" for f in findings)

    def test_excerpt_does_not_contain_raw_secret(self):
        token = "sk-" + "A" * 40
        findings = sp.scan_text(f"key={token}")
        assert findings
        for f in findings:
            assert token not in f.excerpt

    def test_does_not_double_count_env_assignment_for_known_prefix(self):
        token = "sk-" + "A" * 40
        findings = sp.scan_text(f"OPENAI_API_KEY={token}")
        # The env-name finder fires first and short-circuits the rest
        # of that line.
        assert all(f.kind == "env_name" for f in findings)

    def test_location_and_line_number(self):
        findings = sp.scan_text("noop\nOPENAI_API_KEY=x\n", location="foo.env")
        assert findings
        assert findings[0].location == "foo.env"
        assert findings[0].line == 2


class TestScanFile:
    def test_scans_dotenv_file(self, tmp_path: Path):
        env = tmp_path / ".env"
        env.write_text("OPENAI_API_KEY=sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n")
        findings = sp.scan_file(env)
        assert findings

    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert sp.scan_file(tmp_path / "nope") == []

    def test_binary_file_returns_empty(self, tmp_path: Path):
        binary = tmp_path / "blob.bin"
        binary.write_bytes(b"\x00\x01\x02\x03\xff\xfe")
        assert sp.scan_file(binary) == []


class TestScanDiff:
    def test_only_plus_lines_count(self):
        diff = textwrap.dedent(
            """\
            --- a/.env
            +++ b/.env
            -OPENAI_API_KEY=sk-OLDOLDOLDOLDOLDOLDOLDOLDOLDOLDOLDOLD
            +OPENAI_API_KEY=sk-NEWNEWNEWNEWNEWNEWNEWNEWNEWNEWNEWNEW
            """
        )
        findings = sp.scan_diff(diff)
        assert findings
        # The removed line MUST NOT be flagged.
        assert all("NEW" in f.excerpt or "..." in f.excerpt for f in findings)

    def test_diff_picks_up_file_path(self):
        diff = textwrap.dedent(
            """\
            --- a/config.yaml
            +++ b/config.yaml
            +OPENAI_API_KEY=sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
            """
        )
        findings = sp.scan_diff(diff)
        assert findings
        assert findings[0].location == "config.yaml"

    def test_empty_diff_returns_no_findings(self):
        assert sp.scan_diff("") == []


# ---------------------------------------------------------------------------
# assert_not_committable
# ---------------------------------------------------------------------------


class TestAssertNotCommittable:
    def test_clean_text_does_not_raise(self):
        sp.assert_not_committable("def foo():\n    return 1\n")

    def test_secret_raises(self):
        with pytest.raises(sp.SecretLeakError) as ei:
            sp.assert_not_committable("OPENAI_API_KEY=sk-" + "A" * 40)
        assert ei.value.findings

    def test_error_message_does_not_contain_secret(self):
        token = "sk-" + "A" * 40
        with pytest.raises(sp.SecretLeakError) as ei:
            sp.assert_not_committable(f"key={token}")
        assert token not in str(ei.value)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class TestSources:
    def test_available_sources_returns_some(self):
        # process_env and config_yaml_ref are always available.
        names = {s.name for s in sp.available_sources()}
        assert "process_env" in names
        assert "config_yaml_ref" in names

    def test_get_secret_reads_from_env(self):
        env = {"FOO_API_KEY": "value-xxx"}
        assert sp.get_secret("FOO_API_KEY", env=env) == "value-xxx"

    def test_get_secret_returns_none_when_missing(self):
        assert sp.get_secret("DOES_NOT_EXIST_TOKEN", env={}) is None

    def test_get_secret_uses_os_environ_by_default(self, monkeypatch):
        monkeypatch.setenv("HERMES_TEST_TOKEN", "abc")
        assert sp.get_secret("HERMES_TEST_TOKEN") == "abc"
