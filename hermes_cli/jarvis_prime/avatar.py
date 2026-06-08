"""MUSE — canonical avatar + locale-aware voice embodiment.

Stdlib-only, JSON-serialisable single source of truth for *who JARVIS is*
as an embodied presence: name, brand glyph, palette, tagline, and a
locale-aware voice profile plus a local-first voice stack (Whisper STT +
Piper TTS).

Same sharing contract as ``voice_models.py``: no audio/runtime deps, pure
dataclasses, so the CLI, gateway, Termux runtime, and the Android cockpit
(``apps/android``) can all read one definition. The canonical export lives
at ``docs/jarvis-prime/avatar.json``; ``tests/test_jarvis_prime_avatar.py``
asserts the Python defaults and that JSON stay in sync.

The brand identity is the canonical "Singularity" look — one luminous
white core in the void, circled by a single thin spectral ring (cyan →
violet). The reference palette is the browser cockpit's
``gateway/cockpit/static/tokens.css``; the Android theme and this module
mirror it so there is **one** MUSE, not two:

* palette ← ``gateway/cockpit/static/tokens.css`` (Singularity tokens),
  mirrored into ``apps/android/.../ui/theme/Color.kt``
* glyph ← the single white core + spectral ring (cyan→violet)
* tagline / voice prompts ← ``apps/android/.../res/values/strings.xml``

Locale-aware voice + multilingual replies are a concept inspired by
**OpenHuman** (github.com/tinyhumansai/openhuman, GPL-3.0). No code was
copied — this is original MIT work. Concept credit to the OpenHuman team.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "BrandPalette",
    "VoiceProfile",
    "LocalVoiceStack",
    "JarvisAvatar",
    "DEFAULT_AVATAR",
    "default_avatar",
]


# ---------------------------------------------------------------------------
# Brand palette — the canonical "Singularity" palette, lifted from the
# browser cockpit's tokens (gateway/cockpit/static/tokens.css) so the
# CLI/avatar, the cockpit, and the Android app render the same MUSE.
#
# Field NAMES are kept for back-compat; their VALUES now carry Singularity
# semantics: ``gold`` is the white core (primary accent), ``cyan`` is the
# spectral ring, ``crimson``/``jade`` map to danger/ok.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrandPalette:
    ink: str = "#050507"  # --void — background / the dark
    surface: str = "#12151D"  # --void-3 — cards
    signal: str = "#E8ECF4"  # --signal — primary text
    gold: str = "#FFFFFF"  # --core — the white core / primary accent
    cyan: str = "#7AE0FF"  # --ring-1 — spectral ring (cyan end)
    crimson: str = "#FF5C63"  # --danger — destructive / emergency stop
    jade: str = "#5BE3A0"  # --ok — success / online

    def to_dict(self) -> dict[str, str]:
        return {
            "ink": self.ink,
            "surface": self.surface,
            "signal": self.signal,
            "gold": self.gold,
            "cyan": self.cyan,
            "crimson": self.crimson,
            "jade": self.jade,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BrandPalette":
        d = raw or {}
        return cls(
            ink=str(d.get("ink", cls.ink)),
            surface=str(d.get("surface", cls.surface)),
            signal=str(d.get("signal", cls.signal)),
            gold=str(d.get("gold", cls.gold)),
            cyan=str(d.get("cyan", cls.cyan)),
            crimson=str(d.get("crimson", cls.crimson)),
            jade=str(d.get("jade", cls.jade)),
        )


# ---------------------------------------------------------------------------
# Per-locale voice profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceProfile:
    """How JARVIS speaks and is greeted in one locale.

    ``tts_voice`` is an engine-agnostic voice id (Piper voices follow the
    ``<lang>_<REGION>-<name>-<quality>`` convention). The fields are
    advisory: the runtime in ``hermes_cli/voice.py`` maps them to whatever
    STT/TTS backend is installed; this module only describes the contract.
    """

    locale: str
    language_name: str
    tts_voice: str
    greeting: str
    listening_prompt: str = "I'm listening."
    speaking_rate: float = 1.0
    pitch: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "locale": self.locale,
            "language_name": self.language_name,
            "tts_voice": self.tts_voice,
            "greeting": self.greeting,
            "listening_prompt": self.listening_prompt,
            "speaking_rate": self.speaking_rate,
            "pitch": self.pitch,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "VoiceProfile":
        return cls(
            locale=str(raw["locale"]),
            language_name=str(raw.get("language_name", "")),
            tts_voice=str(raw.get("tts_voice", "")),
            greeting=str(raw.get("greeting", "")),
            listening_prompt=str(raw.get("listening_prompt", "I'm listening.")),
            speaking_rate=float(raw.get("speaking_rate", 1.0)),
            pitch=float(raw.get("pitch", 0.0)),
        )


# ---------------------------------------------------------------------------
# Local-first voice stack — concept-ported from OpenHuman's local AI/voice
# config (Ollama-admin + Whisper install + local speech). Declarative only.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalVoiceStack:
    """Local-first STT/TTS configuration JARVIS prefers when offline.

    Defaults favour on-device privacy: faster-whisper for STT (which the
    runtime in ``voice.py`` already uses) and Piper for TTS, both runnable
    without a network round-trip. The cloud path remains available via the
    existing voice providers; this just declares the local default.
    """

    stt_engine: str = "faster-whisper"
    stt_model: str = "base"  # tiny|base|small|medium|large-v3
    stt_compute: str = "int8"  # int8|int8_float16|float16|float32
    tts_engine: str = "piper"
    sample_rate_hz: int = 22050
    offline_first: bool = True
    wake_phrase: str = "Muse"
    vad: bool = True  # voice-activity-detection auto-stop

    def to_dict(self) -> dict[str, Any]:
        return {
            "stt_engine": self.stt_engine,
            "stt_model": self.stt_model,
            "stt_compute": self.stt_compute,
            "tts_engine": self.tts_engine,
            "sample_rate_hz": self.sample_rate_hz,
            "offline_first": self.offline_first,
            "wake_phrase": self.wake_phrase,
            "vad": self.vad,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LocalVoiceStack":
        d = raw or {}
        return cls(
            stt_engine=str(d.get("stt_engine", cls.stt_engine)),
            stt_model=str(d.get("stt_model", cls.stt_model)),
            stt_compute=str(d.get("stt_compute", cls.stt_compute)),
            tts_engine=str(d.get("tts_engine", cls.tts_engine)),
            sample_rate_hz=int(d.get("sample_rate_hz", cls.sample_rate_hz)),
            offline_first=bool(d.get("offline_first", cls.offline_first)),
            wake_phrase=str(d.get("wake_phrase", cls.wake_phrase)),
            vad=bool(d.get("vad", cls.vad)),
        )


# ---------------------------------------------------------------------------
# The avatar
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JarvisAvatar:
    """The embodied identity of MUSE — Multi-Use Synaptic Entity.

    One mind (MUSE) over a synaptic substrate (the gateway, routing, and
    model pathways). ``name`` is the body form ("MUSE"); ``display`` is the
    stylized acronym ("M.U.S.E."); ``full_name`` is the expansion.
    """

    name: str = "MUSE"
    full_name: str = "Multi-Use Synaptic Entity"
    display: str = "M.U.S.E."
    short_name: str = "MUSE"
    tagline: str = "One mind, many pathways."
    glyph: str = (
        "A single luminous white core in the void, circled by one thin "
        "spectral ring (cyan→violet)."
    )
    palette: BrandPalette = field(default_factory=BrandPalette)
    default_locale: str = "en-US"
    voices: tuple[VoiceProfile, ...] = ()
    local_voice: LocalVoiceStack = field(default_factory=LocalVoiceStack)
    persona_spec: str = "docs/jarvis-prime-operating-system.md"

    # -- locale resolution -------------------------------------------------
    def locales(self) -> list[str]:
        return [v.locale for v in self.voices]

    def voice_for(self, locale: Optional[str] = None) -> VoiceProfile:
        """Resolve a VoiceProfile for ``locale`` with graceful fallback.

        Order: exact locale → same language prefix (``en`` ↔ ``en-US``) →
        ``default_locale`` → first configured voice. Always returns a
        profile as long as at least one voice is configured.
        """
        if not self.voices:
            raise ValueError("avatar has no configured voices")
        want = (locale or self.default_locale or "").strip()
        if want:
            for v in self.voices:  # exact
                if v.locale.lower() == want.lower():
                    return v
            lang = want.split("-", 1)[0].lower()  # language prefix
            for v in self.voices:
                if v.locale.split("-", 1)[0].lower() == lang:
                    return v
        for v in self.voices:  # default_locale
            if v.locale.lower() == (self.default_locale or "").lower():
                return v
        return self.voices[0]

    def greeting(self, locale: Optional[str] = None) -> str:
        return self.voice_for(locale).greeting

    # -- serialisation -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "display": self.display,
            "short_name": self.short_name,
            "tagline": self.tagline,
            "glyph": self.glyph,
            "palette": self.palette.to_dict(),
            "default_locale": self.default_locale,
            "voices": [v.to_dict() for v in self.voices],
            "local_voice": self.local_voice.to_dict(),
            "persona_spec": self.persona_spec,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "JarvisAvatar":
        d = raw or {}
        voices = tuple(
            VoiceProfile.from_dict(v)
            for v in d.get("voices", [])
            if isinstance(v, dict)
        )
        return cls(
            name=str(d.get("name", cls.name)),
            full_name=str(d.get("full_name", cls.full_name)),
            display=str(d.get("display", cls.display)),
            short_name=str(d.get("short_name", cls.short_name)),
            tagline=str(d.get("tagline", cls.tagline)),
            glyph=str(d.get("glyph", cls.glyph)),
            palette=BrandPalette.from_dict(d.get("palette", {})),
            default_locale=str(d.get("default_locale", cls.default_locale)),
            voices=voices,
            local_voice=LocalVoiceStack.from_dict(d.get("local_voice", {})),
            persona_spec=str(d.get("persona_spec", cls.persona_spec)),
        )


# ---------------------------------------------------------------------------
# The canonical default avatar. Multilingual to match the project's own
# localized surfaces (en/es/fr/ja/zh/ko READMEs + Android i18n).
# ---------------------------------------------------------------------------

_DEFAULT_VOICES: tuple[VoiceProfile, ...] = (
    VoiceProfile(
        locale="en-US",
        language_name="English",
        tts_voice="en_US-amy-medium",
        greeting="Ready when you are.",
        listening_prompt="I'm listening.",
    ),
    VoiceProfile(
        locale="es-ES",
        language_name="Español",
        tts_voice="es_ES-davefx-medium",
        greeting="Listo cuando tú lo estés.",
        listening_prompt="Te escucho.",
    ),
    VoiceProfile(
        locale="fr-FR",
        language_name="Français",
        tts_voice="fr_FR-siwis-medium",
        greeting="Prêt quand vous l'êtes.",
        listening_prompt="Je vous écoute.",
    ),
    VoiceProfile(
        locale="ja-JP",
        language_name="日本語",
        tts_voice="ja_JP-test-medium",
        greeting="準備はいつでも。",
        listening_prompt="聞いています。",
    ),
    VoiceProfile(
        locale="zh-CN",
        language_name="简体中文",
        tts_voice="zh_CN-huayan-medium",
        greeting="随时待命。",
        listening_prompt="我在听。",
    ),
    VoiceProfile(
        locale="ko-KR",
        language_name="한국어",
        tts_voice="ko_KR-glow-medium",
        greeting="언제든 준비됐어요.",
        listening_prompt="듣고 있어요.",
    ),
)

DEFAULT_AVATAR = JarvisAvatar(voices=_DEFAULT_VOICES)


def default_avatar() -> JarvisAvatar:
    """Return the canonical MUSE avatar."""
    return DEFAULT_AVATAR
