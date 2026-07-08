"""muse omni launcher — argparse + full-agent defaults."""

from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli.main import _BUILTIN_SUBCOMMANDS, cmd_omni


def test_omni_in_builtin_subcommands() -> None:
    assert "omni" in _BUILTIN_SUBCOMMANDS


def test_omni_appears_in_cli_help() -> None:
    from hermes_cli import main as _main

    argv_backup = sys.argv[:]
    sys.argv = ["muse", "--help"]
    buf = io.StringIO()
    try:
        with patch.object(_main, "_plugin_cli_discovery_needed", return_value=False):
            with redirect_stdout(buf):
                with pytest.raises(SystemExit):
                    _main.main()
    finally:
        sys.argv = argv_backup

    text = buf.getvalue()
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", text)
    assert m, text[:500]
    assert "omni" in m.group(1).split(",")


def test_cmd_omni_serves_full_agent() -> None:
    captured: dict = {}

    def fake_serve(**kwargs):
        captured.update(kwargs)
        srv = MagicMock()
        srv.server_address = ("127.0.0.1", 8765)
        return srv

    args = SimpleNamespace(
        with_admin=False,
        no_open=True,
        admin_port=9119,
        skip_build=False,
        host="127.0.0.1",
        port=8765,
        allow_external=False,
        allow_external_hosts=None,
        cors_origins=None,
        agent_mode="full",
    )

    with (
        patch("gateway.cockpit.auth.load_or_create_token", return_value="tok"),
        patch("gateway.cockpit.server.serve", side_effect=fake_serve),
        patch("webbrowser.open"),
        patch("time.sleep", side_effect=KeyboardInterrupt),
    ):
        with pytest.raises(SystemExit) as exc:
            cmd_omni(args)
        assert exc.value.code == 0

    assert captured.get("agent_mode") == "full"
    assert captured.get("token") == "tok"
    assert captured.get("port") == 8765


def test_cockpit_dc_has_local_admin_and_opencode_external_nav() -> None:
    page = Path("gateway/cockpit/static/cockpit.dc.html").read_text(encoding="utf-8")
    assert "local-admin" in page
    assert "Local Admin" in page
    assert "opencode-chat" in page
    assert "http://127.0.0.1:9119/" in page
    assert "isExternal" in page
    assert "/chat/" in page
