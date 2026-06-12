"""Regression tests for packaging metadata in pyproject.toml."""

from pathlib import Path
import tomllib


def _load_optional_dependencies():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return project["optional-dependencies"]


def _load_package_data():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        tool = tomllib.load(handle)["tool"]
    return tool["setuptools"]["package-data"]


def test_matrix_extra_not_in_all():
    """The [matrix] extra pulls `mautrix[encryption]` -> `python-olm`,
    which has Linux-only wheels and no native build path on Windows or
    modern macOS (archived libolm, C++ errors with Clang 21+).

    With matrix in [all], `uv sync --locked` on Windows tried to build
    python-olm from sdist and failed on `make`. As of 2026-05-12 the
    [matrix] extra is excluded from [all] entirely and routed through
    `tools/lazy_deps.py` (LAZY_DEPS["platform.matrix"]) — installs at
    first use, where the user is expected to have a toolchain.
    """
    optional_dependencies = _load_optional_dependencies()

    assert "matrix" in optional_dependencies, "[matrix] extra must still exist for explicit `pip install hermes-agent[matrix]`"
    # Must NOT appear in [all] in any form — neither unconditional nor
    # platform-gated. Lazy-install handles it.
    matrix_in_all = [
        dep for dep in optional_dependencies["all"]
        if "matrix" in dep
    ]
    assert not matrix_in_all, (
        "matrix must not appear in [all] — it's lazy-installed via "
        "tools/lazy_deps.py LAZY_DEPS['platform.matrix']. Found: "
        f"{matrix_in_all}"
    )


def test_dev_extra_not_in_all():
    """The [dev] extra is development/test tooling (pytest, debugpy, ruff,
    ty, pytest-*), not a runtime feature or a packager-shipped skill dep —
    it never belonged in an end-user [all].

    Concretely, `ruff` and `ty` are Rust tools with no Termux/Android
    wheels, so `.[all]` on a phone built them from source. `ty`'s sdist
    bundles the entire ruff monorepo (thousands of parser snapshots) and
    exhausted device storage ("No space left on device", os error 28).

    As of 2026-06-09 [dev] is excluded from [all]. Developers install
    `.[all,dev]` (the documented + CI path: tests.yml installs `.[all,dev]`).
    This test locks the contract so dev tooling can't silently re-enter [all].
    """
    optional_dependencies = _load_optional_dependencies()

    # [dev] must still exist for explicit `.[all,dev]` / `pip install .[dev]`.
    assert "dev" in optional_dependencies, "[dev] extra must still exist for `.[all,dev]`"

    all_extra_specs = optional_dependencies["all"]

    # No `hermes-agent[dev]` self-reference in [all], in any form.
    dev_in_all = [spec for spec in all_extra_specs if "hermes-agent[dev]" in spec]
    assert not dev_in_all, (
        "[dev] must not appear in [all] — it's dev/test tooling, install via "
        f"`.[all,dev]`. Found in [all]: {dev_in_all}"
    )

    # And specifically none of the Rust dev tools that have no Android wheels
    # should be reachable directly from [all].
    rust_tools_in_all = [
        spec for spec in all_extra_specs
        if spec.startswith(("ruff", "ty"))
    ]
    assert not rust_tools_in_all, (
        "ruff/ty must not appear in [all] — they build from sdist on Termux "
        f"and exhaust device storage. Found in [all]: {rust_tools_in_all}"
    )


def test_lazy_installable_extras_excluded_from_all():
    """Policy (2026-05-12): every extra that has a `LAZY_DEPS` entry
    in `tools/lazy_deps.py` must be excluded from [all].

    The lazy-install system exists so one quarantined PyPI release
    (e.g. mistralai 2.4.6) can't break every fresh install. Putting a
    backend in BOTH [all] and LAZY_DEPS defeats that — fresh installs
    eager-install it and inherit whatever's broken upstream.

    If you're tempted to add an opt-in backend to [all] for "convenience,"
    add it to `LAZY_DEPS` instead so it installs at first use.
    """
    optional_dependencies = _load_optional_dependencies()

    # Hard-coded mirror of the extras that are in LAZY_DEPS as of
    # 2026-05-12. This list intentionally duplicates rather than
    # imports tools/lazy_deps.py so the test stays a contract — if
    # someone adds a new lazy-install backend, they have to update
    # this list AND verify [all] doesn't contain it.
    lazy_covered_extras = {
        "anthropic", "bedrock",
        "exa", "firecrawl", "parallel-web",
        "fal",
        "edge-tts", "tts-premium",
        "voice",  # faster-whisper / sounddevice / numpy
        "modal", "daytona", "vercel",
        "messaging", "slack", "matrix", "dingtalk", "feishu",
        "honcho", "hindsight",
    }
    all_extra_specs = optional_dependencies["all"]
    for extra in lazy_covered_extras:
        offending = [
            spec for spec in all_extra_specs
            if f"hermes-agent[{extra}]" in spec
        ]
        assert not offending, (
            f"[{extra}] is in [all] but also in LAZY_DEPS. "
            f"Remove it from [all] in pyproject.toml — it lazy-installs "
            f"at first use. Found in [all]: {offending}"
        )


def test_dev_extra_restores_psutil_off_android():
    """Desktop/server dev installs need psutil for CI and process tests.

    Base dependencies keep psutil out so Termux/Android installs can use
    the compatibility shim, but `.[all,dev]` is the non-Android CI profile.
    """
    optional_dependencies = _load_optional_dependencies()

    dev_extra = optional_dependencies["dev"]
    psutil_specs = [dep for dep in dev_extra if dep.startswith("psutil")]

    assert psutil_specs == ['psutil==7.2.2; sys_platform != "android"']


def test_messaging_extra_includes_qrcode_for_weixin_setup():
    optional_dependencies = _load_optional_dependencies()

    messaging_extra = optional_dependencies["messaging"]
    assert any(dep.startswith("qrcode") for dep in messaging_extra)


def test_dingtalk_extra_includes_qrcode_for_qr_auth():
    """DingTalk's QR-code device-flow auth (muse_cli/dingtalk_auth.py)
    needs the qrcode package."""
    optional_dependencies = _load_optional_dependencies()

    dingtalk_extra = optional_dependencies["dingtalk"]
    assert any(dep.startswith("qrcode") for dep in dingtalk_extra)


def test_feishu_extra_includes_qrcode_for_qr_login():
    """Feishu's QR login flow (gateway/platforms/feishu.py) needs the
    qrcode package."""
    optional_dependencies = _load_optional_dependencies()

    feishu_extra = optional_dependencies["feishu"]
    assert any(dep.startswith("qrcode") for dep in feishu_extra)


def test_dashboard_plugin_manifests_and_assets_are_packaged():
    """Bundled dashboard plugins need their manifests and built assets in
    wheel installs so /api/dashboard/plugins can discover them outside a
    source checkout."""
    package_data = _load_package_data()
    plugin_data = package_data["plugins"]

    assert "*/dashboard/manifest.json" in plugin_data
    assert "*/dashboard/dist/*" in plugin_data
    assert "*/dashboard/dist/**/*" in plugin_data
