// Voice bridge integration. Uses the browser Web Speech API for STT/TTS and
// posts transcripts to the EXISTING M.U.S.E. voice bridge (Flask + Web Speech)
// — it does not reimplement that bridge, it drives it. Microphone permission is
// requested lazily on first listen (a genuine PWA capability).

import { museBase, authHeaders } from './config';

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: any) => void) | null;
  onerror: ((e: any) => void) | null;
  onend: (() => void) | null;
};

function getRecognition(): SpeechRecognitionLike | null {
  const Ctor =
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

export function sttSupported(): boolean {
  return !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
}

export function ttsSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/** Request microphone permission explicitly (so Settings can surface the state). */
export async function requestMic(): Promise<boolean> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
    return true;
  } catch {
    return false;
  }
}

export interface VoiceSession {
  stop: () => void;
}

/**
 * Start listening. Calls onPartial with interim text and onFinal with the
 * settled transcript, which is also POSTed to the M.U.S.E. voice bridge.
 */
export function startListening(
  onPartial: (text: string) => void,
  onFinal: (text: string) => void,
  onError?: (msg: string) => void,
): VoiceSession | null {
  const rec = getRecognition();
  if (!rec) {
    onError?.('Speech recognition not supported on this device');
    return null;
  }
  rec.lang = 'en-US';
  rec.continuous = false;
  rec.interimResults = true;

  rec.onresult = (e: any) => {
    let interim = '';
    let final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) final += t;
      else interim += t;
    }
    if (interim) onPartial(interim);
    if (final) {
      onFinal(final);
      if (museBase()) {
        fetch(`${museBase()}/api/voice/stt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ transcript: final }),
        }).catch(() => {});
      }
    }
  };
  rec.onerror = (e: any) => onError?.(String(e?.error ?? 'recognition error'));
  try {
    rec.start();
  } catch {
    /* already started */
  }
  return { stop: () => rec.stop() };
}

/** Speak text via the browser TTS (the bridge's playback path). */
export function speak(text: string): void {
  if (!ttsSupported()) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-US';
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}
