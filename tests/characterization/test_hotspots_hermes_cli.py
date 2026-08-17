"""Characterization tests for the §5.3 complexity hotspots — hermes_cli side.

Work Packet §5.3 lists the repository's branch-heaviest functions and prescribes
*characterization tests and seam extraction*, "explicitly **not** a broad
rewrite".  This file is the hermes_cli half of the characterization step for:

    hermes_cli/doctor.py::run_doctor                     (1,674 lines / 328 branch nodes)
    hermes_cli/main.py::_cmd_update_impl                 (1,243 / 183)
    hermes_cli/model_switch.py::list_authenticated_providers (693 / 174)
    hermes_cli/config.py::migrate_config                 (  601 / 167)

A characterization test records what the code **does**, not what it ought to
do.  Several pins below capture asymmetries that look like defects — they are
labelled ``CHARACTERIZED ODDITY`` and deliberately left alone.  Changing them is
a behaviour change and must be made deliberately, not silently during a
rewrite.  Four seams have been extracted from ``list_authenticated_providers``:
``_has_fast_aws_sdk_signal``, ``_has_aws_sdk_creds_for_listing``,
``_norm_url``, and ``_can_probe_custom_provider`` now live at module scope
and are still called by the hotspot.

The two cleanest seams are pinned hardest:

  * ``migrate_config`` is *config in → config out* (plus ``.env`` side effects),
    so its version ladder can be driven end to end from a written YAML file.
  * ``list_authenticated_providers`` is *credential/config state → provider
    rows*, so it can be driven with every network lookup stubbed out.

``run_doctor`` and ``_cmd_update_impl`` are pinned at their guard/dispatch
prologues only — the parts that decide *whether* to mutate anything.  See the
module-level ``COVERAGE_NOTES`` at the bottom for what these tests do not reach.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _config_path() -> Path:
    from hermes_cli.config import get_config_path

    return get_config_path()


def _write_raw_config(obj: dict) -> Path:
    """Write ``obj`` verbatim as the user's config.yaml (no defaults merged)."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(obj), encoding="utf-8")
    return path


def _read_raw_config() -> dict:
    return yaml.safe_load(_config_path().read_text(encoding="utf-8"))


def _latest_config_version() -> int:
    from hermes_cli.config import DEFAULT_CONFIG

    return int(DEFAULT_CONFIG["_config_version"])


def _migrate() -> dict:
    from hermes_cli.config import migrate_config

    return migrate_config(interactive=False, quiet=True)


# ===========================================================================
# hermes_cli/config.py :: migrate_config  (601 lines / 167 branch nodes)
#
# Shape: one flat sequence of ``if current_ver < N:`` blocks.  ``current_ver``
# is read ONCE at the top, so a single call runs every applicable block in
# ascending order and the blocks are not independent — an earlier block's write
# is visible to a later block's read.  That coupling is the source of most of
# the surprises pinned below.
# ===========================================================================

class TestMigrateConfigVersionLadder:

    def test_absent_config_reads_as_already_current(self):
        """A brand-new install is never treated as an old install.

        ``check_config_version()`` returns ``(latest, latest)`` when no
        config.yaml exists, so ``migrate_config`` skips every ``current_ver <
        N`` block rather than replaying the whole ladder against defaults.
        """
        from hermes_cli.config import check_config_version

        path = _config_path()
        if path.exists():
            path.unlink()

        latest = _latest_config_version()
        assert check_config_version() == (latest, latest)

    def test_version_is_bumped_to_latest_and_second_run_is_a_no_op(self):
        _write_raw_config({"_config_version": 3})

        first = _migrate()
        second = _migrate()

        from hermes_cli.config import check_config_version

        latest = _latest_config_version()
        assert check_config_version() == (latest, latest)
        assert _read_raw_config()["_config_version"] == latest
        # The first pass reports work; the second reports none.
        assert first["config_added"], "expected the v3 pass to report additions"
        assert second == {"env_added": [], "config_added": [], "warnings": []}

    def test_first_migration_step_expands_a_one_key_file_to_the_full_default_set(self):
        """CHARACTERIZED ODDITY — the v3→v4 block rewrites the whole file.

        That block calls ``save_config(load_config())``, and ``load_config()``
        deep-merges DEFAULT_CONFIG.  So migrating a config that contained a
        single key writes back every default section.  The user's config.yaml
        stops being a diff against the defaults and becomes a full copy of
        them, which is why later ``config set`` edits are made against a
        materialised file rather than an empty one.
        """
        _write_raw_config({"_config_version": 3})
        before = _read_raw_config()
        assert list(before) == ["_config_version"]

        _migrate()

        after = _read_raw_config()
        assert len(after) > 50, f"expected the full default set, got {len(after)} keys"
        for expected in ("agent", "display", "terminal", "stt", "curator", "plugins"):
            assert expected in after

    def test_an_older_config_reports_fewer_additions_than_a_newer_one(self):
        """CHARACTERIZED ODDITY — the ladder's steps are not independent.

        A v3 config reports FEWER ``config_added`` entries than a v14 config,
        which reads backwards.  Cause: the v3→v4 block above already wrote the
        entire default set, so the v14→v15 (``interim_assistant_messages``) and
        v22→v23 (``curator`` / ``auxiliary.curator``) blocks find their keys
        already present and stay silent.  A v14 config never passes through
        v3→v4, so those blocks do report.

        The end state is equivalent; only the *report* differs.  Anyone
        reordering these blocks during a refactor changes this output.
        """
        _write_raw_config({"_config_version": 3})
        from_v3 = _migrate()["config_added"]

        _write_raw_config({"_config_version": 14})
        from_v14 = _migrate()["config_added"]

        assert from_v3 == [
            "display.tool_progress=all (default)",
            "plugins.enabled (opt-in allow-list, 0 grandfathered)",
        ]
        assert "display.interim_assistant_messages=true (default)" in from_v14
        assert any(entry.startswith("curator (") for entry in from_v14)
        assert any(entry.startswith("auxiliary.curator (") for entry in from_v14)
        assert len(from_v3) < len(from_v14)


class TestMigrateConfigCustomProviders:
    """v11 → v12: the ``custom_providers`` list becomes the ``providers`` dict."""

    def test_list_is_converted_keyed_and_removed(self):
        _write_raw_config({
            "_config_version": 11,
            "custom_providers": [
                {"name": "My Endpoint (Local)", "base_url": "http://x/v1",
                 "api_key": "no-key", "model": "m1",
                 "api_mode": "chat_completions"},
                {"name": "", "url": "http://host.example/v1", "api_key": "sk-1"},
                {"name": "No URL"},
                "notadict",
            ],
        })

        _migrate()
        providers = _read_raw_config()["providers"]

        # Key generation: lowercase, spaces → "-", parentheses stripped.
        assert providers["my-endpoint-local"] == {
            "api": "http://x/v1",
            "name": "My Endpoint (Local)",
            "default_model": "m1",       # from ``model``
            "transport": "chat_completions",  # from ``api_mode``
        }
        # Empty name falls back to the URL hostname with dots → hyphens.
        assert providers["host-example"] == {
            "api": "http://host.example/v1",
            "api_key": "sk-1",
        }
        # An entry with no URL, and a non-dict entry, are both skipped.
        assert set(providers) == {"my-endpoint-local", "host-example"}
        # The old list is deleted, not left alongside the new dict.
        assert "custom_providers" not in _read_raw_config()

    def test_placeholder_api_keys_are_dropped_but_real_ones_are_kept(self):
        _write_raw_config({
            "_config_version": 11,
            "custom_providers": [
                {"name": "Placeholder", "base_url": "http://p/v1", "api_key": "no-key"},
                {"name": "Required", "base_url": "http://q/v1",
                 "api_key": "no-key-required"},
                {"name": "Real", "base_url": "http://r/v1", "api_key": "sk-real"},
            ],
        })

        _migrate()
        providers = _read_raw_config()["providers"]

        assert "api_key" not in providers["placeholder"]
        assert "api_key" not in providers["required"]
        assert providers["real"]["api_key"] == "sk-real"


class TestMigrateConfigStt:
    """v13 → v14: the flat ``stt.model`` key moves into a provider section."""

    def test_an_openai_model_name_under_provider_local_is_dropped_not_moved(self):
        """A recorded crash ("Invalid model size") is what this block exists for.

        ``whisper-1`` is not a faster-whisper size, so it is discarded rather
        than written into ``stt.local.model``; the local section keeps its
        default.
        """
        _write_raw_config({
            "_config_version": 13,
            "stt": {"provider": "local", "model": "whisper-1"},
        })

        _migrate()
        stt = _read_raw_config()["stt"]

        assert stt["local"]["model"] == "base"   # DEFAULT_CONFIG value, untouched
        assert "model" not in stt                # the flat key is always removed

    def test_a_real_local_model_name_is_moved_into_the_local_section(self):
        _write_raw_config({
            "_config_version": 13,
            "stt": {"provider": "local", "model": "large-v3"},
        })

        _migrate()
        stt = _read_raw_config()["stt"]

        assert stt["local"]["model"] == "large-v3"
        assert "model" not in stt

    def test_a_cloud_provider_gets_the_value_in_its_own_section(self):
        _write_raw_config({
            "_config_version": 13,
            "stt": {"provider": "mistral", "model": "zzz-custom"},
        })

        _migrate()
        stt = _read_raw_config()["stt"]

        assert stt["mistral"]["model"] == "zzz-custom"
        assert stt["provider"] == "mistral"
        assert "model" not in stt

    def test_an_existing_nested_model_wins_over_the_legacy_flat_key(self):
        _write_raw_config({
            "_config_version": 13,
            "stt": {"provider": "local", "model": "large-v3",
                    "local": {"model": "tiny"}},
        })

        _migrate()
        stt = _read_raw_config()["stt"]

        assert stt["local"]["model"] == "tiny"
        assert "model" not in stt


class TestMigrateConfigPluginsOptIn:
    """v20 → v21: plugins become opt-in; installed user plugins are grandfathered."""

    def test_installed_plugins_are_grandfathered_by_manifest_name(self):
        from hermes_constants import get_hermes_home

        plugins_dir = get_hermes_home() / "plugins"
        (plugins_dir / "alpha").mkdir(parents=True, exist_ok=True)
        (plugins_dir / "alpha" / "plugin.yaml").write_text(
            "name: alpha-plugin\n", encoding="utf-8")
        (plugins_dir / "beta").mkdir(parents=True, exist_ok=True)
        (plugins_dir / "beta" / "plugin.yml").write_text("{}\n", encoding="utf-8")
        (plugins_dir / "gamma").mkdir(parents=True, exist_ok=True)  # no manifest

        _write_raw_config({
            "_config_version": 20,
            "plugins": {"disabled": ["alpha-plugin"]},
        })

        result = _migrate()
        plugins = _read_raw_config()["plugins"]

        # ``alpha`` declares name ``alpha-plugin``, which is on the disabled
        # list, so it is NOT grandfathered — the match is on the manifest's
        # declared name, not on the directory name.
        # ``beta``'s manifest declares no name, so the directory name is used.
        # ``gamma`` has no manifest at all and is invisible to the scan.
        assert plugins["enabled"] == ["beta"]
        assert plugins["disabled"] == ["alpha-plugin"]
        assert "plugins.enabled (opt-in allow-list, 1 grandfathered)" in \
            result["config_added"]


class TestMigrateConfigEnvSideEffects:
    """The ladder also rewrites ``.env`` — those writes are blanks, not deletes."""

    def test_dead_env_vars_are_blanked_rather_than_removed(self):
        from hermes_cli.config import get_env_value, save_env_value

        save_env_value("ANTHROPIC_TOKEN", "tok")     # cleared by the v8→v9 block
        save_env_value("LLM_MODEL", "old-model")     # cleared by the v12→v13 block
        save_env_value("OPENAI_MODEL", "old-model-2")

        _write_raw_config({"_config_version": 8})
        _migrate()

        # CHARACTERIZED ODDITY: the key survives with an empty value, so the
        # variable is still *present* in .env after migration.
        assert get_env_value("ANTHROPIC_TOKEN") == ""
        assert get_env_value("LLM_MODEL") == ""
        assert get_env_value("OPENAI_MODEL") == ""


class TestMigrateConfigOpenRouterUnpin:
    """v23 → v24: a stale OpenRouter base_url under ``provider: auto`` is cleared."""

    def test_auto_provider_with_an_openrouter_url_is_unpinned(self):
        _write_raw_config({
            "_config_version": 23,
            # Mixed case on purpose — the match is case-insensitive.
            "model": {"provider": "auto", "base_url": "https://OpenRouter.ai/api/v1"},
        })

        result = _migrate()

        assert _read_raw_config()["model"]["base_url"] == ""
        assert "model.base_url cleared (stale OpenRouter URL under provider: auto)" \
            in result["config_added"]

    def test_an_explicit_openrouter_provider_keeps_its_url(self):
        _write_raw_config({
            "_config_version": 23,
            "model": {"provider": "openrouter",
                      "base_url": "https://openrouter.ai/api/v1"},
        })

        _migrate()

        assert _read_raw_config()["model"]["base_url"] == \
            "https://openrouter.ai/api/v1"


# ===========================================================================
# hermes_cli/model_switch.py :: list_authenticated_providers  (693 / 174)
#
# Shape: five append-only "sections" (built-in registry, models.dev overlay,
# canonical providers, user ``providers:`` dict, bare current endpoint, saved
# ``custom_providers:`` list) writing into one ``results`` list, followed by
# two post-passes (disabled filter, current-model injection) and a sort.
#
# Every test below stubs out network and credential discovery so only the
# user-config sections can emit rows.  That keeps the pins deterministic on a
# machine with real provider keys installed.
# ===========================================================================

@pytest.fixture()
def no_provider_discovery(monkeypatch):
    """Silence every credential source and every network lookup.

    Without this, the row list depends on which API keys the operator happens
    to have exported, and the assertions below would be machine-specific.
    """
    import agent.anthropic_adapter as anthropic_adapter
    import agent.models_dev as models_dev
    import hermes_cli.model_switch as model_switch
    import hermes_cli.models as models

    monkeypatch.setattr(models_dev, "fetch_models_dev", lambda *a, **k: {})
    monkeypatch.setattr(models, "cached_provider_model_ids", lambda *a, **k: [])
    monkeypatch.setattr(models, "cached_fetch_api_models", lambda *a, **k: [])
    monkeypatch.setattr(models, "get_curated_nous_model_ids", lambda *a, **k: [])
    monkeypatch.setattr(models, "fetch_ollama_cloud_models", lambda *a, **k: [])
    monkeypatch.setattr(model_switch, "_credential_pool_is_usable",
                        lambda *a, **k: False)
    monkeypatch.setattr(anthropic_adapter, "read_claude_code_credentials",
                        lambda *a, **k: None)
    monkeypatch.setattr(anthropic_adapter, "read_hermes_oauth_credentials",
                        lambda *a, **k: None)
    # The extracted AWS probe reads the process environment.  Silence it
    # here so a developer machine with AWS_PROFILE / keys set cannot inject
    # a Bedrock row into the exact-list pins below.
    for _aws_env in (
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
    ):
        monkeypatch.delenv(_aws_env, raising=False)


def _list_providers(**kwargs):
    from hermes_cli.model_switch import list_authenticated_providers

    return list_authenticated_providers(**kwargs)


@pytest.mark.usefixtures("no_provider_discovery")
class TestListAuthenticatedProvidersOrdering:

    def test_rows_sort_current_first_then_by_model_count_descending(self):
        rows = _list_providers(custom_providers=[
            {"name": "One", "base_url": "https://1.example/v1", "models": ["a"]},
            {"name": "Three", "base_url": "https://3.example/v1",
             "models": ["a", "b", "c"]},
            {"name": "Two", "base_url": "https://2.example/v1", "models": ["a", "b"]},
        ])

        assert [r["slug"] for r in rows] == [
            "custom:three", "custom:two", "custom:one"]
        assert [r["total_models"] for r in rows] == [3, 2, 1]

    def test_the_current_provider_is_hoisted_to_the_front(self):
        rows = _list_providers(
            custom_providers=[
                {"name": "One", "base_url": "https://1.example/v1", "models": ["a"]},
                {"name": "Three", "base_url": "https://3.example/v1",
                 "models": ["a", "b", "c"]},
            ],
            current_provider="custom:one",
        )

        assert rows[0]["slug"] == "custom:one"
        assert rows[0]["is_current"] is True
        assert rows[1]["slug"] == "custom:three"

    def test_an_uncurated_current_model_is_injected_at_the_front_of_its_row(self):
        rows = _list_providers(
            custom_providers=[
                {"name": "One", "base_url": "https://1.example/v1", "models": ["a"]},
            ],
            current_provider="custom:one",
            current_model="zzz",
        )

        assert rows[0]["models"] == ["zzz", "a"]
        assert rows[0]["total_models"] == 2


@pytest.mark.usefixtures("no_provider_discovery")
class TestListAuthenticatedProvidersDeduplication:

    def test_a_disabled_user_provider_is_hidden(self):
        rows = _list_providers(user_providers={
            "off-one": {"name": "Off", "api": "https://o.example/v1",
                        "default_model": "m", "enabled": False},
            "on-one": {"name": "On", "api": "https://n.example/v1",
                       "default_model": "m"},
        })

        assert [r["slug"] for r in rows] == ["on-one"]

    def test_a_user_providers_entry_hides_the_matching_custom_providers_entry(self):
        """Callers routinely pass both lists (the compatibility merge in
        ``get_compatible_custom_providers()``).  Matching on
        ``(display name, base url)`` is what keeps that from producing two
        identically-labelled picker rows."""
        rows = _list_providers(
            user_providers={"dupe": {"name": "Dupe", "api": "https://d.example/v1",
                                     "default_model": "m"}},
            custom_providers=[{"name": "Dupe", "base_url": "https://d.example/v1",
                               "model": "m"}],
        )

        assert len(rows) == 1
        assert rows[0]["slug"] == "dupe"
        assert rows[0]["source"] == "user-config"

    def test_same_endpoint_with_distinct_credentials_stays_two_rows(self):
        """Grouping is by endpoint + credential + wire protocol, so two proxies
        on one host with different ``key_env`` values must not collapse — that
        would let picker selection route through the wrong credential."""
        rows = _list_providers(custom_providers=[
            {"name": "Proxy — A", "base_url": "https://p.example/v1",
             "key_env": "K_A", "model": "ma"},
            {"name": "Proxy — B", "base_url": "https://p.example/v1",
             "key_env": "K_B", "model": "mb"},
        ])

        # The per-model suffix after " — " is stripped from the display name,
        # and the second row's slug collision is resolved with a "-2" suffix.
        assert [r["slug"] for r in rows] == ["custom:proxy", "custom:proxy-2"]
        assert [r["name"] for r in rows] == ["Proxy", "Proxy"]
        assert [r["models"] for r in rows] == [["ma"], ["mb"]]


@pytest.mark.usefixtures("no_provider_discovery")
class TestListAuthenticatedProvidersBareEndpoint:

    def test_a_bare_model_config_endpoint_is_surfaced_as_its_own_row(self):
        """``model.provider: custom`` + ``model.base_url:`` has no named row to
        render, so section 3b synthesises one — otherwise ``/model`` looks like
        it ignored config.yaml."""
        rows = _list_providers(
            current_provider="custom",
            current_base_url="https://bare.example/v1/",
            current_model="m1",
        )

        assert len(rows) == 1
        assert rows[0]["slug"] == "custom"
        assert rows[0]["name"] == "Custom endpoint"
        assert rows[0]["source"] == "model-config"
        assert rows[0]["is_current"] is True
        assert rows[0]["models"] == ["m1"]
        # The trailing slash is stripped from the reported api_url.
        assert rows[0]["api_url"] == "https://bare.example/v1"

    def test_a_named_custom_provider_on_the_same_url_suppresses_the_bare_row(self):
        rows = _list_providers(
            current_provider="custom",
            current_base_url="https://bare.example/v1/",
            current_model="m1",
            custom_providers=[{"name": "Bare", "base_url": "https://bare.example/v1",
                               "model": "m1"}],
        )

        assert [r["slug"] for r in rows] == ["custom:bare"]


@pytest.mark.usefixtures("no_provider_discovery")
class TestListAuthenticatedProvidersKnownAsymmetries:
    """Two parameters that do not apply uniformly across the sections."""

    def test_max_models_does_not_cap_saved_custom_provider_rows(self):
        """CHARACTERIZED ODDITY — ``max_models`` is applied by sections 1, 2,
        2b and 3b but NOT by section 4.

        Section 4 emits ``grp["models"]`` unsliced (model_switch.py:3231), so a
        caller asking for two models can still be handed the full list for a
        saved custom provider.  The docstring's "models: list[str] — curated
        model IDs (up to max_models)" is therefore true of built-in rows only.
        """
        rows = _list_providers(
            custom_providers=[
                {"name": "Big", "base_url": "https://b.example/v1",
                 "models": ["a", "b", "c", "d"]},
            ],
            max_models=2,
        )

        assert rows[0]["models"] == ["a", "b", "c", "d"]
        assert rows[0]["total_models"] == 4

    def test_max_models_does_cap_the_bare_endpoint_row(self):
        """The same call *is* honoured on the section-3b row, which is what
        makes the previous test an asymmetry rather than a blanket no-op."""
        rows = _list_providers(
            current_provider="custom",
            current_base_url="https://bare.example/v1",
            current_model="",          # no injection — see the next test
            max_models=0,
        )

        assert rows[0]["models"] == []
        assert rows[0]["total_models"] == 0

    def test_the_current_model_injection_overrides_the_cap_and_desyncs_the_count(self):
        """CHARACTERIZED ODDITY — two post-passes disagree about the same row.

        Section 3b slices the model list to ``max_models`` *and* records
        ``total_models = len(models_before_slicing)``.  The current-model
        injection post-pass then re-adds the model the cap removed and does
        ``total_models += 1``.  The row ends up reporting a total of 2 while
        carrying exactly one model — the count is neither the pre-cap total
        nor the post-cap length.

        Injection winning is arguably right (a picker that cannot show the
        model you are currently using is broken).  The count is not.  Pinned
        as-is so a refactor has to decide deliberately.
        """
        rows = _list_providers(
            current_provider="custom",
            current_base_url="https://bare.example/v1",
            current_model="only",
            max_models=0,
        )

        assert rows[0]["models"] == ["only"]
        assert rows[0]["total_models"] == 2
        assert len(rows[0]["models"]) != rows[0]["total_models"]

    def test_excluded_providers_does_not_hide_user_defined_rows(self):
        """CHARACTERIZED ODDITY — the exclusion set is consulted only by the
        built-in sections (1, 2, 2b).

        ``_excluded`` is built at model_switch.py:2144 and compared against
        hermes/models.dev/canonical ids.  Sections 3, 3b and 4 never read it,
        so a caller cannot hide a user-defined endpoint this way even when it
        passes that row's exact slug.
        """
        rows = _list_providers(
            custom_providers=[
                {"name": "Alpha", "base_url": "https://a.example/v1", "model": "x"},
            ],
            excluded_providers=["custom:alpha"],
        )

        assert [r["slug"] for r in rows] == ["custom:alpha"]


# ===========================================================================
# hermes_cli/model_switch.py :: _has_fast_aws_sdk_signal
#
# Seam extracted from list_authenticated_providers.  Pins the relationships
# the plan names (bearer only / access-key pair only / neither) plus the
# two cases the original nested helper treated as *not* a signal: a lone
# access key, and whitespace-only values.
# ===========================================================================

_AWS_SIGNAL_ENV = (
    "AWS_BEARER_TOKEN_BEDROCK",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_PROFILE",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
)


class TestHasFastAwsSdkSignal:
    """Provider-auth probe lifted out of ``list_authenticated_providers``."""

    @pytest.fixture(autouse=True)
    def _clear_aws_env(self, monkeypatch):
        for name in _AWS_SIGNAL_ENV:
            monkeypatch.delenv(name, raising=False)

    def test_neither_signal_is_unauthenticated(self):
        from hermes_cli.model_switch import _has_fast_aws_sdk_signal

        assert _has_fast_aws_sdk_signal() is False

    def test_bearer_token_only_is_authenticated(self, monkeypatch):
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "tok")
        from hermes_cli.model_switch import _has_fast_aws_sdk_signal

        assert _has_fast_aws_sdk_signal() is True

    def test_access_key_pair_only_is_authenticated(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKI")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
        from hermes_cli.model_switch import _has_fast_aws_sdk_signal

        assert _has_fast_aws_sdk_signal() is True

    def test_access_key_without_secret_is_not_a_signal(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKI")
        from hermes_cli.model_switch import _has_fast_aws_sdk_signal

        assert _has_fast_aws_sdk_signal() is False

    def test_whitespace_only_values_are_not_signals(self, monkeypatch):
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "   ")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "  ")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "  ")
        monkeypatch.setenv("AWS_PROFILE", "\t")
        from hermes_cli.model_switch import _has_fast_aws_sdk_signal

        assert _has_fast_aws_sdk_signal() is False

    def test_profile_only_is_authenticated(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "default")
        from hermes_cli.model_switch import _has_fast_aws_sdk_signal

        assert _has_fast_aws_sdk_signal() is True

    @pytest.mark.usefixtures("no_provider_discovery")
    def test_the_hotspot_still_consults_the_extracted_probe(self, monkeypatch):
        """``list_authenticated_providers`` must keep calling the helper.

        The Bedrock overlay in section 2 is the only caller; if a later
        rewrite inlines the probe or drops the call, this pin fails even
        when custom-provider rows still look right.
        """
        import hermes_cli.model_switch as model_switch

        calls = {"n": 0}

        def _probe() -> bool:
            calls["n"] += 1
            return False

        monkeypatch.setattr(model_switch, "_has_fast_aws_sdk_signal", _probe)
        rows = _list_providers(custom_providers=[
            {"name": "One", "base_url": "https://1.example/v1", "models": ["a"]},
        ])

        assert calls["n"] >= 1
        assert [r["slug"] for r in rows] == ["custom:one"]


class TestHasAwsSdkCredsForListing:
    """Listing gate lifted out of ``list_authenticated_providers``."""

    @pytest.fixture(autouse=True)
    def _clear_aws_env(self, monkeypatch):
        for name in _AWS_SIGNAL_ENV:
            monkeypatch.delenv(name, raising=False)

    def test_fast_signal_authenticates_any_slug(self, monkeypatch):
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "tok")
        from hermes_cli.model_switch import _has_aws_sdk_creds_for_listing

        assert _has_aws_sdk_creds_for_listing("bedrock", current_provider="openai") is True

    def test_other_slug_without_signal_is_not_authenticated(self):
        from hermes_cli.model_switch import _has_aws_sdk_creds_for_listing

        assert _has_aws_sdk_creds_for_listing("bedrock", current_provider="openai") is False

    def test_current_slug_delegates_to_has_aws_credentials(self, monkeypatch):
        import hermes_cli.model_switch as model_switch

        calls = {"n": 0}

        def _fake():
            calls["n"] += 1
            return True

        monkeypatch.setitem(
            __import__("sys").modules,
            "agent.bedrock_adapter",
            type(sys)("agent.bedrock_adapter"),
        )
        sys.modules["agent.bedrock_adapter"].has_aws_credentials = _fake
        assert model_switch._has_aws_sdk_creds_for_listing("bedrock", current_provider="bedrock") is True
        assert calls["n"] == 1

    def test_botocore_walk_failure_is_unauthenticated(self, monkeypatch):
        from hermes_cli.model_switch import _has_aws_sdk_creds_for_listing

        class _Boom:
            def has_aws_credentials(self):
                raise RuntimeError("no chain")

        monkeypatch.setitem(sys.modules, "agent.bedrock_adapter", _Boom())
        assert _has_aws_sdk_creds_for_listing("bedrock", current_provider="bedrock") is False

    @pytest.mark.usefixtures("no_provider_discovery")
    def test_the_hotspot_still_consults_the_extracted_listing_gate(self, monkeypatch):
        import hermes_cli.model_switch as model_switch

        calls = {"n": 0}

        def _gate(slug, current_provider=None):
            calls["n"] += 1
            return False

        monkeypatch.setattr(model_switch, "_has_aws_sdk_creds_for_listing", _gate)
        rows = _list_providers(
            custom_providers=[
                {"name": "One", "base_url": "https://1.example/v1", "models": ["a"]},
            ]
        )
        assert calls["n"] >= 1
        assert [r["slug"] for r in rows] == ["custom:one"]


class TestNormUrl:
    """Endpoint-dedup helper lifted out of ``list_authenticated_providers``."""

    def test_none_and_empty_become_empty(self):
        from hermes_cli.model_switch import _norm_url

        assert _norm_url(None) == ""
        assert _norm_url("") == ""
        assert _norm_url("   ") == ""

    def test_trailing_slash_and_case_are_folded(self):
        from hermes_cli.model_switch import _norm_url

        assert _norm_url("https://API.Example.com/V1/") == "https://api.example.com/v1"

    def test_already_canonical_is_unchanged(self):
        from hermes_cli.model_switch import _norm_url

        assert _norm_url("https://api.example.com/v1") == "https://api.example.com/v1"

    def test_the_hotspot_still_consults_the_extracted_normalizer(self):
        """``_record_builtin_endpoint`` must keep calling the helper.

        Custom-only listing never records a built-in endpoint, so this pin
        is the code object, not a row list.
        """
        import hermes_cli.model_switch as model_switch

        recorders = [
            c
            for c in model_switch.list_authenticated_providers.__code__.co_consts
            if hasattr(c, "co_name") and c.co_name == "_record_builtin_endpoint"
        ]
        assert recorders, "nested _record_builtin_endpoint missing"
        assert "_norm_url" in recorders[0].co_names
        assert hasattr(model_switch, "_norm_url")


class TestCanProbeCustomProvider:
    """Probe gate lifted out of ``list_authenticated_providers``."""

    def test_global_probe_wins_even_when_row_is_not_current(self):
        from hermes_cli.model_switch import _can_probe_custom_provider

        assert _can_probe_custom_provider(
            row_is_current=False,
            probe_custom_providers=True,
            probe_current_custom_provider=False,
        ) is True

    def test_current_row_only_when_global_probe_is_off(self):
        from hermes_cli.model_switch import _can_probe_custom_provider

        assert _can_probe_custom_provider(
            row_is_current=True,
            probe_custom_providers=False,
            probe_current_custom_provider=True,
        ) is True
        assert _can_probe_custom_provider(
            row_is_current=False,
            probe_custom_providers=False,
            probe_current_custom_provider=True,
        ) is False

    def test_both_flags_off_never_probes(self):
        from hermes_cli.model_switch import _can_probe_custom_provider

        assert _can_probe_custom_provider(
            row_is_current=True,
            probe_custom_providers=False,
            probe_current_custom_provider=False,
        ) is False

    def test_the_hotspot_still_consults_the_extracted_probe_gate(self):
        import hermes_cli.model_switch as model_switch

        assert "_can_probe_custom_provider" in model_switch.list_authenticated_providers.__code__.co_names
        assert hasattr(model_switch, "_can_probe_custom_provider")


# ===========================================================================
# hermes_cli/doctor.py :: run_doctor  (1,674 lines / 328 branch nodes)
#
# Only the prologue is pinned: the environment stamp and the ``--ack`` fast
# path, which returns before any diagnostic runs.
# ===========================================================================

class TestRunDoctorAckFastPath:

    @staticmethod
    def _real_advisory_id() -> str:
        from hermes_cli.security_advisories import ADVISORIES

        return ADVISORIES[0].id

    def test_an_unknown_advisory_id_exits_2_and_lists_the_known_ids(self, capsys):
        from hermes_cli import doctor

        with pytest.raises(SystemExit) as exc:
            doctor.run_doctor(SimpleNamespace(ack="not-a-real-advisory"))

        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "Unknown advisory ID: 'not-a-real-advisory'" in out
        assert self._real_advisory_id() in out

    def test_the_ack_path_returns_before_any_diagnostic_runs(self, monkeypatch, capsys):
        """The fast path must not pay for the full doctor sweep.

        Proven by making the first diagnostic section explode: if the ack path
        ever fell through to it, this test would raise instead of returning.
        """
        import hermes_cli.security_advisories as advisories

        def _boom(*_a, **_k):
            raise AssertionError("run_doctor ran diagnostics on the --ack fast path")

        monkeypatch.setattr(advisories, "detect_compromised", _boom)

        from hermes_cli import doctor

        real_id = self._real_advisory_id()
        assert doctor.run_doctor(SimpleNamespace(ack=real_id)) is None

        assert real_id in advisories.get_acked_ids()
        assert f"Acknowledged advisory {real_id}" in capsys.readouterr().out

    def test_a_failed_persist_exits_1_rather_than_reporting_success(self, monkeypatch,
                                                                    capsys):
        import hermes_cli.security_advisories as advisories

        monkeypatch.setattr(advisories, "ack_advisory", lambda _id: False)

        from hermes_cli import doctor

        real_id = self._real_advisory_id()
        with pytest.raises(SystemExit) as exc:
            doctor.run_doctor(SimpleNamespace(ack=real_id))

        assert exc.value.code == 1
        assert "Failed to persist ack" in capsys.readouterr().out

    def test_hermes_interactive_is_stamped_but_never_overwritten(self, monkeypatch):
        """``run_doctor`` uses ``setdefault``, so doctor-under-a-gateway keeps
        whatever the caller already declared."""
        from hermes_cli import doctor

        monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)
        with pytest.raises(SystemExit):
            doctor.run_doctor(SimpleNamespace(ack="nope"))
        assert os.environ["HERMES_INTERACTIVE"] == "1"

        monkeypatch.setenv("HERMES_INTERACTIVE", "0")
        with pytest.raises(SystemExit):
            doctor.run_doctor(SimpleNamespace(ack="nope"))
        assert os.environ["HERMES_INTERACTIVE"] == "0"


# ===========================================================================
# hermes_cli/main.py :: _cmd_update_impl  (1,243 lines / 183 branch nodes)
#
# Only the prologue is pinned: the Windows concurrency guard and the
# install-method dispatch.  Those are the branches that decide whether the
# process is allowed to mutate the install at all.
#
# NOTE: tests/hermes_cli/conftest.py installs an autouse stub that neutralises
# ``_detect_concurrent_hermes_instances``.  It is scoped to that directory, so
# every test here patches the detector explicitly.
# ===========================================================================

@pytest.fixture()
def update_env(monkeypatch, tmp_path):
    """Neutralise everything ``_cmd_update_impl`` could mutate.

    Returns a recorder list so ordering between the guard, the backup and the
    chosen update route can be asserted.
    """
    from hermes_cli import main as cli_main

    calls: list[str] = []

    monkeypatch.setattr(cli_main, "_venv_scripts_dir", lambda: tmp_path / "Scripts")
    monkeypatch.setattr(cli_main, "_run_pre_update_backup",
                        lambda _args: calls.append("backup"))
    monkeypatch.setattr(cli_main, "_update_via_zip", lambda _args: calls.append("zip"))
    monkeypatch.setattr(cli_main, "_cmd_update_pip", lambda _args: calls.append("pip"))
    # PROJECT_ROOT without a .git directory — keeps every test off the real repo.
    no_repo = tmp_path / "norepo"
    no_repo.mkdir()
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", no_repo)
    return SimpleNamespace(main=cli_main, calls=calls, monkeypatch=monkeypatch,
                           tmp_path=tmp_path)


class TestCmdUpdateImplConcurrencyGuard:

    def test_a_running_instance_on_windows_aborts_before_any_mutation(
            self, update_env, capsys):
        """Ordering is the invariant, not just the exit code.

        The guard sits above ``_run_pre_update_backup``, so an aborted update
        leaves no backup behind and touches nothing.
        """
        main = update_env.main
        update_env.monkeypatch.setattr(main, "_is_windows", lambda: True)
        update_env.monkeypatch.setattr(
            main, "_detect_concurrent_hermes_instances",
            lambda _d: [(4321, "muse.exe")])

        with pytest.raises(SystemExit) as exc:
            main._cmd_update_impl(SimpleNamespace(yes=True, force=False),
                                  gateway_mode=False)

        assert exc.value.code == 2
        assert update_env.calls == []          # no backup, no zip, no pip
        out = capsys.readouterr().out
        assert "Another MUSE process is running" in out
        assert "PID 4321  muse.exe" in out
        assert "muse update --force" in out

    def test_force_skips_the_detection_entirely(self, update_env, capsys):
        """``--force`` does not merely ignore the result — the detector is
        never called, so a slow process scan is skipped as well."""
        main = update_env.main
        update_env.monkeypatch.setattr(main, "_is_windows", lambda: True)
        update_env.monkeypatch.setattr(
            main, "_detect_concurrent_hermes_instances",
            lambda _d: update_env.calls.append("detect") or [(1, "muse.exe")])
        update_env.monkeypatch.setattr(sys, "platform", "win32")

        main._cmd_update_impl(SimpleNamespace(yes=True, force=True),
                              gateway_mode=False)
        capsys.readouterr()

        assert "detect" not in update_env.calls
        assert update_env.calls == ["backup", "zip"]

    def test_the_guard_is_windows_only(self, update_env, capsys):
        main = update_env.main
        update_env.monkeypatch.setattr(main, "_is_windows", lambda: False)
        update_env.monkeypatch.setattr(
            main, "_detect_concurrent_hermes_instances",
            lambda _d: update_env.calls.append("detect") or [(1, "hermes")])
        update_env.monkeypatch.setattr(sys, "platform", "linux")

        import hermes_cli.config as config

        update_env.monkeypatch.setattr(config, "detect_install_method",
                                       lambda _root: "pip")

        main._cmd_update_impl(SimpleNamespace(yes=True, force=False),
                              gateway_mode=False)
        capsys.readouterr()

        assert "detect" not in update_env.calls


class TestCmdUpdateImplInstallMethodDispatch:
    """With no ``.git`` present, the route depends on platform + install method."""

    def test_windows_without_a_git_dir_falls_back_to_the_zip_route(
            self, update_env, capsys):
        main = update_env.main
        update_env.monkeypatch.setattr(main, "_is_windows", lambda: True)
        update_env.monkeypatch.setattr(
            main, "_detect_concurrent_hermes_instances", lambda _d: [])
        update_env.monkeypatch.setattr(sys, "platform", "win32")

        main._cmd_update_impl(SimpleNamespace(yes=True, force=False),
                              gateway_mode=False)
        capsys.readouterr()

        assert update_env.calls == ["backup", "zip"]

    def test_a_pip_install_is_handed_to_the_pip_updater_and_returns(
            self, update_env, capsys):
        main = update_env.main
        update_env.monkeypatch.setattr(main, "_is_windows", lambda: False)
        update_env.monkeypatch.setattr(sys, "platform", "linux")

        import hermes_cli.config as config

        update_env.monkeypatch.setattr(config, "detect_install_method",
                                       lambda _root: "pip")

        assert main._cmd_update_impl(SimpleNamespace(yes=True, force=False),
                                     gateway_mode=False) is None
        capsys.readouterr()

        # Backup first, then the pip route — and nothing after it.
        assert update_env.calls == ["backup", "pip"]

    def test_a_non_git_non_pip_install_exits_1_with_reinstall_instructions(
            self, update_env, capsys):
        main = update_env.main
        update_env.monkeypatch.setattr(main, "_is_windows", lambda: False)
        update_env.monkeypatch.setattr(sys, "platform", "linux")

        import hermes_cli.config as config

        update_env.monkeypatch.setattr(config, "detect_install_method",
                                       lambda _root: "git")

        with pytest.raises(SystemExit) as exc:
            main._cmd_update_impl(SimpleNamespace(yes=True, force=False),
                                  gateway_mode=False)

        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "Not a git repository. Please reinstall:" in out
        assert "scripts/install.sh" in out
        # CHARACTERIZED ODDITY: the pre-update backup already ran before the
        # install method was even inspected, so an install that cannot be
        # updated still pays for (and leaves behind) a backup.
        assert update_env.calls == ["backup"]


# ---------------------------------------------------------------------------
# COVERAGE_NOTES — what these tests deliberately do NOT reach.
#
# Stated explicitly because §29.2 forbids presenting partial work as complete.
#
#   hermes_cli/config.py::migrate_config (167 branch nodes)
#       Covered: the version gate and idempotency, the cross-block coupling
#       introduced by the v3→v4 full-file write, and the v11→v12, v13→v14,
#       v20→v21, v23→v24 blocks plus the v8→v9 / v12→v13 .env writes.
#       NOT covered: every ``interactive=True`` branch (the required-env
#       prompt loop, the "new optional keys" prompt, and the skill-declared
#       config prompt) — those call ``input()`` / ``getpass()`` directly with
#       no injection seam, so exercising them means patching builtins rather
#       than characterizing a seam.  Also not covered: the v4→v5 timezone
#       block, the v14→v15/v15→v16/v16→v17 display and compression blocks
#       beyond their presence in the report list, and ``sanitize_env_file``'s
#       repair counting.
#
#   hermes_cli/model_switch.py::list_authenticated_providers (174 branch nodes)
#       Covered: sections 3 (user ``providers:``), 3b (bare current endpoint)
#       and 4 (``custom_providers:``), the grouping/dedup rules between them,
#       the disabled-provider post-filter, the current-model injection
#       post-pass, the final sort, and the two parameter asymmetries above.
#       The extracted ``_has_fast_aws_sdk_signal`` probe is pinned directly
#       (bearer only / access-key pair only / neither / half-pair /
#       whitespace) and the hotspot is asserted to still call it.
#       NOT covered: sections 1, 2 and 2b (built-in PROVIDER_REGISTRY,
#       models.dev overlay, canonical providers).  Those emit rows only when
#       real credentials are present, and the fixture above deliberately
#       removes every credential source so the pins stay machine-independent.
#       Consequently ``excluded_providers``, ``force_fresh_nous_tier``,
#       ``refresh`` and the aws_sdk/bedrock *row-emission* branch are
#       exercised only in the negative.  Live ``/models`` probing
#       (``cached_fetch_api_models``) is stubbed to empty throughout, so the
#       ``discover_models`` / ``has_explicit_models`` probe-gate ladder and
#       ``_save_discovered_models_to_config`` write-back are untested.
#
#   hermes_cli/doctor.py::run_doctor (328 branch nodes)
#       Covered: the HERMES_INTERACTIVE stamp and all three outcomes of the
#       ``--ack`` fast path.  NOT covered: any of the ~20 diagnostic sections
#       that follow it, the ``--fix`` auto-repair branches, or the issue/
#       manual-issue accounting and exit status.  ``run_doctor`` inspects the
#       live machine (installed packages, PATH, cron, sqlite build, provider
#       reachability); pinning those would pin this laptop, not the function.
#
#   hermes_cli/main.py::_cmd_update_impl (183 branch nodes)
#       Covered: the Windows concurrent-instance guard including its ordering
#       against the pre-update backup, ``--force``, and the four-way
#       no-.git dispatch (zip / pip / reinstall).  NOT covered: everything
#       past ``git fetch`` — fork detection, branch consolidation, the stash
#       ladder, conflict handling, the post-pull dependency install and the
#       restart prompt.  Those shell out to git against a real working tree;
#       reaching them from a test means building a fixture repository, which
#       is a larger piece of work than this task and is recorded as such
#       rather than faked.
# ---------------------------------------------------------------------------
