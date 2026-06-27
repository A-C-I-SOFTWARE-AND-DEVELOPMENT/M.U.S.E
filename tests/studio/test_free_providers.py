"""Tests for the free image/voice adapters (Pollinations + edge-tts).

Network-free: probes are monkey-patched. A live smoke run exists separately.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.studio.adapters import free_providers
from agent.studio.adapters.base import default_registry
from agent.studio.types import Provider


@pytest.fixture(autouse=True)
def _clear_caches():
    for fn in (free_providers._pollinations_available,):
        if hasattr(fn, "_cache"):
            delattr(fn, "_cache")
    yield


def test_pollinations_stubs_when_offline(tmp_path: Path):
    with patch.object(free_providers, "_pollinations_available", return_value=False):
        ad = free_providers.PollinationsImageAdapter()
        assert ad.available() is False
        r = ad.run("a robot on mars", tmp_path)
        assert r.status == "stubbed"


def test_pollinations_writes_png_when_online(tmp_path: Path):
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    fake_resp = MagicMock()
    fake_resp.read.return_value = fake_png
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda *a: None
    with patch.object(free_providers, "_pollinations_available", return_value=True), \
         patch("agent.studio.adapters.free_providers.urllib.request.urlopen",
               return_value=fake_resp):
        ad = free_providers.PollinationsImageAdapter()
        r = ad.run("a robot on mars", tmp_path, width=512, height=512, seed=42)
        assert r.status == "ok"
        out = Path(r.artifacts[0])
        assert out.exists()
        assert out.read_bytes().startswith(b"\x89PNG")
        assert "seed=42" in r.notes


def test_edge_tts_picks_voice_from_role(tmp_path: Path):
    assert free_providers._pick_voice("Greeting for Hero NPC", {}) \
        == free_providers.EDGE_VOICE_BY_ROLE["hero"]
    assert free_providers._pick_voice("Line for villain", {}) \
        == free_providers.EDGE_VOICE_BY_ROLE["villain"]
    assert free_providers._pick_voice("random text", {"voice": "en-US-AvaNeural"}) \
        == "en-US-AvaNeural"
    assert free_providers._pick_voice("nothing matched", {}) \
        == free_providers.EDGE_VOICE_BY_ROLE["default"]


def test_edge_tts_writes_mp3_when_available(tmp_path: Path):
    # Mock the edge_tts.Communicate class so no network call is made
    saved = {}
    class FakeCommunicate:
        def __init__(self, text, voice, rate="+0%"):
            saved["text"] = text
            saved["voice"] = voice
        async def save(self, path):
            Path(path).write_bytes(b"ID3" + b"\x00" * 32)  # minimal MP3 header
    with patch.object(free_providers, "_edge_tts_available", return_value=True), \
         patch.dict("sys.modules", {}):
        import sys
        fake_mod = MagicMock()
        fake_mod.Communicate = FakeCommunicate
        sys.modules["edge_tts"] = fake_mod
        try:
            ad = free_providers.EdgeTTSVoiceAdapter()
            r = ad.run("Greeting line for Hero NPC.", tmp_path,
                       text="Hold the line, brothers!")
            assert r.status == "ok"
            out = Path(r.artifacts[0])
            assert out.suffix == ".mp3"
            assert out.read_bytes().startswith(b"ID3")
            assert saved["text"] == "Hold the line, brothers!"
            assert saved["voice"] == free_providers.EDGE_VOICE_BY_ROLE["hero"]
        finally:
            sys.modules.pop("edge_tts", None)


def test_registry_picks_free_image_over_stub_when_online():
    with patch.object(free_providers, "_pollinations_available", return_value=True):
        picked = default_registry.pick("concept_art")
        # Picked is the Pollinations adapter (priority 70 with available=True)
        assert isinstance(picked, free_providers.PollinationsImageAdapter)


def test_registry_picks_edge_tts_over_stub_when_available():
    with patch.object(free_providers, "_edge_tts_available", return_value=True):
        picked = default_registry.pick("voice")
        assert isinstance(picked, free_providers.EdgeTTSVoiceAdapter)
