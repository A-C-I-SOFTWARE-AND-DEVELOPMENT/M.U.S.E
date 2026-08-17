"""Characterization tests for the §5.3 complexity hotspots — gateway side.

Work Packet §5.3 lists fifteen branch-heavy functions and prescribes
*characterization tests and seam extraction*, "explicitly **not** a broad
rewrite".  This file is the first half of the characterization step for:

    gateway/run.py::_run_agent                  (2,343 lines / 485 branch nodes)
    gateway/run.py::_handle_message             (1,171 / 282)
    gateway/run.py::_handle_message_with_agent  (1,082 / 212)
    gateway/run.py::run_sync                    (  959 / 169)
    gateway/config.py::load_gateway_config      (  530 / 231)
    gateway/config.py::_apply_env_overrides     (  635 / 176)

A characterization test records what the code **does**, not what it ought to
do.  Several pins below capture asymmetries that look like defects — they are
labelled ``CHARACTERIZED ODDITY`` and deliberately left alone.  Changing them is
a behaviour change and must be made deliberately, not silently during a
refactor.  Nothing in this file refactors production code.

Scope is stated honestly rather than implied: see the module-level
``COVERAGE_NOTES`` at the bottom for what these tests do *not* reach.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Import shim for gateway.run — DOCUMENTED WORKAROUND, NOT A FIX
#
# On this working tree ``import gateway.run`` raises at import time:
#
#     gateway/restart.py:33
#     KeyError: 'restart_after_turn_timeout'
#
# The repository carries TWO diverging copies of ``DEFAULT_CONFIG``:
# ``hermes_cli/config_defaults.py`` (which defines the key, value 21600) and a
# stale duplicate at ``hermes_cli/config.py:577`` (which does not).  The stale
# copy is short 18 ``agent`` keys in total.  ``gateway/restart.py`` reads the
# stale one, so every module that imports ``gateway.run`` is unimportable.
#
# Fixing that is a production change in files this task does not own, so it is
# reported rather than fixed.  The shim below repairs the dict *only for the
# duration of the import*, then restores it, so the characterization tests can
# actually execute.  When the underlying defect is fixed the shim becomes a
# no-op — it never masks a different import error, and it never leaves the
# mutated dict behind for other tests in the same process.
# ---------------------------------------------------------------------------

def _import_gateway_run():
    try:
        import gateway.run as run_mod

        return run_mod
    except KeyError as exc:
        if "restart_after_turn_timeout" not in str(exc):
            raise
    import hermes_cli.config as _cfg
    import hermes_cli.config_defaults as _cfg_defaults

    agent_defaults = _cfg.DEFAULT_CONFIG["agent"]
    added = [
        key
        for key in _cfg_defaults.DEFAULT_CONFIG["agent"]
        if key not in agent_defaults
    ]
    for key in added:
        agent_defaults[key] = _cfg_defaults.DEFAULT_CONFIG["agent"][key]
    try:
        import gateway.run as run_mod
    finally:
        for key in added:
            agent_defaults.pop(key, None)
    return run_mod


gateway_run = _import_gateway_run()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def hermes_home() -> Path:
    """The per-test HERMES_HOME sandbox installed by tests/conftest.py."""
    return Path(os.environ["HERMES_HOME"])


def _write_yaml(home: Path, text: str) -> None:
    (home / "config.yaml").write_text(text, encoding="utf-8")


def _write_gateway_json(home: Path, obj: dict) -> None:
    (home / "gateway.json").write_text(json.dumps(obj), encoding="utf-8")


# ===========================================================================
# gateway/config.py :: load_gateway_config  (530 lines / 231 branch nodes)
#
# The docstring states the precedence contract:
#   1. environment variables
#   2. ~/.hermes/config.yaml
#   3. ~/.hermes/gateway.json  (legacy base layer)
#   4. built-in defaults
# Every test in this class pins one rung of that ladder.
# ===========================================================================

class TestLoadGatewayConfigPrecedence:
    def test_empty_home_yields_builtin_defaults_and_no_platforms(self, hermes_home):
        from gateway.config import load_gateway_config

        config = load_gateway_config()

        assert config.default_reset_policy.at_hour == 4
        assert config.default_reset_policy.idle_minutes == 1440
        assert config.multiplex_profiles is False
        assert config.max_concurrent_sessions is None
        # No config file at all means no platform is materialized.
        assert config.platforms == {}

    def test_gateway_json_is_the_base_layer_and_config_yaml_wins(self, hermes_home):
        """Rung 3 supplies defaults; rung 2 overwrites the keys it names."""
        from gateway.config import load_gateway_config

        _write_gateway_json(
            hermes_home,
            {"max_concurrent_sessions": 99, "always_log_local": True},
        )
        _write_yaml(hermes_home, "max_concurrent_sessions: 5\n")

        config = load_gateway_config()

        assert config.max_concurrent_sessions == 5  # config.yaml wins
        assert config.always_log_local is True      # gateway.json survives

    def test_top_level_key_beats_nested_gateway_section(self, hermes_home):
        from gateway.config import load_gateway_config

        _write_yaml(
            hermes_home,
            "session_reset:\n"
            "  at_hour: 7\n"
            "  idle_minutes: 30\n"
            "gateway:\n"
            "  session_reset:\n"
            "    at_hour: 19\n"
            "    idle_minutes: 999\n",
        )

        config = load_gateway_config()

        assert config.default_reset_policy.at_hour == 7
        assert config.default_reset_policy.idle_minutes == 30

    def test_nested_gateway_section_used_when_top_level_absent(self, hermes_home):
        from gateway.config import load_gateway_config

        _write_yaml(
            hermes_home,
            "gateway:\n"
            "  session_reset:\n"
            "    at_hour: 19\n"
            "    idle_minutes: 999\n",
        )

        config = load_gateway_config()

        assert config.default_reset_policy.at_hour == 19
        assert config.default_reset_policy.idle_minutes == 999

    def test_out_of_range_reset_policy_is_clamped_to_defaults(self, hermes_home):
        """_validate_gateway_config repairs in place rather than raising."""
        from gateway.config import load_gateway_config

        _write_yaml(
            hermes_home,
            "session_reset:\n  at_hour: 99\n  idle_minutes: -5\n",
        )

        config = load_gateway_config()

        assert config.default_reset_policy.at_hour == 4
        assert config.default_reset_policy.idle_minutes == 1440

    def test_malformed_yaml_falls_back_instead_of_raising(self, hermes_home):
        """The whole config.yaml block is one try/except: a syntax error
        silently discards *every* YAML-sourced setting and the gateway still
        starts on defaults."""
        from gateway.config import load_gateway_config

        _write_yaml(hermes_home, "session_reset: [unclosed\n")

        config = load_gateway_config()

        assert config.default_reset_policy.at_hour == 4
        assert config.platforms == {}

    def test_non_mapping_quick_commands_is_dropped_not_coerced(self, hermes_home):
        from gateway.config import load_gateway_config

        _write_yaml(hermes_home, "quick_commands: [1, 2, 3]\n")
        assert load_gateway_config().quick_commands == {}

        _write_yaml(
            hermes_home,
            "quick_commands:\n  hi:\n    type: exec\n    command: echo hi\n",
        )
        assert load_gateway_config().quick_commands == {
            "hi": {"type": "exec", "command": "echo hi"}
        }

    def test_api_server_shared_keys_are_bridged_into_extra(self, hermes_home):
        """``gateway.api_server.port`` must land in ``extra`` — PlatformConfig
        .from_dict only reads the nested ``extra:`` sub-key."""
        from gateway.config import Platform, load_gateway_config

        _write_yaml(
            hermes_home,
            "gateway:\n"
            "  api_server:\n"
            "    enabled: true\n"
            "    port: 8642\n"
            "    host: 127.0.0.1\n"
            f"    key: {'k' * 32}\n",
        )

        config = load_gateway_config()
        api = config.platforms[Platform.API_SERVER]

        assert api.enabled is True
        assert api.extra["port"] == 8642
        assert api.extra["host"] == "127.0.0.1"
        assert api.extra["key"] == "k" * 32

    def test_top_level_require_mention_bridges_to_telegram_and_env(
        self, hermes_home, monkeypatch
    ):
        from gateway.config import Platform, load_gateway_config

        # setenv (not delenv) so monkeypatch is guaranteed to restore/remove it.
        monkeypatch.setenv("TELEGRAM_REQUIRE_MENTION", "")
        _write_yaml(hermes_home, "require_mention: true\n")

        config = load_gateway_config()

        assert config.platforms[Platform.TELEGRAM].extra["require_mention"] is True
        assert os.environ["TELEGRAM_REQUIRE_MENTION"] == "true"

    def test_telegram_block_require_mention_beats_top_level(
        self, hermes_home, monkeypatch
    ):
        from gateway.config import Platform, load_gateway_config

        monkeypatch.setenv("TELEGRAM_REQUIRE_MENTION", "")
        _write_yaml(
            hermes_home,
            "require_mention: true\ntelegram:\n  require_mention: false\n",
        )

        config = load_gateway_config()

        assert config.platforms[Platform.TELEGRAM].extra["require_mention"] is False

    def test_nested_and_top_level_platform_blocks_deep_merge_extra(
        self, hermes_home
    ):
        """``gateway.platforms.<p>`` is merged FIRST, then ``platforms.<p>``:
        scalar keys take the top-level value, but ``extra`` dicts union."""
        from gateway.config import Platform, load_gateway_config

        _write_yaml(
            hermes_home,
            "gateway:\n"
            "  platforms:\n"
            "    discord:\n"
            "      enabled: false\n"
            "      extra:\n"
            "        a: 1\n"
            "platforms:\n"
            "  discord:\n"
            "    enabled: true\n"
            "    extra:\n"
            "      b: 2\n",
        )

        config = load_gateway_config()
        discord = config.platforms[Platform.DISCORD]

        assert discord.enabled is True          # top level wins the scalar
        assert discord.extra["a"] == 1          # nested extra survives
        assert discord.extra["b"] == 2          # top-level extra unioned in

    @pytest.mark.parametrize(
        "raw, expected",
        [("ignore", "ignore"), ("pair", "pair"), ("bogus", "pair"), ("5", "pair")],
    )
    def test_unauthorized_dm_behavior_normalizes_unknowns_to_pair(
        self, hermes_home, raw, expected
    ):
        from gateway.config import load_gateway_config

        _write_yaml(hermes_home, f"unauthorized_dm_behavior: {raw!r}\n")

        assert load_gateway_config().unauthorized_dm_behavior == expected

    def test_enabled_explicit_marker_never_escapes_into_the_returned_config(
        self, hermes_home
    ):
        """``_enabled_explicit`` is an internal handshake between
        load_gateway_config() and _apply_env_overrides(); the final cleanup
        loop pops it from every platform."""
        from gateway.config import Platform, load_gateway_config

        _write_yaml(hermes_home, "telegram:\n  enabled: false\n")

        telegram = load_gateway_config().platforms[Platform.TELEGRAM]

        assert telegram.enabled is False
        assert "_enabled_explicit" not in telegram.extra


class TestMultiplexProfilesEnvPrecedence:
    """GATEWAY_MULTIPLEX_PROFILES is rung 1 and beats config.yaml — but only
    for recognized tokens.  Blank and unrecognized values fall through."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("1", True),
            ("true", True),
            ("YES", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("no", False),
            ("OFF", False),
            ("", None),
            ("   ", None),
            ("banana", None),
        ],
    )
    def test_env_override_token_table(self, monkeypatch, raw, expected):
        from gateway.config import _env_multiplex_profiles_override

        monkeypatch.setenv("GATEWAY_MULTIPLEX_PROFILES", raw)

        assert _env_multiplex_profiles_override() is expected

    def test_unset_env_returns_none(self, monkeypatch):
        from gateway.config import _env_multiplex_profiles_override

        monkeypatch.delenv("GATEWAY_MULTIPLEX_PROFILES", raising=False)

        assert _env_multiplex_profiles_override() is None

    def test_env_off_overrides_config_yaml_opt_in(self, hermes_home, monkeypatch):
        from gateway.config import load_gateway_config

        _write_yaml(hermes_home, "gateway:\n  multiplex_profiles: true\n")

        monkeypatch.setenv("GATEWAY_MULTIPLEX_PROFILES", "")
        assert load_gateway_config().multiplex_profiles is True

        monkeypatch.setenv("GATEWAY_MULTIPLEX_PROFILES", "0")
        assert load_gateway_config().multiplex_profiles is False

        # CHARACTERIZED: a provisioned-but-empty secret must NOT shadow the
        # config.yaml opt-in, so blank falls back to True.
        monkeypatch.setenv("GATEWAY_MULTIPLEX_PROFILES", "   ")
        assert load_gateway_config().multiplex_profiles is True


# ===========================================================================
# gateway/config.py :: _apply_env_overrides  (635 lines / 176 branch nodes)
#
# Env vars are rung 1 of the precedence ladder.  The function is a long flat
# sequence of per-platform blocks that are NOT uniform — the tests below pin
# the differences, because a refactor that "unifies" them would change
# behaviour.
# ===========================================================================

@pytest.fixture()
def fresh_config():
    from gateway.config import GatewayConfig

    return GatewayConfig()


class TestApplyEnvOverridesEnablement:
    def test_no_env_enables_nothing(self, fresh_config):
        from gateway.config import _apply_env_overrides

        _apply_env_overrides(fresh_config)

        assert fresh_config.platforms == {}

    def test_bot_token_creates_and_enables_the_platform(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:abcdefgh")
        _apply_env_overrides(fresh_config)

        telegram = fresh_config.platforms[Platform.TELEGRAM]
        assert telegram.enabled is True
        assert telegram.token == "1234:abcdefgh"

    def test_explicit_disable_marker_blocks_reenable_but_token_is_still_stored(
        self, fresh_config, monkeypatch
    ):
        """CHARACTERIZED ODDITY: an explicitly disabled platform stays
        disabled, yet the env token is still written onto its config.  The
        comment at gateway/config.py:1996 says this is deliberate (skills may
        send without the adapter running) — pinned so a refactor cannot drop
        it by accident."""
        from gateway.config import Platform, PlatformConfig, _apply_env_overrides

        fresh_config.platforms[Platform.TELEGRAM] = PlatformConfig(
            enabled=False, extra={"_enabled_explicit": True}
        )
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:abcdefgh")

        _apply_env_overrides(fresh_config)

        telegram = fresh_config.platforms[Platform.TELEGRAM]
        assert telegram.enabled is False
        assert telegram.token == "1234:abcdefgh"

    def test_disabled_without_the_marker_is_reenabled_by_the_token(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, PlatformConfig, _apply_env_overrides

        fresh_config.platforms[Platform.TELEGRAM] = PlatformConfig(enabled=False)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:abcdefgh")

        _apply_env_overrides(fresh_config)

        assert fresh_config.platforms[Platform.TELEGRAM].enabled is True

    def test_enabled_explicit_marker_is_stripped_from_every_platform(
        self, fresh_config
    ):
        from gateway.config import Platform, PlatformConfig, _apply_env_overrides

        fresh_config.platforms[Platform.TELEGRAM] = PlatformConfig(
            enabled=True, extra={"_enabled_explicit": True, "keep": "me"}
        )

        _apply_env_overrides(fresh_config)

        extra = fresh_config.platforms[Platform.TELEGRAM].extra
        assert "_enabled_explicit" not in extra
        assert extra["keep"] == "me"


class TestApplyEnvOverridesValueParsing:
    @pytest.mark.parametrize("raw", ["off", "first", "all", "ALL", "First"])
    def test_valid_reply_mode_is_lowercased_and_materializes_the_platform(
        self, fresh_config, monkeypatch, raw
    ):
        """CHARACTERIZED ODDITY: the reply-mode branch creates the platform
        entry but leaves ``enabled=False`` — unlike the token branch, which
        enables.  A settings-only env var must not turn a platform on."""
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("TELEGRAM_REPLY_TO_MODE", raw)
        _apply_env_overrides(fresh_config)

        telegram = fresh_config.platforms[Platform.TELEGRAM]
        assert telegram.reply_to_mode == raw.lower()
        assert telegram.enabled is False

    @pytest.mark.parametrize("raw", ["bogus", "", "  ", "none"])
    def test_invalid_reply_mode_does_not_even_create_the_platform(
        self, fresh_config, monkeypatch, raw
    ):
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("TELEGRAM_REPLY_TO_MODE", raw)
        _apply_env_overrides(fresh_config)

        assert Platform.TELEGRAM not in fresh_config.platforms

    def test_fallback_ips_are_split_stripped_and_emptied_out(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("TELEGRAM_FALLBACK_IPS", " 1.1.1.1 , ,2.2.2.2,")
        _apply_env_overrides(fresh_config)

        assert fresh_config.platforms[Platform.TELEGRAM].extra["fallback_ips"] == [
            "1.1.1.1",
            "2.2.2.2",
        ]

    def test_home_channel_env_is_asymmetric_between_telegram_and_slack(
        self, fresh_config, monkeypatch
    ):
        """CHARACTERIZED ODDITY, and the highest-risk one in this function.

        ``TELEGRAM_HOME_CHANNEL`` is applied only ``if ... in config.platforms``
        — with no other Telegram config it is silently dropped.
        ``SLACK_HOME_CHANNEL`` uses ``setdefault`` and creates a *disabled*
        Slack entry instead.  The default channel name differs too: "Home" for
        Telegram, "" for Slack.
        """
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1001234")
        monkeypatch.setenv("SLACK_HOME_CHANNEL", "C0123456")

        _apply_env_overrides(fresh_config)

        assert Platform.TELEGRAM not in fresh_config.platforms

        slack = fresh_config.platforms[Platform.SLACK]
        assert slack.enabled is False
        assert slack.home_channel.chat_id == "C0123456"
        assert slack.home_channel.name == ""

    def test_telegram_home_channel_applies_once_the_platform_exists(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:abcdefgh")
        monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1001234")

        _apply_env_overrides(fresh_config)

        home = fresh_config.platforms[Platform.TELEGRAM].home_channel
        assert home.chat_id == "-1001234"
        assert home.name == "Home"

    @pytest.mark.parametrize(
        "raw, expected",
        [("false", False), ("0", False), ("no", False), ("true", True), ("", True)],
    )
    def test_whatsapp_enabled_respects_explicit_disable_over_yaml(
        self, fresh_config, monkeypatch, raw, expected
    ):
        """A YAML-enabled WhatsApp stays on unless the env explicitly says
        false/0/no.  A blank value keeps whatever YAML set."""
        from gateway.config import Platform, PlatformConfig, _apply_env_overrides

        fresh_config.platforms[Platform.WHATSAPP] = PlatformConfig(enabled=True)
        monkeypatch.setenv("WHATSAPP_ENABLED", raw)

        _apply_env_overrides(fresh_config)

        assert fresh_config.platforms[Platform.WHATSAPP].enabled is expected

    def test_weak_api_server_key_does_not_materialize_the_platform(
        self, fresh_config, monkeypatch
    ):
        """The adapter's startup guard requires a >=16 char usable secret; the
        loader refuses to create the platform at all rather than creating one
        the adapter will refuse to start."""
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("API_SERVER_KEY", "short")
        _apply_env_overrides(fresh_config)

        assert Platform.API_SERVER not in fresh_config.platforms

    def test_usable_api_server_key_enables_and_bridges_into_extra(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, _apply_env_overrides

        monkeypatch.setenv("API_SERVER_KEY", "x" * 32)
        _apply_env_overrides(fresh_config)

        api = fresh_config.platforms[Platform.API_SERVER]
        assert api.enabled is True
        assert api.extra["key"] == "x" * 32

    def test_relay_url_env_beats_yaml_and_trailing_slash_is_stripped(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, PlatformConfig, _apply_env_overrides

        fresh_config.platforms[Platform.RELAY] = PlatformConfig(
            enabled=False, extra={"relay_url": "https://yaml.example/"}
        )
        monkeypatch.setenv("GATEWAY_RELAY_URL", "  https://relay.example/  ")

        _apply_env_overrides(fresh_config)

        relay = fresh_config.platforms[Platform.RELAY]
        assert relay.enabled is True
        assert relay.extra["relay_url"] == "https://relay.example"

    def test_relay_falls_back_to_the_yaml_url_when_env_is_absent(
        self, fresh_config, monkeypatch
    ):
        from gateway.config import Platform, PlatformConfig, _apply_env_overrides

        fresh_config.platforms[Platform.RELAY] = PlatformConfig(
            enabled=False, extra={"relay_url": "https://yaml.example/"}
        )
        monkeypatch.setenv("GATEWAY_RELAY_URL", "")

        _apply_env_overrides(fresh_config)

        relay = fresh_config.platforms[Platform.RELAY]
        assert relay.enabled is True
        assert relay.extra["relay_url"] == "https://yaml.example"


class TestCoerceHelpersUsedByBothLoaders:
    """The small coercers are the seams ``load_gateway_config`` and
    ``_apply_env_overrides`` both lean on; every one of them swallows bad
    input rather than raising, which is why a typo never stops the gateway."""

    @pytest.mark.parametrize(
        "value, default, expected",
        [
            (None, True, True),
            (None, False, False),
            ("true", False, True),
            ("  ON  ", False, True),
            ("off", True, False),
            ("0", True, False),
            ("maybe", True, True),      # unrecognized string keeps the default
            ("maybe", False, False),
        ],
    )
    def test_coerce_bool_preserves_the_caller_default(self, value, default, expected):
        from gateway.config import _coerce_bool

        assert _coerce_bool(value, default) is expected

    @pytest.mark.parametrize(
        "value, expected",
        [(None, "auto"), (True, "auto"), (False, "off"), ("  SSE ", "sse"), ("", "auto")],
    )
    def test_normalize_transport_token_handles_the_yaml_bool_quirk(
        self, value, expected
    ):
        """YAML 1.1 parses a bare ``off`` as boolean False; without this
        mapping ``mode: off`` would stringify to "false" and enable streaming."""
        from gateway.config import _normalize_transport_token

        assert _normalize_transport_token(value) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [
            (None, 0),
            (True, 0),          # bool is rejected, not coerced to 1
            (0, 0),
            (30, 30),
            ("30", 30),
            ("  30  ", 30),
            ("-1", 0),
            ("abc", 0),
            (2_147_483_648, 0),  # above the systemd ceiling
            (2_147_483_647, 2_147_483_647),
        ],
    )
    def test_coerce_systemd_watchdog_seconds(self, value, expected):
        from gateway.config import coerce_systemd_watchdog_seconds

        assert coerce_systemd_watchdog_seconds(value) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [(None, None), (True, None), (0, None), (-3, None), (7, 7), ("7", 7),
         (7.0, 7), (7.5, None), ("nope", None)],
    )
    def test_coerce_optional_positive_int(self, value, expected):
        from gateway.config import _coerce_optional_positive_int

        assert _coerce_optional_positive_int(value, "k") == expected


# ===========================================================================
# gateway/run.py :: _handle_message  (1,171 lines / 282 branch nodes)
#
# The reachable seam is the dispatch prologue: plugin hook -> authorization ->
# pending-update interception -> pending-clarify interception.  Each of those
# returns before the session/agent machinery starts, so they are testable with
# a hollow runner.  Everything after the clarify interception needs a live
# SessionStore and agent and is NOT covered here (see COVERAGE_NOTES).
# ===========================================================================

def _make_source(
    *,
    platform_value: str = "slack",
    user_id: str | None = "u1",
    chat_type: str = "dm",
    chat_id: str = "c1",
):
    from gateway.platforms.base import SessionSource

    return SessionSource(
        platform=MagicMock(value=platform_value),
        chat_id=chat_id,
        chat_type=chat_type,
        user_id=user_id,
        user_name="Tester",
    )


def _make_event(text: str = "hello", *, internal: bool = False, **source_kwargs):
    from gateway.platforms.base import MessageEvent, MessageType

    event = MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=_make_source(**source_kwargs),
        message_id="m1",
    )
    event.internal = internal
    return event


def _make_runner(*, authorized: bool = True, dm_behavior: str = "pair"):
    """Hollow GatewayRunner — the ``object.__new__`` pattern already used by
    tests/gateway/test_busy_session_auth_bypass.py."""
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner.config = MagicMock()
    runner.session_store = MagicMock()
    runner.pairing_store = MagicMock()
    runner.pairing_store._is_rate_limited.return_value = False
    runner.pairing_store.generate_code.return_value = "ABC123"
    runner._update_prompt_pending = {}
    runner._is_user_authorized = lambda source: authorized
    runner._get_unauthorized_dm_behavior = lambda platform: dm_behavior
    runner._session_key_for_source = lambda source: "sess-key"
    return runner


@pytest.fixture()
def quiet_dispatch(monkeypatch):
    """Neutralize the two optional side-channels the prologue touches so the
    branch under test is the only thing exercised."""
    import hermes_cli.plugins as plugins_mod
    import tools.clarify_gateway as clarify_mod

    monkeypatch.setattr(plugins_mod, "invoke_hook", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(
        clarify_mod, "get_pending_for_session", lambda key: None, raising=False
    )
    return plugins_mod, clarify_mod


class TestHandleMessagePrologue:
    def test_unauthorized_dm_offers_a_pairing_code_and_returns_none(
        self, quiet_dispatch
    ):
        from gateway.run import GatewayRunner

        runner = _make_runner(authorized=False, dm_behavior="pair")
        adapter = MagicMock()
        adapter.send = AsyncMock()
        event = _make_event()
        runner.adapters[event.source.platform] = adapter

        result = asyncio.run(GatewayRunner._handle_message(runner, event))

        assert result is None
        runner.pairing_store.generate_code.assert_called_once()
        adapter.send.assert_awaited_once()
        assert "ABC123" in adapter.send.await_args.args[1]

    def test_rate_limited_unauthorized_dm_is_silent(self, quiet_dispatch):
        from gateway.run import GatewayRunner

        runner = _make_runner(authorized=False, dm_behavior="pair")
        runner.pairing_store._is_rate_limited.return_value = True
        adapter = MagicMock()
        adapter.send = AsyncMock()
        event = _make_event()
        runner.adapters[event.source.platform] = adapter

        result = asyncio.run(GatewayRunner._handle_message(runner, event))

        assert result is None
        runner.pairing_store.generate_code.assert_not_called()
        adapter.send.assert_not_awaited()

    def test_unauthorized_group_message_is_dropped_without_pairing(
        self, quiet_dispatch
    ):
        from gateway.run import GatewayRunner

        runner = _make_runner(authorized=False, dm_behavior="pair")
        adapter = MagicMock()
        adapter.send = AsyncMock()
        event = _make_event(chat_type="channel")
        runner.adapters[event.source.platform] = adapter

        result = asyncio.run(GatewayRunner._handle_message(runner, event))

        assert result is None
        runner.pairing_store.generate_code.assert_not_called()
        adapter.send.assert_not_awaited()

    def test_unauthorized_dm_with_ignore_behavior_sends_nothing(self, quiet_dispatch):
        from gateway.run import GatewayRunner

        runner = _make_runner(authorized=False, dm_behavior="ignore")
        adapter = MagicMock()
        adapter.send = AsyncMock()
        event = _make_event()
        runner.adapters[event.source.platform] = adapter

        assert asyncio.run(GatewayRunner._handle_message(runner, event)) is None
        runner.pairing_store.generate_code.assert_not_called()
        adapter.send.assert_not_awaited()

    def test_missing_user_id_defers_to_the_authorization_check(self, quiet_dispatch):
        """A message with no user identity cannot be paired, but a chat-scoped
        allowlist can still authorize it — so the branch calls
        ``_is_user_authorized`` rather than dropping outright."""
        from gateway.run import GatewayRunner

        runner = _make_runner(authorized=False)
        seen = []
        runner._is_user_authorized = lambda source: (seen.append(source), False)[1]
        event = _make_event(user_id=None)

        assert asyncio.run(GatewayRunner._handle_message(runner, event)) is None
        assert len(seen) == 1

    def test_plugin_hook_skip_short_circuits_before_authorization(self, monkeypatch):
        import hermes_cli.plugins as plugins_mod
        from gateway.run import GatewayRunner

        monkeypatch.setattr(
            plugins_mod,
            "invoke_hook",
            lambda *a, **k: [{"action": "skip", "reason": "handled"}],
            raising=False,
        )
        runner = _make_runner(authorized=False)
        called = []
        runner._is_user_authorized = lambda source: called.append(source) or True
        event = _make_event()

        assert asyncio.run(GatewayRunner._handle_message(runner, event)) is None
        assert called == []  # auth never ran — the hook is ahead of it

    def test_plugin_hook_rewrite_replaces_event_text_and_continues(
        self, monkeypatch
    ):
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        monkeypatch.setattr(
            plugins_mod,
            "invoke_hook",
            lambda *a, **k: [{"action": "rewrite", "text": "REWRITTEN"}],
            raising=False,
        )
        seen_texts = []

        class _Pending:
            clarify_id = "cl-1"

        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", lambda key: _Pending(), raising=False
        )

        def _resolve(clarify_id, text):
            seen_texts.append(text)
            return True

        monkeypatch.setattr(
            clarify_mod, "resolve_gateway_clarify", _resolve, raising=False
        )

        runner = _make_runner()
        event = _make_event("original")

        # The clarify interception is the next observable stop after the hook,
        # so it reports which text survived the rewrite.
        assert asyncio.run(GatewayRunner._handle_message(runner, event)) == ""
        assert seen_texts == ["REWRITTEN"]

    def test_hook_failure_is_swallowed_and_dispatch_continues(self, monkeypatch):
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        def _boom(*a, **k):
            raise RuntimeError("plugin exploded")

        monkeypatch.setattr(plugins_mod, "invoke_hook", _boom, raising=False)
        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", lambda key: None, raising=False
        )

        runner = _make_runner(authorized=False)
        event = _make_event(chat_type="channel")

        # Reaches (and is stopped by) the auth gate rather than propagating.
        assert asyncio.run(GatewayRunner._handle_message(runner, event)) is None

    def test_internal_events_skip_the_hook_and_the_auth_gate(self, monkeypatch):
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        hook_calls = []
        monkeypatch.setattr(
            plugins_mod,
            "invoke_hook",
            lambda *a, **k: hook_calls.append(a) or [],
            raising=False,
        )

        class _Pending:
            clarify_id = "cl-1"

        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", lambda key: _Pending(), raising=False
        )
        monkeypatch.setattr(
            clarify_mod, "resolve_gateway_clarify", lambda *a: True, raising=False
        )

        runner = _make_runner(authorized=False)
        auth_calls = []
        runner._is_user_authorized = lambda source: auth_calls.append(source) or False
        event = _make_event("hi", internal=True)

        assert asyncio.run(GatewayRunner._handle_message(runner, event)) == ""
        assert hook_calls == []
        assert auth_calls == []


class TestHandleMessagePendingUpdatePrompt:
    """The /update prompt interception writes ``.update_response`` under
    HERMES_HOME.  ``gateway.run._hermes_home`` is resolved at import time, so
    the test rebinds it rather than relying on the env var."""

    @pytest.fixture(autouse=True)
    def _redirect_hermes_home(self, tmp_path, monkeypatch):
        import gateway.run as run_mod

        monkeypatch.setattr(run_mod, "_hermes_home", tmp_path)
        self.home = tmp_path
        return tmp_path

    @pytest.mark.parametrize(
        "text, expected_written",
        [
            ("/approve", "y"),
            ("/yes", "y"),
            ("/deny", "n"),
            ("/no", "n"),
            ("mytoken", "mytoken"),
        ],
    )
    def test_pending_prompt_captures_the_reply(
        self, quiet_dispatch, text, expected_written
    ):
        from gateway.run import GatewayRunner

        runner = _make_runner()
        runner._update_prompt_pending = {"sess-key": True}
        event = _make_event(text)

        result = asyncio.run(GatewayRunner._handle_message(runner, event))

        assert result.startswith("✓ Sent")
        assert (self.home / ".update_response").read_text() == expected_written
        # The pending marker is consumed so the next message dispatches normally.
        assert runner._update_prompt_pending == {}

    def test_long_reply_is_truncated_in_the_confirmation_only(self, quiet_dispatch):
        from gateway.run import GatewayRunner

        runner = _make_runner()
        runner._update_prompt_pending = {"sess-key": True}
        long_text = "z" * 40
        event = _make_event(long_text)

        result = asyncio.run(GatewayRunner._handle_message(runner, event))

        assert "…" in result
        assert (self.home / ".update_response").read_text() == long_text

    def test_recognized_slash_command_cancels_the_prompt_and_falls_through(
        self, monkeypatch
    ):
        """CHARACTERIZED: ``/new`` during a pending update prompt writes an
        EMPTY response — unblocking the detached updater with its own default
        — and then continues into normal dispatch instead of returning.

        It also survives the pending-clarify interceptor untouched: that block
        deliberately refuses to consume anything starting with ``/``.  So a
        recognized slash command passes BOTH interceptors, which the hollow
        runner proves by falling into the session machinery it cannot serve.
        """
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        monkeypatch.setattr(
            plugins_mod, "invoke_hook", lambda *a, **k: [], raising=False
        )

        class _Pending:
            clarify_id = "cl-1"

        resolved = []
        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", lambda key: _Pending(), raising=False
        )
        monkeypatch.setattr(
            clarify_mod,
            "resolve_gateway_clarify",
            lambda *a: resolved.append(a) or True,
            raising=False,
        )

        runner = _make_runner()
        runner._update_prompt_pending = {"sess-key": True}
        event = _make_event("/new")

        with pytest.raises(AttributeError, match="_running_agents"):
            asyncio.run(GatewayRunner._handle_message(runner, event))

        assert (self.home / ".update_response").read_text() == ""
        assert runner._update_prompt_pending == {}
        assert resolved == []  # the clarify interceptor let the command past


class TestHandleMessagePendingClarify:
    def test_free_text_reply_resolves_the_clarify_and_returns_empty_string(
        self, monkeypatch
    ):
        """The empty string is load-bearing: adapters that echo the return
        value must not double-post, because the agent emits the next message."""
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        monkeypatch.setattr(
            plugins_mod, "invoke_hook", lambda *a, **k: [], raising=False
        )

        class _Pending:
            clarify_id = "cl-42"

        resolved = []
        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", lambda key: _Pending(), raising=False
        )
        monkeypatch.setattr(
            clarify_mod,
            "resolve_gateway_clarify",
            lambda cid, text: resolved.append((cid, text)) or True,
            raising=False,
        )

        runner = _make_runner()

        assert asyncio.run(
            GatewayRunner._handle_message(runner, _make_event("  blue  "))
        ) == ""
        assert resolved == [("cl-42", "blue")]

    def test_slash_command_during_a_pending_clarify_is_not_swallowed(
        self, monkeypatch
    ):
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        monkeypatch.setattr(
            plugins_mod, "invoke_hook", lambda *a, **k: [], raising=False
        )

        class _Pending:
            clarify_id = "cl-42"

        resolved = []
        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", lambda key: _Pending(), raising=False
        )
        monkeypatch.setattr(
            clarify_mod,
            "resolve_gateway_clarify",
            lambda cid, text: resolved.append((cid, text)) or True,
            raising=False,
        )

        runner = _make_runner()
        # Falls through into the session machinery, which the hollow runner
        # cannot serve — the point is that the clarify path did NOT consume it.
        with pytest.raises(AttributeError, match="_running_agents"):
            asyncio.run(GatewayRunner._handle_message(runner, _make_event("/help")))
        assert resolved == []

    def test_clarify_lookup_failure_is_swallowed(self, monkeypatch):
        import hermes_cli.plugins as plugins_mod
        import tools.clarify_gateway as clarify_mod
        from gateway.run import GatewayRunner

        monkeypatch.setattr(
            plugins_mod, "invoke_hook", lambda *a, **k: [], raising=False
        )

        def _boom(key):
            raise RuntimeError("clarify store down")

        monkeypatch.setattr(
            clarify_mod, "get_pending_for_session", _boom, raising=False
        )

        runner = _make_runner(authorized=False)
        event = _make_event(chat_type="channel")

        assert asyncio.run(GatewayRunner._handle_message(runner, event)) is None


# ===========================================================================
# gateway/run.py :: _run_agent  (2,343 lines / 485 branch nodes)
#
# The first statement of the function is a whole-body bypass: proxy mode.
# It is the one branch of _run_agent reachable without a live AIAgent, and it
# is exactly the kind of argument-forwarding a seam extraction breaks.
# ===========================================================================

class TestRunAgentProxyDelegation:
    def test_proxy_mode_delegates_and_drops_two_parameters(self):
        """CHARACTERIZED ODDITY: ``channel_prompt`` and ``_interrupt_depth``
        are accepted by ``_run_agent`` but are NOT forwarded to
        ``_run_agent_via_proxy``.  A per-channel system prompt therefore
        silently does not apply in proxy mode."""
        from gateway.run import GatewayRunner

        runner = object.__new__(GatewayRunner)
        runner._get_proxy_url = lambda: "http://proxy.invalid"
        captured = {}

        async def _via_proxy(**kwargs):
            captured.update(kwargs)
            return {"final_response": "from-proxy"}

        runner._run_agent_via_proxy = _via_proxy
        source = _make_source()

        result = asyncio.run(
            GatewayRunner._run_agent(
                runner,
                message="hi",
                context_prompt="ctx",
                history=[{"role": "user", "content": "hi"}],
                source=source,
                session_id="s1",
                session_key="sk1",
                run_generation=3,
                _interrupt_depth=2,
                event_message_id="m9",
                channel_prompt="CHANNEL PROMPT",
            )
        )

        assert result == {"final_response": "from-proxy"}
        assert set(captured) == {
            "message",
            "context_prompt",
            "history",
            "source",
            "session_id",
            "session_key",
            "run_generation",
            "event_message_id",
        }
        assert "channel_prompt" not in captured
        assert "_interrupt_depth" not in captured
        assert captured["run_generation"] == 3

    def test_no_proxy_url_does_not_take_the_proxy_path(self):
        from gateway.run import GatewayRunner

        runner = object.__new__(GatewayRunner)
        runner._get_proxy_url = lambda: ""
        called = []

        async def _via_proxy(**kwargs):
            called.append(kwargs)
            return {}

        runner._run_agent_via_proxy = _via_proxy

        # Falls past the bypass into the real body, which the hollow runner
        # cannot serve. The assertion is that the proxy was NOT used; which
        # attribute the body trips over first is an implementation detail and
        # is deliberately not pinned.
        with pytest.raises(AttributeError):
            asyncio.run(
                GatewayRunner._run_agent(
                    runner,
                    message="hi",
                    context_prompt="",
                    history=[],
                    source=_make_source(),
                    session_id="s1",
                )
            )
        assert called == []


# ===========================================================================
# Seam helpers the hotspot bodies call.
#
# These module-level functions are the already-extracted seams of the two
# largest run.py hotspots: _normalize_empty_agent_response,
# _should_clear_resume_pending_after_turn and _sanitize_gateway_final_response
# are the post-turn tail of _handle_message_with_agent (run.py:8627-8642);
# _is_control_interrupt_message (17672) and
# _preserve_queued_followup_history_offset (17868) sit inside _run_agent.
# Pinning them protects the seams a further extraction would lean on.
# ===========================================================================

class TestNormalizeEmptyAgentResponse:
    def test_non_empty_response_is_returned_untouched(self):
        from gateway.run import _normalize_empty_agent_response

        assert _normalize_empty_agent_response({"failed": True}, "real text") == "real text"

    @pytest.mark.parametrize(
        "error",
        ["context length exceeded", "TOKEN limit", "payload too large", "prompt too long"],
    )
    def test_context_shaped_failures_get_the_compact_advice(self, error):
        from gateway.run import _normalize_empty_agent_response

        out = _normalize_empty_agent_response({"failed": True, "error": error}, "")

        assert "Session too large" in out
        assert "/compact" in out

    def test_http_400_is_a_context_failure_only_with_a_long_history(self):
        from gateway.run import _normalize_empty_agent_response

        short = _normalize_empty_agent_response(
            {"failed": True, "error": "400 bad request"}, "", history_len=10
        )
        long = _normalize_empty_agent_response(
            {"failed": True, "error": "400 bad request"}, "", history_len=51
        )

        assert "The request failed" in short
        assert "Session too large" in long

    def test_generic_failure_truncates_the_error_at_300_chars(self):
        from gateway.run import _normalize_empty_agent_response

        out = _normalize_empty_agent_response(
            {"failed": True, "error": "e" * 500}, ""
        )

        assert "e" * 300 in out
        assert "e" * 301 not in out

    def test_silent_success_with_api_calls_gets_a_transient_error_notice(self):
        from gateway.run import _normalize_empty_agent_response

        out = _normalize_empty_agent_response({"api_calls": 2}, "")

        assert "no response was generated" in out

    def test_interrupted_turn_keeps_the_empty_response(self):
        from gateway.run import _normalize_empty_agent_response

        assert _normalize_empty_agent_response(
            {"api_calls": 2, "interrupted": True}, ""
        ) == ""

    def test_partial_result_reports_the_stop_reason(self):
        from gateway.run import _normalize_empty_agent_response

        out = _normalize_empty_agent_response(
            {"api_calls": 1, "partial": True, "error": "tool crashed"}, ""
        )

        assert out.startswith("⚠️ Processing stopped: tool crashed")

    def test_zero_api_calls_stays_empty(self):
        from gateway.run import _normalize_empty_agent_response

        assert _normalize_empty_agent_response({"api_calls": 0}, "") == ""


class TestShouldClearResumePendingAfterTurn:
    @pytest.mark.parametrize(
        "result, expected",
        [
            ({}, True),
            ({"completed": True}, True),
            ({"interrupted": True}, False),
            ({"failed": True}, False),
            ({"partial": True}, False),
            ({"error": "boom"}, False),
            ({"completed": False}, False),
            ({"completed": None}, True),   # only an explicit False blocks it
            ({"error": ""}, True),         # falsy error does not block
            ("not a dict", False),
        ],
    )
    def test_truth_table(self, result, expected):
        from gateway.run import _should_clear_resume_pending_after_turn

        assert _should_clear_resume_pending_after_turn(result) is expected


class TestPreserveQueuedFollowupHistoryOffset:
    def test_outer_offset_is_carried_into_the_followup(self):
        from gateway.run import _preserve_queued_followup_history_offset

        merged = _preserve_queued_followup_history_offset(
            {"history_offset": 3}, {"history_offset": 9, "final_response": "x"}
        )

        assert merged["history_offset"] == 3
        assert merged["final_response"] == "x"

    def test_followup_offset_already_at_or_below_the_outer_one_is_kept(self):
        from gateway.run import _preserve_queued_followup_history_offset

        followup = {"history_offset": 2}
        assert (
            _preserve_queued_followup_history_offset({"history_offset": 3}, followup)
            is followup
        )

    def test_missing_or_non_int_offsets_return_the_followup_unchanged(self):
        from gateway.run import _preserve_queued_followup_history_offset

        followup = {"final_response": "x"}
        assert (
            _preserve_queued_followup_history_offset({"history_offset": 3}, followup)
            is not followup
        )
        assert (
            _preserve_queued_followup_history_offset({}, followup) is followup
        )
        assert (
            _preserve_queued_followup_history_offset({"history_offset": "3"}, followup)
            is followup
        )

    def test_merge_does_not_mutate_the_followup_dict(self):
        from gateway.run import _preserve_queued_followup_history_offset

        followup = {"history_offset": 9}
        merged = _preserve_queued_followup_history_offset(
            {"history_offset": 3}, followup
        )

        assert followup["history_offset"] == 9
        assert merged is not followup


class TestControlInterruptClassification:
    @pytest.mark.parametrize(
        "message, expected",
        [
            ("Stop requested", True),
            ("stop requested", True),
            ("  Stop    requested  ", True),   # whitespace is collapsed
            ("Session reset requested", True),
            ("Execution timed out (inactivity)", True),
            ("SSE client disconnected", True),
            ("Gateway shutting down", True),
            ("Gateway restarting", True),
            ("please stop", False),
            ("Stop requested now", False),
            ("", False),
            (None, False),
        ],
    )
    def test_truth_table(self, message, expected):
        from gateway.run import _is_control_interrupt_message

        assert _is_control_interrupt_message(message) is expected


class TestSanitizeGatewayFinalResponse:
    def test_non_telegram_platforms_are_passed_through_verbatim(self):
        from gateway.run import _sanitize_gateway_final_response

        raw = "API call failed: sk-abcdefghijklmnopqrstuvwxyz012345"
        assert _sanitize_gateway_final_response("discord", raw) == raw

    def test_telegram_provider_error_is_replaced_by_a_category(self):
        from gateway.run import _sanitize_gateway_final_response

        out = _sanitize_gateway_final_response(
            "telegram", "API call failed: incorrect api key provided"
        )

        assert "⚠️" in out
        assert "incorrect api key" not in out.lower()

    def test_telegram_prose_mentioning_a_status_code_is_not_rewritten(self):
        from gateway.run import _sanitize_gateway_final_response

        prose = "Sure — HTTP 404 means the resource was not found, so check the path."
        assert _sanitize_gateway_final_response("telegram", prose) == prose

    def test_empty_text_short_circuits(self):
        from gateway.run import _sanitize_gateway_final_response

        assert _sanitize_gateway_final_response("telegram", "") == ""


# ---------------------------------------------------------------------------
# COVERAGE_NOTES — what these tests deliberately do NOT reach.
#
# Stated explicitly because §29.2 forbids presenting partial work as complete.
#
#   gateway/run.py::_run_agent (485 branch nodes)
#       Covered: the proxy-mode bypass and its argument forwarding, plus two
#       module-level seams called from its body.  NOT covered: the ~700 lines
#       of toolset/display/streaming resolution, the progress-queue plumbing,
#       the interrupt/resume ladder, or the executor hand-off.  Those need a
#       live AIAgent and a real event loop with adapters.
#
#   gateway/run.py::run_sync (169 branch nodes)
#       NOT covered at all.  ``run_sync`` is a closure defined inside
#       ``_run_agent`` (run.py:16357) with no independent entry point, so it
#       cannot be called without first driving ~700 lines of _run_agent setup
#       and constructing a real AIAgent.  Reaching it is blocked, not skipped.
#
#   gateway/run.py::_handle_message_with_agent (212 branch nodes)
#       NOT covered as a function.  Its first act is
#       ``self.session_store.get_or_create_session(source)`` and everything
#       after depends on a live SessionStore, session DB and adapter set.
#       Covered instead: its post-turn tail seams (run.py:8627-8642).
#
#   gateway/run.py::_handle_message (282 branch nodes)
#       Covered: the dispatch prologue — plugin hook actions, the four
#       authorization outcomes, the pending-update interception and the
#       pending-clarify interception.  NOT covered: command dispatch, the
#       busy-session/interrupt path, media handling, or anything past the
#       clarify block.
#
#   gateway/config.py::load_gateway_config (231 branch nodes)
#       Covered: the four-rung precedence ladder, the top-level-vs-nested
#       fallback contract, the shared-key and api_server bridging, the
#       malformed-YAML fallback, and the _enabled_explicit handshake.  NOT
#       covered: the per-plugin ``apply_yaml_config_fn`` dispatch (needs the
#       platform registry populated with real plugin entries) or the
#       per-platform bridged-key list beyond require_mention.
#
#   gateway/config.py::_apply_env_overrides (176 branch nodes)
#       Covered: the enablement contract (_enable_from_env, the
#       _enabled_explicit marker, the final strip), the value-parsing branches
#       for Telegram/Slack/WhatsApp/API-server/relay, and the shared coercers.
#       NOT covered: the ~20 remaining per-platform env blocks (Discord,
#       Signal, Matrix, Mattermost, Email, SMS, Home Assistant, WhatsApp
#       Cloud, …) which follow the same shapes, and the registry-driven
#       plugin-enable pass, whose outcome depends on which plugins are
#       installed in the running environment.
# ---------------------------------------------------------------------------
