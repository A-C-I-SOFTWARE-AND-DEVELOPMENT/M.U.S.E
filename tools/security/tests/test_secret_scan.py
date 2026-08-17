"""Tests for the credential scanner — Work Packet §9.2.

The most important property under test is negative: **no matched value ever
reaches the output.** ``test_values_never_reach_any_output`` asserts that over
every rule, against the full report, the suppression document and the printed
summary.

Every fake credential in this file is synthetic, built from a fixed prefix plus
padding. They are *supposed* to be found — the scanner flags its own test file,
which is why ``tools/security/tests/`` appears in the suppression file under
``test_fixture``.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from tools.security import secret_scan as ss

# --- synthetic samples, built rather than written, so no realistic literal ---
# FAKE_AWS deliberately avoids the words test/fake/example: several assertions
# below turn on a *production-path* hit staying `unreviewed`, and placeholder
# vocabulary inside the value would move it to `doc_example` instead.
FAKE_AWS = "AKIA" + "NOTREALQ3M7XR2VB"
FAKE_GITHUB = "ghp_" + "0" * 20 + "TestOnlyFakeToken1"
FAKE_ANTHROPIC = "sk-ant-" + "TestOnlyFakeValue" + "9" * 24
FAKE_OPENAI = "sk-proj-" + "TestOnlyFakeValue" + "7" * 20
FAKE_GOOGLE = "AIza" + "TestOnlyFakeValue123456789012345678"[:35]
FAKE_SLACK = "xoxb-000000000000-" + "TestOnlyFakeValue00000"
FAKE_NVIDIA = "nvapi-" + "TestOnlyFakeValue" + "3" * 30
HIGH_ENTROPY = "7Zq3XvB9nKp2LdWs4TyH8mCe1RfJ6uGaX4pQ"

ALL_FAKES = [
    FAKE_AWS,
    FAKE_GITHUB,
    FAKE_ANTHROPIC,
    FAKE_OPENAI,
    FAKE_GOOGLE,
    FAKE_SLACK,
    FAKE_NVIDIA,
    HIGH_ENTROPY,
]


# ---------------------------------------------------------------------------
# Locations only
# ---------------------------------------------------------------------------


def test_values_never_reach_any_output(tmp_path: Path) -> None:
    source = "\n".join(f'KEY_{i} = "{value}"' for i, value in enumerate(ALL_FAKES))
    findings = ss.scan_text(source, "src/app.py")
    assert findings, "fixtures produced no findings; the test would be vacuous"

    report = ss.build_report(
        tmp_path, findings, [], ss.ScanStats(), "0" * 40
    )
    suppressions = ss.build_suppression_document(
        ss.scan_text(source, "tests/test_app.py"), commit="0" * 40, added_by="test"
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        ss.print_summary(report, limit=100)

    surfaces = {
        "report json": json.dumps(report),
        "suppressions json": json.dumps(suppressions),
        "printed summary": buffer.getvalue(),
    }
    for value in ALL_FAKES:
        for name, blob in surfaces.items():
            assert value not in blob, f"{name} leaked a matched value"
            # Not even a distinctive tail of it.
            assert value[-12:] not in blob, f"{name} leaked a value fragment"


def test_report_declares_that_values_are_not_stored(tmp_path: Path) -> None:
    report = ss.build_report(tmp_path, [], [], ss.ScanStats(), "abc")
    assert report["values_stored"] is False
    assert "TRIAGE AID" in report["_disclaimer"]
    assert "not a finding of leaked credentials" in report["_disclaimer"].lower()


# ---------------------------------------------------------------------------
# Known prefixes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sample", "expected_rule"),
    [
        (FAKE_AWS, "aws_access_key_id"),
        (FAKE_GITHUB, "github_token"),
        (FAKE_ANTHROPIC, "anthropic_api_key"),
        (FAKE_OPENAI, "openai_api_key"),
        (FAKE_GOOGLE, "google_api_key"),
        (FAKE_SLACK, "slack_token"),
        (FAKE_NVIDIA, "nvidia_nim_key"),
        ("github_pat_" + "b" * 60, "github_pat_fine_grained"),
        ("glpat-" + "c" * 24, "gitlab_pat"),
        ("sk_live_" + "d" * 24, "stripe_secret_key"),
        ("SG." + "e" * 22 + "." + "f" * 22, "sendgrid_api_key"),
        ("npm_" + "g" * 36, "npm_token"),
        ("pypi-" + "h" * 40, "pypi_token"),
        ("hf_" + "i" * 36, "huggingface_token"),
        ("123456789:AA" + "j" * 33, "telegram_bot_token"),
        ("SK" + "0123456789abcdef" * 2, "twilio_api_key_sid"),
        ("sk-or-v1-" + "0123456789abcdef" * 4, "openrouter_api_key"),
    ],
)
def test_known_prefixes_are_detected(sample: str, expected_rule: str) -> None:
    findings = ss.scan_text(f'VALUE = "{sample}"\n', "src/prod.py")
    assert [f.rule for f in findings] == [expected_rule]
    assert findings[0].rule_kind == "known_prefix"
    assert findings[0].value_length == len(sample)


def test_structural_rules() -> None:
    pem = ss.scan_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", "keys/id_ed25519")
    assert [f.rule for f in pem] == ["private_key_header"]

    jwt_value = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "k" * 24
    jwt = ss.scan_text(f"AUTH = {jwt_value}\n", "src/prod.py")
    assert "jwt" in {f.rule for f in jwt}

    conn = ss.scan_text(
        "DSN = postgres://svcuser:Hx7fQ2mVt9Ls@db.internal:5432/app\n", "src/prod.py"
    )
    assert "connection_string_password" in {f.rule for f in conn}


def test_a_clean_file_produces_nothing() -> None:
    clean = (
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "API_KEY_ENV_NAME = 'OPENAI_API_KEY'\n"
        "url = 'https://api.example.com/v1/chat'\n"
    )
    assert ss.scan_text(clean, "src/math_utils.py") == []


def test_specific_rule_wins_over_generic_shape() -> None:
    findings = ss.scan_text(f'api_key = "{FAKE_ANTHROPIC}"\n', "src/prod.py")
    assert [f.rule for f in findings] == ["anthropic_api_key"]


# ---------------------------------------------------------------------------
# Entropy
# ---------------------------------------------------------------------------


def test_entropy_ordering_and_edges() -> None:
    assert ss.shannon_entropy("") == 0.0
    assert ss.shannon_entropy("aaaaaaaa") == 0.0
    assert ss.shannon_entropy(HIGH_ENTROPY) > 4.0
    assert ss.shannon_entropy("aaaaaaaa") < ss.shannon_entropy("password") < ss.shannon_entropy(
        HIGH_ENTROPY
    )


def test_charset_classification() -> None:
    assert ss.charset_class("deadbeef0123") == "hex"
    assert ss.charset_class("abc-DEF_123") == "base64url"
    assert ss.charset_class("abc+DEF/123=") == "base64"
    assert ss.charset_class("hello world!") == "printable_ascii"
    assert ss.charset_class("") == "empty"


def test_low_entropy_shape_hit_is_dropped_but_prefix_hit_is_not() -> None:
    # Shape-only rules carry an entropy floor...
    assert ss.scan_text('password = "aaaaaaaaaaaaaaaa"\n', "src/prod.py") == []
    # ...but a known prefix is structural evidence and is never dropped for it.
    low_entropy_prefix = "AKIA" + "A" * 16
    findings = ss.scan_text(f'k = "{low_entropy_prefix}"\n', "src/prod.py")
    assert [f.rule for f in findings] == ["aws_access_key_id"]


def test_entropy_is_reported_not_judged() -> None:
    findings = ss.scan_text(f'api_key = "{HIGH_ENTROPY}"\n', "src/prod.py")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.value_entropy_bits_per_char > 4.0
    assert finding.value_length == len(HIGH_ENTROPY)
    assert finding.value_charset == "base64url"
    # A high score does not become a verdict of "leaked".
    assert finding.proposed_triage == "unreviewed"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/unit/test_client.py", "test_fixture"),
        ("tests/conftest.py", "test_fixture"),
        ("apps/desktop/electron/backend-health.test.ts", "test_fixture"),
        ("apps/desktop/electron/store.spec.tsx", "test_fixture"),
        ("pkg/client/client_test.go", "test_fixture"),
        ("app/src/test/java/com/x/FooTest.kt", "test_fixture"),
        ("docs/getting-started.md", "doc_example"),
        ("website/docs/user-guide/messaging/slack.md", "doc_example"),
        ("website/docs/user-guide/skills/bundled/github/auth.md", "doc_example"),
        ("third_party/lib/config.py", "vendor"),
        ("node_modules/pkg/index.js", "vendor"),
        ("recovered-agent-sources/old/cli.py", "archived_source"),
        ("src/prod.py", "unreviewed"),
    ],
)
def test_path_context_drives_the_proposal(path: str, expected: str) -> None:
    findings = ss.scan_text(f'API_KEY = "{HIGH_ENTROPY}"\n', path)
    assert len(findings) == 1
    assert findings[0].proposed_triage == expected


def test_redaction_vocabulary_in_nearby_lines() -> None:
    source = (
        "# Patterns used to redact credentials out of tool output before logging.\n"
        f'api_key = "{HIGH_ENTROPY}"\n'
    )
    findings = ss.scan_text(source, "agent/logging_helpers.py")
    assert findings[0].proposed_triage == "redaction_code"
    assert "nearby:redaction_vocabulary" in findings[0].context_signals


def test_redaction_path_alone_is_enough() -> None:
    findings = ss.scan_text(f'api_key = "{HIGH_ENTROPY}"\n', "agent/redact.py")
    assert findings[0].proposed_triage == "redaction_code"


@pytest.mark.parametrize(
    "line",
    [
        'api_key = "${OPENAI_API_KEY}"',
        'auth_token = "env(SUPABASE_AUTH_SMS_TWILIO_AUTH_TOKEN)"',
        'token = "{resolved_token_path}"',
        'password = "{{ vault_db_password }}"',
        'TOKEN="$(muse cockpit token --json)"',
        "token = 'result of $(muse cockpit token)'",
    ],
)
def test_substitution_references_are_not_credentials(line: str) -> None:
    findings = ss.scan_text(line + "\n", "src/prod.py")
    assert findings, "fixture matched nothing; the assertion would be vacuous"
    assert findings[0].proposed_triage == "not_a_credential"
    assert findings[0].proposed_reason.startswith("the match is a substitution reference")


def test_backtick_delimited_command_substitution_lands_in_the_hand_queue() -> None:
    """A documented limitation, asserted rather than left to be discovered.

    ``token = `cat ~/.hermes/token``` uses backticks as the *delimiters*, so the
    captured value contains no backticks and value-level analysis cannot see
    that it is a command substitution. The scanner does not guess: the hit stays
    ``unreviewed`` and a human decides. Failing into the hand queue is the
    correct direction to fail.
    """
    findings = ss.scan_text("token = `cat ~/.hermes/token`\n", "scripts/deploy.sh")
    assert [f.proposed_triage for f in findings] == ["unreviewed"]


def test_substitution_reference_outranks_path_context() -> None:
    """A reference in production code is not a 'doc example'; it is not a value."""
    findings = ss.scan_text('api_key = "${OPENAI_API_KEY}"\n', "docs/setup.md")
    assert findings[0].proposed_triage == "not_a_credential"


def test_placeholder_vocabulary_proposes_doc_example() -> None:
    findings = ss.scan_text('api_key = "your-api-key-goes-here"\n', "src/prod.py")
    assert findings[0].proposed_triage == "doc_example"
    assert "placeholder_vocabulary" in findings[0].placeholder_signals


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------


def test_fingerprint_survives_line_drift_but_not_a_path_change() -> None:
    line = f'API_KEY = "{HIGH_ENTROPY}"\n'
    a = ss.scan_text(line, "src/prod.py")[0]
    b = ss.scan_text("import os\n\n\n" + line, "src/prod.py")[0]
    c = ss.scan_text(line, "src/other.py")[0]
    assert a.fingerprint == b.fingerprint
    assert a.line != b.line
    assert a.fingerprint != c.fingerprint


def test_fingerprint_changes_when_the_surrounding_line_changes() -> None:
    a = ss.scan_text(f'api_key = "{HIGH_ENTROPY}"\n', "src/prod.py")[0]
    b = ss.scan_text(f'refresh_token = "{HIGH_ENTROPY}"\n', "src/prod.py")[0]
    assert a.rule == b.rule == "generic_secret_assignment"
    assert a.fingerprint != b.fingerprint


def test_fingerprint_is_stable_when_only_the_value_changes() -> None:
    """Rotating a fixture's fake value keeps its suppression valid.

    This is a deliberate design choice, not an accident: the fingerprint is
    computed over the redacted line, so it identifies a *location and shape*
    rather than a secret.
    """
    a = ss.scan_text(f'API_KEY = "{HIGH_ENTROPY}"\n', "src/prod.py")[0]
    b = ss.scan_text('API_KEY = "9pQ4rT6yU8iO0aS2dF4gH6jK8lZ1xC3v"\n', "src/prod.py")[0]
    assert a.fingerprint == b.fingerprint


def test_redaction_removes_every_match_on_a_line() -> None:
    line = f'A = "{FAKE_AWS}"; B = "{FAKE_GITHUB}"'
    findings = ss.scan_text(line + "\n", "src/prod.py")
    assert len(findings) == 2
    spans = [(f.column - 1, f.column - 1 + f.value_length) for f in findings]
    redacted = ss._redact_line(line, spans)
    assert FAKE_AWS not in redacted
    assert FAKE_GITHUB not in redacted
    assert redacted.count(ss.REDACTED) == 2


# ---------------------------------------------------------------------------
# Suppressions
# ---------------------------------------------------------------------------


def _write_suppression_file(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "supp.json"
    path.write_text(
        json.dumps(
            {
                "version": ss.SUPPRESSION_FILE_VERSION,
                "_comment": ss.DISCLAIMER,
                "suppressions": entries,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_suppression_round_trip(tmp_path: Path) -> None:
    findings = ss.scan_text(f'API_KEY = "{HIGH_ENTROPY}"\n', "tests/test_x.py")
    doc = ss.build_suppression_document(findings, commit="abc", added_by="test")
    path = tmp_path / "supp.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    remaining, suppressed = ss.apply_suppressions(findings, ss.load_suppressions(path))
    assert remaining == []
    assert len(suppressed) == 1
    assert suppressed[0][1].triage == "test_fixture"


def test_unreviewed_findings_are_never_auto_suppressed() -> None:
    findings = ss.scan_text(f'API_KEY = "{HIGH_ENTROPY}"\n', "src/prod.py")
    doc = ss.build_suppression_document(findings, commit="abc", added_by="test")
    assert doc["suppressions"] == []
    assert "REQUIRES HAND REVIEW" in doc["_hand_review_required"] or "PROPOSALS" in doc[
        "_hand_review_required"
    ]


def test_true_positive_may_not_be_suppressed(tmp_path: Path) -> None:
    path = _write_suppression_file(
        tmp_path,
        [{"fingerprint": "deadbeef", "triage": "true_positive", "reason": "shipped"}],
    )
    with pytest.raises(ss.SuppressionError, match="may not be suppressed"):
        ss.load_suppressions(path)


def test_suppression_requires_a_reason(tmp_path: Path) -> None:
    path = _write_suppression_file(
        tmp_path, [{"fingerprint": "deadbeef", "triage": "test_fixture", "reason": "  "}]
    )
    with pytest.raises(ss.SuppressionError, match="reason is required"):
        ss.load_suppressions(path)


def test_suppression_requires_a_target(tmp_path: Path) -> None:
    path = _write_suppression_file(
        tmp_path, [{"triage": "test_fixture", "reason": "because"}]
    )
    with pytest.raises(ss.SuppressionError, match="fingerprint or a path_glob"):
        ss.load_suppressions(path)


def test_unknown_triage_bucket_is_rejected(tmp_path: Path) -> None:
    path = _write_suppression_file(
        tmp_path,
        [{"fingerprint": "d", "triage": "probably_fine", "reason": "vibes"}],
    )
    with pytest.raises(ss.SuppressionError, match="is not one of"):
        ss.load_suppressions(path)


def test_unsupported_suppression_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "supp.json"
    path.write_text(json.dumps({"version": 99, "suppressions": []}), encoding="utf-8")
    with pytest.raises(ss.SuppressionError, match="unsupported"):
        ss.load_suppressions(path)


def test_path_glob_suppression(tmp_path: Path) -> None:
    findings = ss.scan_text(f'API_KEY = "{HIGH_ENTROPY}"\n', "vendor/lib/config.py")
    path = _write_suppression_file(
        tmp_path,
        [
            {
                "path_glob": "vendor/**",
                "triage": "vendor",
                "reason": "vendored third-party tree",
            }
        ],
    )
    remaining, suppressed = ss.apply_suppressions(findings, ss.load_suppressions(path))
    assert remaining == []
    assert len(suppressed) == 1


def test_suppression_scoped_to_a_rule_does_not_hide_other_rules(tmp_path: Path) -> None:
    source = f'A = "{FAKE_AWS}"\nB = "{FAKE_GITHUB}"\n'
    findings = ss.scan_text(source, "src/prod.py")
    path = _write_suppression_file(
        tmp_path,
        [
            {
                "path_glob": "src/*",
                "rule": "aws_access_key_id",
                "triage": "test_fixture",
                "reason": "scoped",
            }
        ],
    )
    remaining, suppressed = ss.apply_suppressions(findings, ss.load_suppressions(path))
    assert [f.rule for f in remaining] == ["github_token"]
    assert [f.rule for f, _ in suppressed] == ["aws_access_key_id"]


# ---------------------------------------------------------------------------
# The shipped suppression file
# ---------------------------------------------------------------------------

SHIPPED = Path(__file__).resolve().parents[1] / "secret_scan_suppressions.json"


def test_shipped_suppression_file_is_valid_and_versioned() -> None:
    assert SHIPPED.is_file(), SHIPPED
    doc = json.loads(SHIPPED.read_text(encoding="utf-8"))
    assert doc["version"] == ss.SUPPRESSION_FILE_VERSION
    assert len(doc["repo_commit"]) == 40
    assert doc["scanner"] == f"{ss.SCANNER_NAME}@{ss.SCANNER_VERSION}"
    suppressions = ss.load_suppressions(SHIPPED)  # validates every entry
    assert suppressions, "the shipped file is empty"
    assert all(s.reason and s.added_by for s in suppressions)
    assert all(s.triage != "true_positive" for s in suppressions)


def test_shipped_suppression_file_contains_no_matched_values() -> None:
    """Locations only: no entry may carry anything that looks like a credential."""
    text = SHIPPED.read_text(encoding="utf-8")
    doc = json.loads(text)
    allowed_keys = {
        "fingerprint",
        "rule",
        "path",
        "triage",
        "reason",
        "added_at",
        "added_by",
    }
    for entry in doc["suppressions"]:
        assert set(entry) <= allowed_keys, set(entry) - allowed_keys
        assert entry["rule"] in ss.RULES_BY_NAME
        assert len(entry["fingerprint"]) == 16

    # Re-scan the suppression file itself; it must not trip any known-prefix or
    # structural rule, which is the strongest available check that no credential
    # was copied into it.
    self_findings = ss.scan_text(text, "tools/security/secret_scan_suppressions.json")
    assert [f.rule for f in self_findings if f.rule_kind != "shape"] == []


# ---------------------------------------------------------------------------
# Walk policy
# ---------------------------------------------------------------------------


def test_scan_tree_skips_excluded_dirs_and_binaries(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(f'K = "{FAKE_AWS}"\n', encoding="utf-8")
    for excluded in ("node_modules", ".git", "__pycache__", ".venv", "dist"):
        directory = tmp_path / excluded
        directory.mkdir()
        (directory / "leak.py").write_text(f'K = "{FAKE_GITHUB}"\n', encoding="utf-8")
    (tmp_path / "model.safetensors").write_text(
        f'K = "{FAKE_GITHUB}"\n', encoding="utf-8"
    )
    (tmp_path / "blob.dat").write_bytes(b"\x00\x01" + FAKE_GITHUB.encode())

    findings, stats = ss.scan_tree(tmp_path)
    assert [f.rule for f in findings] == ["aws_access_key_id"]
    assert findings[0].path == "src/app.py"
    assert stats.skipped_binary_suffix >= 1
    assert stats.files_scanned >= 1


def test_scan_tree_records_what_it_skipped(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("x" * 5000, encoding="utf-8")
    _, stats = ss.scan_tree(tmp_path, max_bytes=1000)
    assert stats.skipped_too_large == 1
    assert stats.files_scanned == 0


def test_very_long_lines_are_skipped(tmp_path: Path) -> None:
    """A minified bundle is noise, and skipping it must be visible in the code."""
    source = "// " + "a" * 9000 + f' "{FAKE_AWS}"\n'
    assert ss.scan_text(source, "src/bundle.js") == []
    assert ss.scan_text(f'K = "{FAKE_AWS}"\n', "src/bundle.js")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_selftest_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert ss.main(["--selftest"]) == 0
    assert "SELFTEST PASSED" in capsys.readouterr().out


def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "tree"
    (tree / "tests").mkdir(parents=True)
    (tree / "tests" / "test_client.py").write_text(
        f'TOKEN = "{FAKE_GITHUB}"\n', encoding="utf-8"
    )
    (tree / "app.py").write_text(f'TOKEN = "{FAKE_AWS}"\n', encoding="utf-8")

    report_path = tmp_path / "report.json"
    proposed = tmp_path / "proposed.json"
    code = ss.main(
        [
            "--root",
            str(tree),
            "--commit",
            "0" * 40,
            "--json",
            str(report_path),
            "--propose-suppressions",
            str(proposed),
            "--fail-on-unsuppressed",
        ]
    )
    assert code == 1, "an unreviewed finding must fail the CI gate"
    out = capsys.readouterr().out
    assert "TRIAGE AID" in out
    assert FAKE_AWS not in out and FAKE_GITHUB not in out

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["repo_commit"] == "0" * 40
    assert report["unsuppressed_total"] == 2

    doc = json.loads(proposed.read_text(encoding="utf-8"))
    # Only the test fixture is auto-proposed; app.py stays in the queue.
    assert [e["path"] for e in doc["suppressions"]] == ["tests/test_client.py"]
    assert "REQUIRES HAND REVIEW" in doc["suppressions"][0]["added_by"]

    # Apply it: the fixture is suppressed, the production hit is not.
    code2 = ss.main(
        [
            "--root",
            str(tree),
            "--commit",
            "0" * 40,
            "--suppressions",
            str(proposed),
            "--fail-on-unsuppressed",
        ]
    )
    assert code2 == 1
    out2 = capsys.readouterr().out
    assert "unsuppressed : 1" in out2
    assert "suppressed   : 1" in out2


def test_cli_rejects_a_bad_suppression_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "app.py").write_text("x = 1\n", encoding="utf-8")
    bad = _write_suppression_file(
        tmp_path, [{"fingerprint": "d", "triage": "true_positive", "reason": "no"}]
    )
    assert ss.main(["--root", str(tree), "--suppressions", str(bad)]) == 2
    assert "suppression file rejected" in capsys.readouterr().err
