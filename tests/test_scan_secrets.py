"""Tests for ``scripts/scan_secrets.py`` — the repo secret-scan gate.

Every secret-shaped value here is assembled at runtime via concatenation so
the test file's own source never trips the scanner that scans this repo. We
exercise the pure functions (diff parsing, line scanning, kind partitioning,
path allowlist) rather than spawning git, so the tests are hermetic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load scripts/scan_secrets.py by path (scripts/ is not a package). The module
# must be registered in sys.modules before exec so its @dataclass can resolve
# its own __module__ under ``from __future__ import annotations``.
_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "scan_secrets.py"
_spec = importlib.util.spec_from_file_location("scan_secrets", _MODULE_PATH)
assert _spec and _spec.loader
scan_secrets = importlib.util.module_from_spec(_spec)
sys.modules["scan_secrets"] = scan_secrets
_spec.loader.exec_module(scan_secrets)


# --- synthetic secrets (built so the literal in source is NOT a match) -------

# AWS access key id: "AKIA" + 16 uppercase/digits -> known_prefix.
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
# GitHub PAT: "ghp_" + 36 alnum -> known_prefix.
FAKE_GH = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
# A credential-shaped env assignment value -> high_entropy / known_prefix.
FAKE_OPENAI = "sk-" + "abcdef0123456789ABCDEFghijklmnop"


def _diff(path: str, *added: str) -> str:
    """Build a minimal unified diff that adds ``added`` lines to ``path``."""
    body = "".join(f"+{line}\n" for line in added)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added)} @@\n"
        f"{body}"
    )


# ---------------------------------------------------------------------------
# iter_added_lines
# ---------------------------------------------------------------------------


class TestIterAddedLines:
    def test_tracks_path_and_new_line_numbers(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,2 +1,3 @@\n"
            " context\n"
            "+added one\n"
            "+added two\n"
            "-removed\n"
        )
        rows = list(scan_secrets.iter_added_lines(diff))
        assert rows == [("foo.py", 2, "added one"), ("foo.py", 3, "added two")]

    def test_ignores_deleted_file_target(self):
        diff = (
            "diff --git a/gone.py b/gone.py\n"
            "--- a/gone.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-old\n"
        )
        assert list(scan_secrets.iter_added_lines(diff)) == []


# ---------------------------------------------------------------------------
# scan_diff_text — the CI gate path
# ---------------------------------------------------------------------------


class TestScanDiffText:
    def test_clean_diff_has_no_hits(self):
        diff = _diff("module.py", "def add(a, b):", "    return a + b")
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    def test_known_prefix_is_caught(self):
        diff = _diff("config.py", f'AWS = "{FAKE_AWS}"')
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        assert hits and hits[0].kind == "known_prefix"
        # The value must never appear verbatim in the printed excerpt.
        assert FAKE_AWS not in hits[0].excerpt

    def test_env_assignment_is_caught(self):
        diff = _diff("setup.sh", f"OPENAI_API_KEY={FAKE_OPENAI}")
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        assert any(h.kind in {"env_name", "known_prefix"} for h in hits)

    def test_pragma_suppresses_line(self):
        diff = _diff("config.py", f'AWS = "{FAKE_AWS}"  # pragma: allowlist secret')
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    def test_path_allowlist_skips_file(self):
        diff = _diff(".env.example", f"GITHUB_TOKEN={FAKE_GH}")
        # .env.example is in DEFAULT_ALLOW_GLOBS.
        hits = scan_secrets.scan_diff_text(
            diff, allow_globs=scan_secrets.DEFAULT_ALLOW_GLOBS
        )
        assert hits == []

    def test_multiline_pem_block_is_caught(self):
        # Markers built by concatenation so this test file's own source never
        # forms a contiguous PEM block (which would trip the repo gate on it).
        begin = "-----BEGIN " + "RSA PRIVATE KEY-----"
        end = "-----END " + "RSA PRIVATE KEY-----"
        diff = _diff(
            "id_rsa",
            begin,
            "MIIBOwIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Q",
            "uKUpRKfFLfRYC9AIKjbJTWit+CqvjSFmGEsAvw==",
            end,
        )
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        kinds = {h.kind for h in hits}
        assert "pem_block" in kinds
        blocking, _ = scan_secrets.partition(hits, strict=False)
        assert any(h.kind == "pem_block" for h in blocking)

    def test_multiline_pem_block_respects_pragma(self):
        begin = "-----BEGIN " + "RSA PRIVATE KEY-----  # pragma: allowlist secret"
        end = "-----END " + "RSA PRIVATE KEY-----"
        diff = _diff("id_rsa", begin, "MIIBOwIBAAJBAKj34GkxFhD90==", end)
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        assert not any(h.kind == "pem_block" for h in hits)


# ---------------------------------------------------------------------------
# GitHub Actions expression values — secret *references*, not secrets
# ---------------------------------------------------------------------------


class TestActionsExprSuppression:
    """Regression for PR #423's red secret-scan check.

    ``muse-desktop-release.yml`` passes signing secrets to steps as
    ``NAME: ${{ secrets.NAME }}``. The assigned value is a GitHub Actions
    *expression* — a reference resolved by the runner, never credential
    material — so the ``env_name`` detector must not flag it. A real value
    assigned to the same name must still flag.
    """

    # The four lines that falsely tripped the gate on PR #423 (verbatim,
    # including the two GH_TOKEN occurrences from separate jobs).
    PR_423_FALSE_POSITIVES = [
        "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
        "          APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}",
        "          APPLE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}",
        "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
    ]

    def test_pr_423_lines_do_not_flag(self):
        diff = _diff(
            ".github/workflows/muse-desktop-release.yml",
            *self.PR_423_FALSE_POSITIVES,
        )
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    @pytest.mark.parametrize("line", sorted(set(PR_423_FALSE_POSITIVES)))
    def test_each_pr_423_line_alone(self, line):
        diff = _diff(".github/workflows/muse-desktop-release.yml", line)
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    def test_shell_style_expression_assignment_does_not_flag(self):
        # `NAME=${{ ... }}` (the `=` form of the same detector) is equally
        # a reference.
        diff = _diff("workflow.yml", "GH_TOKEN=${{ secrets.GITHUB_TOKEN }}")
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    def test_real_value_on_same_name_still_flags(self):
        # Value assembled by concatenation so this file's source never
        # carries a credential-shaped assignment.
        line = "          APPLE_CERTIFICATE_PASSWORD: " + "hunter2" + "real"
        diff = _diff(".github/workflows/muse-desktop-release.yml", line)
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        assert any(h.kind == "env_name" for h in hits)
        blocking, _ = scan_secrets.partition(hits, strict=False)
        assert blocking

    def test_expression_plus_extra_material_still_flags(self):
        # Only a *pure* expression is a reference; an expression embedded in
        # a longer value could smuggle real material around the gate.
        line = "API_TOKEN: ${{ secrets.X }}" + "-hunter2" + "real"
        diff = _diff("workflow.yml", line)
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        assert any(h.kind == "env_name" for h in hits)

    def test_is_actions_expression_assignment_helper(self):
        good = "  GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}  "
        assert scan_secrets._is_actions_expression_assignment(good)
        assert not scan_secrets._is_actions_expression_assignment(
            "GH_TOKEN: " + "notanexpression"
        )
        assert not scan_secrets._is_actions_expression_assignment("just text")


class TestComposeInterpolationSuppression:
    """Regression for PR #629's red secret-scan check.

    ``integrations/n8n/docker-compose.yml`` passes credentials to containers
    as ``NAME: ${NAME}`` / ``NAME: ${NAME:-default}``. The assigned value is
    a compose/shell *interpolation* — a reference resolved from the runtime
    environment, never credential material — so the ``env_name`` detector
    must not flag it. A real value assigned to the same name must still flag.
    """

    PR_629_FALSE_POSITIVES = [
        "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}",
        "      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}",
        "      N8N_USER_MANAGEMENT_JWT_SECRET: ${N8N_USER_MANAGEMENT_JWT_SECRET}",
        "      MUSE_COCKPIT_TOKEN: ${MUSE_COCKPIT_TOKEN:-}",
    ]

    def test_pr_629_lines_do_not_flag(self):
        diff = _diff("integrations/n8n/docker-compose.yml", *self.PR_629_FALSE_POSITIVES)
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    @pytest.mark.parametrize("line", sorted(set(PR_629_FALSE_POSITIVES)))
    def test_each_pr_629_line_alone(self, line):
        diff = _diff("integrations/n8n/docker-compose.yml", line)
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    def test_shell_style_interpolation_assignment_does_not_flag(self):
        diff = _diff("compose.yml", "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}")
        assert scan_secrets.scan_diff_text(diff, allow_globs=()) == []

    def test_interpolation_plus_extra_material_still_flags(self):
        # Only a *pure* interpolation is a reference; an interpolation
        # embedded in a longer value could smuggle real material past the
        # gate.
        line = "API_TOKEN: ${SALT}" + "-hunter2" + "real"
        diff = _diff("compose.yml", line)
        hits = scan_secrets.scan_diff_text(diff, allow_globs=())
        assert any(h.kind == "env_name" for h in hits)
        blocking, _ = scan_secrets.partition(hits, strict=False)
        assert blocking

    def test_is_interpolation_assignment_helper(self):
        assert scan_secrets._is_interpolation_assignment(
            "  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  "
        )
        assert scan_secrets._is_interpolation_assignment(
            "MUSE_COCKPIT_TOKEN: ${MUSE_COCKPIT_TOKEN:-}"
        )
        assert not scan_secrets._is_interpolation_assignment(
            "POSTGRES_PASSWORD: " + "notaninterpolation"
        )
        assert not scan_secrets._is_interpolation_assignment("just text")


# ---------------------------------------------------------------------------
# partition — kind policy (blocking vs advisory)
# ---------------------------------------------------------------------------


class TestPartition:
    def _hit(self, kind: str) -> "scan_secrets.Hit":
        return scan_secrets.Hit(path="f", line=1, kind=kind, excerpt="x")

    def test_high_entropy_is_advisory_by_default(self):
        blocking, advisory = scan_secrets.partition(
            [self._hit("high_entropy")], strict=False
        )
        assert blocking == [] and len(advisory) == 1

    def test_high_entropy_blocks_under_strict(self):
        blocking, advisory = scan_secrets.partition(
            [self._hit("high_entropy")], strict=True
        )
        assert len(blocking) == 1 and advisory == []

    @pytest.mark.parametrize("kind", ["known_prefix", "pem_block", "env_name"])
    def test_high_confidence_kinds_always_block(self, kind):
        blocking, advisory = scan_secrets.partition([self._hit(kind)], strict=False)
        assert len(blocking) == 1 and advisory == []


# ---------------------------------------------------------------------------
# scan_tree — reads tracked files from disk
# ---------------------------------------------------------------------------


class TestScanTree:
    def test_skips_unreadable_and_allowlisted(self, tmp_path, monkeypatch):
        # Point the scanner's repo root at a tmp dir and stub git ls-files.
        (tmp_path / "clean.py").write_text("print('hello world')\n")
        (tmp_path / "leak.py").write_text(f'KEY = "{FAKE_AWS}"\n')
        (tmp_path / "skip.example").write_text(f'KEY = "{FAKE_AWS}"\n')

        monkeypatch.setattr(scan_secrets, "_REPO_ROOT", tmp_path)
        monkeypatch.setattr(
            scan_secrets,
            "_run_git",
            lambda args: "clean.py\nleak.py\nskip.example\n",
        )
        hits = scan_secrets.scan_tree(allow_globs=scan_secrets.DEFAULT_ALLOW_GLOBS)
        paths = {h.path for h in hits}
        assert "leak.py" in paths
        assert "clean.py" not in paths
        assert "skip.example" not in paths  # allowlisted by *.example


# ---------------------------------------------------------------------------
# main — exit codes
# ---------------------------------------------------------------------------


class TestMainExitCodes:
    def test_clean_diff_exits_zero(self, monkeypatch, capsys):
        diff = _diff("module.py", "x = 1")
        monkeypatch.setattr(scan_secrets, "_resolve_diff", lambda args: diff)
        assert scan_secrets.main(["--base", "origin/main"]) == 0

    def test_blocking_diff_exits_one(self, monkeypatch):
        diff = _diff("config.py", f'AWS = "{FAKE_AWS}"')
        monkeypatch.setattr(scan_secrets, "_resolve_diff", lambda args: diff)
        assert scan_secrets.main(["--base", "origin/main"]) == 1
