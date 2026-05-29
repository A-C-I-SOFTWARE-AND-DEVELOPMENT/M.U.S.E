"""Tests for hermes_cli.jarvis_prime.avatar — the canonical JARVIS Prime
avatar + locale-aware voice embodiment, and its CLI surface.

Hermetic: stdlib only, no audio deps, no network.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from hermes_cli.jarvis_prime import avatar as av

_CANONICAL_JSON = (
    Path(__file__).resolve().parent.parent / "docs" / "jarvis-prime" / "avatar.json"
)


# ---------------------------------------------------------------------------
# Identity + brand fidelity (must match the Android app verbatim)
# ---------------------------------------------------------------------------


def test_default_identity() -> None:
    a = av.DEFAULT_AVATAR
    assert a.name == "JARVIS Prime"
    assert a.short_name == "Jarvis"
    assert a.tagline == "Your command-center agent."
    assert "watchful eye" in a.glyph


def test_palette_matches_android_brand() -> None:
    p = av.DEFAULT_AVATAR.palette
    # Lifted verbatim from apps/android/.../ui/theme/Color.kt.
    assert p.gold == "#E6B341"
    assert p.cyan == "#38C6E0"
    assert p.ink == "#05070D"
    assert p.signal == "#E7ECF7"


def test_is_multilingual() -> None:
    locales = av.DEFAULT_AVATAR.locales()
    assert "en-US" in locales
    # Matches the project's localized READMEs / Android i18n.
    for loc in ("es-ES", "fr-FR", "ja-JP", "zh-CN", "ko-KR"):
        assert loc in locales


# ---------------------------------------------------------------------------
# Locale-aware voice resolution
# ---------------------------------------------------------------------------


def test_voice_for_exact_match() -> None:
    v = av.DEFAULT_AVATAR.voice_for("fr-FR")
    assert v.locale == "fr-FR"
    assert v.language_name == "Français"


def test_voice_for_language_prefix_fallback() -> None:
    # "fr" should resolve to the fr-FR profile.
    assert av.DEFAULT_AVATAR.voice_for("fr").locale == "fr-FR"


def test_voice_for_unknown_falls_back_to_default_locale() -> None:
    a = av.DEFAULT_AVATAR
    assert a.voice_for("pt-BR").locale == a.default_locale == "en-US"


def test_voice_for_none_uses_default() -> None:
    assert av.DEFAULT_AVATAR.voice_for(None).locale == "en-US"


def test_greeting_is_localized() -> None:
    a = av.DEFAULT_AVATAR
    assert a.greeting("en-US") == "Ready when you are."
    assert a.greeting("es-ES") == "Listo cuando tú lo estés."


def test_voice_for_raises_without_voices() -> None:
    bare = av.JarvisAvatar(voices=())
    try:
        bare.voice_for("en-US")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError when no voices are configured")


# ---------------------------------------------------------------------------
# Local voice stack (OpenHuman-inspired local-first defaults)
# ---------------------------------------------------------------------------


def test_local_voice_stack_defaults() -> None:
    lv = av.DEFAULT_AVATAR.local_voice
    assert lv.stt_engine == "faster-whisper"  # matches hermes_cli/voice.py
    assert lv.tts_engine == "piper"
    assert lv.offline_first is True
    assert lv.wake_phrase == "Jarvis"


# ---------------------------------------------------------------------------
# Serialisation + canonical JSON sync
# ---------------------------------------------------------------------------


def test_json_round_trip() -> None:
    a = av.DEFAULT_AVATAR
    rebuilt = av.JarvisAvatar.from_dict(json.loads(a.to_json()))
    assert rebuilt.to_dict() == a.to_dict()


def test_canonical_json_in_sync_with_python_defaults() -> None:
    # The committed JSON the Android cockpit reads must match the Python
    # source of truth. Regenerate with the avatar module if this fails.
    assert _CANONICAL_JSON.is_file(), f"missing canonical export: {_CANONICAL_JSON}"
    on_disk = json.loads(_CANONICAL_JSON.read_text(encoding="utf-8"))
    assert on_disk == av.DEFAULT_AVATAR.to_dict()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_avatar_json() -> None:
    from hermes_cli.jarvis_prime.__main__ import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["avatar", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["name"] == "JARVIS Prime"
    assert payload["palette"]["gold"] == "#E6B341"


def test_cli_avatar_locale_json_returns_one_profile() -> None:
    from hermes_cli.jarvis_prime.__main__ import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["avatar", "--locale", "ja-JP", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["locale"] == "ja-JP"
    assert payload["language_name"] == "日本語"


def test_cli_avatar_human_readable() -> None:
    from hermes_cli.jarvis_prime.__main__ import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["avatar"])
    assert rc == 0
    out = buf.getvalue()
    assert "JARVIS Prime" in out
    assert "Local voice stack" in out
