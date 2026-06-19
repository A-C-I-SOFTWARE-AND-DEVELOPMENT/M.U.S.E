# muse — Avatar & Voice Embodiment

> One canonical definition of *who muse is* as an embodied presence —
> brand glyph, palette, tagline, and a **locale-aware voice** + local-first
> voice stack — shared by the CLI, gateway, Termux runtime, and the Android
> cockpit.

- **Source of truth:** [`hermes_cli/jarvis_prime/avatar.py`](../../hermes_cli/jarvis_prime/avatar.py)
  (stdlib-only, JSON-serializable — same sharing contract as `voice_models.py`).
- **Canonical export:** [`avatar.json`](./avatar.json) — generated from the Python
  defaults; `tests/test_jarvis_prime_avatar.py` keeps the two in sync.

```text
python -m hermes_cli.jarvis_prime avatar                # full embodiment
python -m hermes_cli.jarvis_prime avatar --locale ja-JP # one locale's voice
python -m hermes_cli.jarvis_prime avatar --json         # machine-readable
```

---

## Identity (mirrors the Android app verbatim)

| Field | Value | Sourced from |
|---|---|---|
| Name | **muse** | `res/values/strings.xml` (`app_name`) |
| Tagline | *Your command-center agent.* | `strings.xml` (`app_tagline`) |
| Glyph | Two concentric rings — gold outer, cyan inner — around a luminous gold **prime dot**: the watchful eye | `ui/components/JarvisPrimeIcon.kt` |
| Gold (brand) | `#E6B341` | `ui/theme/Color.kt` (`JarvisGold`) |
| Cyan (accent) | `#38C6E0` | `JarvisCyan` |
| Ink (bg) | `#05070D` | `JarvisInkAbyss` |
| Signal (text) | `#E7ECF7` | `JarvisSignal` |

The Android cockpit is **already** branded muse end to end (launcher
icon, `JarvisPrimeIcon`, `JarvisStatusHeader`, `JarvisShell`, theme tokens).
This module makes that identity a portable artifact so the CLI and any future
surface render the *same* muse instead of drifting.

---

## Locale-aware voice

Each locale carries a Piper voice id, a greeting, and a listening prompt.
Resolution falls back gracefully: **exact locale → language prefix
(`fr` ↔ `fr-FR`) → `default_locale` (`en-US`) → first configured voice**.

| Locale | Language | Greeting | Piper voice |
|---|---|---|---|
| en-US | English | Ready when you are. | `en_US-amy-medium` |
| es-ES | Español | Listo cuando tú lo estés. | `es_ES-davefx-medium` |
| fr-FR | Français | Prêt quand vous l'êtes. | `fr_FR-siwis-medium` |
| ja-JP | 日本語 | 準備はいつでも。 | `ja_JP-test-medium` |
| zh-CN | 简体中文 | 随时待命。 | `zh_CN-huayan-medium` |
| ko-KR | 한국어 | 언제든 준비됐어요. | `ko_KR-glow-medium` |

Greetings/prompts match the tone of the existing Android voice strings
("Ready when you are." / "I'm listening.").

---

## Local-first voice stack

`LocalVoiceStack` declares the on-device default muse prefers when offline.
It is **declarative** — the runtime in
[`hermes_cli/voice.py`](../../hermes_cli/voice.py) maps it to whatever STT/TTS
backend is installed; the cloud path still works via the existing voice
providers.

| Field | Default | Notes |
|---|---|---|
| `stt_engine` | `faster-whisper` | already what `voice.py` uses |
| `stt_model` | `base` | `tiny`…`large-v3` |
| `stt_compute` | `int8` | quantized for CPU/edge |
| `tts_engine` | `piper` | offline neural TTS |
| `offline_first` | `true` | prefer local; no audio leaves device |
| `wake_phrase` | `muse` | for opt-in wake-word capture |
| `vad` | `true` | voice-activity auto-stop |

---

## Adding or changing a locale

1. Add a `VoiceProfile` to `_DEFAULT_VOICES` in `avatar.py` (or override at
   runtime via `JarvisAvatar.from_dict(...)`).
2. Regenerate the canonical export:
   ```python
   from hermes_cli.jarvis_prime.avatar import DEFAULT_AVATAR
   import pathlib
   pathlib.Path("docs/jarvis-prime/avatar.json").write_text(
       DEFAULT_AVATAR.to_json() + "\n", encoding="utf-8")
   ```
3. `pytest tests/test_jarvis_prime_avatar.py` — the sync guard will confirm
   the JSON matches the Python source of truth.

---

## Credits

The **locale-aware voice + multilingual reply** model and the **local-first**
voice stack are concepts inspired by **OpenHuman**
(https://github.com/tinyhumansai/openhuman, by the tinyhumans.ai team,
GPL-3.0). This module is **original, MIT-licensed** work — **no OpenHuman code
was copied** (it is GPL-3.0 Rust/Tauri). Concept credit to the OpenHuman authors.
