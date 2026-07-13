/**
 * Voice service — speech-to-text (browser Web Speech API) and text-to-speech
 * (browser SpeechSynthesis), plus optional gateway voice intake integration.
 *
 * Uses the WebView2's built-in Web Speech API (available in Tauri/Edge) for
 * recognition and synthesis. No external dependencies. Falls back gracefully
 * when the APIs are unavailable.
 */

import { api } from "./gateway";

// ---- Speech-to-text (recognition) ----------------------------------------

function getRecognitionCtor(): any | null {
  if (typeof window === "undefined") return null;
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

export function isSTTSupported(): boolean {
  return getRecognitionCtor() !== null;
}

export type STTCallbacks = {
  onInterim?: (text: string) => void;
  onFinal?: (text: string) => void;
  onError?: (message: string) => void;
  onEnd?: () => void;
};

export class VoiceListener {
  private recognition: any = null;
  private listening = false;

  get isActive(): boolean {
    return this.listening;
  }

  start(lang: string, cb: STTCallbacks): void {
    const Ctor = getRecognitionCtor();
    if (!Ctor) {
      cb.onError?.("Speech recognition not supported in this browser");
      return;
    }
    if (this.listening) return;

    const rec = new Ctor();
    rec.lang = lang || "en-US";
    rec.interimResults = true;
    rec.continuous = false;

    rec.onresult = (event: any) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      if (final) cb.onFinal?.(final.trim());
      else if (interim) cb.onInterim?.(interim.trim());
    };

    rec.onerror = (event: any) => {
      const err = event?.error || "unknown";
      const msgs: Record<string, string> = {
        "no-speech": "No speech detected",
        "audio-capture": "Microphone not accessible",
        "not-allowed": "Microphone permission denied",
        network: "Network error during recognition",
      };
      cb.onError?.(msgs[err] || `Recognition error: ${err}`);
    };

    rec.onend = () => {
      this.listening = false;
      cb.onEnd?.();
    };

    this.recognition = rec;
    this.listening = true;
    try {
      rec.start();
    } catch (e) {
      this.listening = false;
      cb.onError?.("Failed to start recognition");
    }
  }

  stop(): void {
    if (this.recognition && this.listening) {
      try {
        this.recognition.stop();
      } catch {
        /* already stopped */
      }
    }
    this.listening = false;
  }
}

// ---- Text-to-speech (synthesis) -------------------------------------------

export function isTTSSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function getVoices(): SpeechSynthesisVoice[] {
  if (!isTTSSupported()) return [];
  return window.speechSynthesis.getVoices();
}

export type SpeakOptions = {
  voice?: SpeechSynthesisVoice | null;
  rate?: number;   // 0.1 – 10, default 1
  pitch?: number;  // 0 – 2, default 1
  volume?: number; // 0 – 1, default 1
};

export function speak(text: string, opts?: SpeakOptions): void {
  if (!isTTSSupported() || !text.trim()) return;
  window.speechSynthesis.cancel(); // barge-in: interrupt any current speech
  const utter = new SpeechSynthesisUtterance(text);
  if (opts?.voice) utter.voice = opts.voice;
  utter.rate = opts?.rate ?? 1;
  utter.pitch = opts?.pitch ?? 1;
  utter.volume = opts?.volume ?? 1;
  window.speechSynthesis.speak(utter);
}

export function stopSpeaking(): void {
  if (isTTSSupported()) window.speechSynthesis.cancel();
}

export function isSpeaking(): boolean {
  return isTTSSupported() && window.speechSynthesis.speaking;
}

// ---- Voice preferences (persisted in localStorage) ------------------------

const VOICE_PREFS_KEY = "muse.voice.prefs";

export type VoicePrefs = {
  sttLang: string;        // e.g. "en-US"
  ttsEnabled: boolean;    // auto-speak assistant replies
  ttsVoiceURI: string;    // selected voice URI (empty = default)
  ttsRate: number;
  ttsPitch: number;
};

const DEFAULT_PREFS: VoicePrefs = {
  sttLang: "en-US",
  ttsEnabled: false,
  ttsVoiceURI: "",
  ttsRate: 1,
  ttsPitch: 1,
};

export function getVoicePrefs(): VoicePrefs {
  try {
    const raw = localStorage.getItem(VOICE_PREFS_KEY);
    if (!raw) return DEFAULT_PREFS;
    return { ...DEFAULT_PREFS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function setVoicePrefs(prefs: Partial<VoicePrefs>): VoicePrefs {
  const merged = { ...getVoicePrefs(), ...prefs };
  localStorage.setItem(VOICE_PREFS_KEY, JSON.stringify(merged));
  return merged;
}

// ---- Gateway voice intake (optional — uses cockpit endpoints) -------------

/**
 * The gateway has voice intake endpoints at /v1/cockpit/voice/intake/* that
 * accept pre-transcribed text and run it through the full intake pipeline
 * (mode normalization, confirmation, job submission). This is the bridge
 * between the browser-side STT and the backend's voice coaching pipeline.
 */

export async function submitVoiceIntake(
  transcript: string,
  mode?: string,
): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  try {
    const r = await api("/v1/cockpit/voice/intake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript, mode: mode || "normal" }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, error: String(d.error ?? r.status) };
    return { ok: true, jobId: d.job_id };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}
