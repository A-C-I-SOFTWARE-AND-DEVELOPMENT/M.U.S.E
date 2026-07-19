import { useEffect, useState } from "react";
import type { CSSProperties, JSX } from "react";

/**
 * M.U.S.E. boot splash — a one-shot "instrument powering on" overlay shown
 * on dashboard load.
 *
 * Sequence (~1.45s, pure CSS on transform/opacity/filter, no JS rAF):
 *
 *    0–560ms   the sigil draws itself: faint bezel ring + dial ticks fade
 *              in, a thin --accent arc sweeps the full circle (SVG
 *              stroke-dashoffset), a single sonar "power-on ping" expands
 *              from the center dot
 *  260–995ms   the M.U.S.E. wordmark materializes glyph by glyph (blur →
 *              sharp, 6px rise, 45ms stagger); the period separators render
 *              in --accent
 *  160–1040ms  one scanline sweeps the viewport while five dust motes
 *              drift upward and burn out
 *  720ms+      a mono status caption ("observatory online") settles in
 * 1050–1450ms  the overlay dissolves (opacity → 0, content settles to
 *              scale 1.02 + slight blur), then the component unmounts
 *
 * Hard gates: prefers-reduced-motion skips straight to content (the splash
 * never renders), and a sessionStorage flag caps it at one run per browser
 * session. pointer-events drops to none the moment the dissolve begins and
 * the node leaves the DOM entirely when done — it can never trap
 * interaction. No spinner, no progress bar, no generic fade-in-up: an
 * instrument waking up.
 */

const SESSION_KEY = "muse.boot-splash.seen";
const DISSOLVE_AT_MS = 1050;
const DONE_AT_MS = 1450;

/** Wordmark glyphs; the period separators render in --accent. */
const GLYPHS: ReadonlyArray<{ ch: string; accent: boolean }> = [
  { ch: "M", accent: false },
  { ch: ".", accent: true },
  { ch: "U", accent: false },
  { ch: ".", accent: true },
  { ch: "S", accent: false },
  { ch: ".", accent: true },
  { ch: "E", accent: false },
  { ch: ".", accent: true },
];

/** Dust motes riding the power-on thermal. */
const MOTES: ReadonlyArray<{
  left: string;
  bottom: string;
  size: number;
  x: string;
  ms: number;
  delay: number;
  accent: boolean;
}> = [
  { left: "31%", bottom: "30%", size: 2, x: "-12px", ms: 1250, delay: 60, accent: true },
  { left: "44%", bottom: "24%", size: 3, x: "9px", ms: 1400, delay: 220, accent: false },
  { left: "58%", bottom: "28%", size: 2, x: "14px", ms: 1150, delay: 140, accent: true },
  { left: "67%", bottom: "34%", size: 2, x: "-8px", ms: 1350, delay: 320, accent: false },
  { left: "50%", bottom: "20%", size: 3, x: "-16px", ms: 1200, delay: 420, accent: true },
];

/* Scoped keyframes, injected once with the overlay. All durations route
   through the Observatory motion tokens (--ease-motion / --ease-smooth). */
const BOOT_CSS = `
@keyframes muse-boot-fade{from{opacity:0}}
@keyframes muse-boot-ring-draw{to{stroke-dashoffset:0}}
@keyframes muse-boot-ping{from{opacity:.5;transform:scale(.2)}to{opacity:0;transform:scale(1)}}
@keyframes muse-boot-glyph{from{opacity:0;transform:translateY(6px) scale(.94);filter:blur(7px)}55%{opacity:1}to{opacity:1;transform:none;filter:blur(0)}}
@keyframes muse-boot-scan{from{top:-12%;opacity:0}10%{opacity:.45}90%{opacity:.45}to{top:112%;opacity:0}}
@keyframes muse-boot-mote{from{transform:translate3d(0,7vh,0);opacity:0}30%{opacity:.5}to{transform:translate3d(var(--mote-x,10px),-13vh,0);opacity:0}}
@keyframes muse-boot-caption{from{opacity:0;letter-spacing:.34em}to{opacity:.5;letter-spacing:.2em}}
@keyframes muse-boot-dissolve{from{opacity:1}to{opacity:0}}
@keyframes muse-boot-settle{from{transform:scale(1);filter:blur(0)}to{transform:scale(1.02);filter:blur(3px)}}
`;

/** Once per session, and never for reduced-motion users. */
function shouldPlay(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return false;
  }
  try {
    return window.sessionStorage.getItem(SESSION_KEY) !== "1";
  } catch {
    // Storage blocked (private mode etc.) — still allow the visual run.
    return true;
  }
}

export function BootSplash(): JSX.Element | null {
  // Lazy initializer: decided synchronously on first render so the overlay
  // is part of the very first paint (no dashboard flash beneath it).
  const [playing] = useState(shouldPlay);
  const [dissolving, setDissolving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!playing) return;
    try {
      window.sessionStorage.setItem(SESSION_KEY, "1");
    } catch {
      /* non-fatal — worst case the splash replays next session */
    }
    const dissolveTimer = window.setTimeout(
      () => setDissolving(true),
      DISSOLVE_AT_MS,
    );
    const doneTimer = window.setTimeout(() => setDone(true), DONE_AT_MS);
    return () => {
      window.clearTimeout(dissolveTimer);
      window.clearTimeout(doneTimer);
    };
  }, [playing]);

  if (!playing || done) return null;

  return (
    <div
      aria-hidden
      style={{
        position: "fixed",
        inset: 0,
        // Above every page layer (Backdrop z≤101, header z-40), just under
        // the cursor trail/ring (9998/9999) so the custom cursor floats
        // over the boot sequence.
        zIndex: 9990,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(ellipse 62% 52% at 50% 46%, color-mix(in srgb, var(--accent) 5%, var(--bg)) 0%, var(--bg) 72%)",
        pointerEvents: dissolving ? "none" : "auto",
        animation: dissolving
          ? "muse-boot-dissolve 400ms var(--ease-motion) both"
          : undefined,
      }}
    >
      <style>{BOOT_CSS}</style>

      {/* Single scanline sweep. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          height: 1,
          background:
            "linear-gradient(90deg, transparent, color-mix(in srgb, var(--accent) 38%, transparent), transparent)",
          animation: "muse-boot-scan 880ms linear 160ms both",
        }}
      />

      {/* Dust motes. */}
      {MOTES.map((m, i) => (
        <span
          key={i}
          style={
            {
              position: "absolute",
              left: m.left,
              bottom: m.bottom,
              width: m.size,
              height: m.size,
              borderRadius: "50%",
              backgroundColor: m.accent ? "var(--accent)" : "var(--fg-dim)",
              animation: `muse-boot-mote ${m.ms}ms var(--ease-smooth) ${m.delay}ms both`,
              "--mote-x": m.x,
            } as CSSProperties
          }
        />
      ))}

      {/* Sigil + wordmark + caption. */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          animation: dissolving
            ? "muse-boot-settle 400ms var(--ease-motion) both"
            : undefined,
        }}
      >
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none">
          {/* Bezel ring. */}
          <circle
            cx="60"
            cy="60"
            r="56"
            stroke="var(--fg-faint)"
            strokeOpacity="0.4"
            strokeWidth="1"
            style={{ animation: "muse-boot-fade 240ms ease-out both" }}
          />
          {/* Dial ticks. */}
          {[0, 90, 180, 270].map((deg) => (
            <line
              key={deg}
              x1="60"
              y1="4"
              x2="60"
              y2="9"
              stroke="var(--fg-dim)"
              strokeWidth="1"
              transform={`rotate(${deg} 60 60)`}
              style={{ animation: "muse-boot-fade 200ms ease-out 390ms both" }}
            />
          ))}
          {/* Power arc — draws clockwise from 12 o'clock. */}
          <circle
            cx="60"
            cy="60"
            r="48"
            stroke="var(--accent)"
            strokeWidth="1.5"
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
            style={{
              strokeDasharray: 302,
              strokeDashoffset: 302,
              animation: "muse-boot-ring-draw 560ms var(--ease-motion) 90ms both",
            }}
          />
          {/* Center dot + one-shot power-on ping. */}
          <circle
            cx="60"
            cy="60"
            r="2.5"
            fill="var(--accent)"
            style={{ animation: "muse-boot-fade 200ms ease-out 300ms both" }}
          />
          <circle
            cx="60"
            cy="60"
            r="26"
            stroke="var(--accent)"
            strokeWidth="1"
            style={{
              transformBox: "fill-box",
              transformOrigin: "center",
              animation: "muse-boot-ping 720ms var(--ease-smooth) 310ms both",
            }}
          />
        </svg>

        <div
          style={{
            marginTop: 20,
            fontFamily: "var(--theme-font-display)",
            fontWeight: 700,
            fontSize: "clamp(2.1rem, 5.5vw, 3.2rem)",
            lineHeight: 1,
            letterSpacing: "0.04em",
            color: "var(--fg)",
          }}
        >
          {GLYPHS.map((g, i) => (
            <span
              key={i}
              style={{
                display: "inline-block",
                color: g.accent ? "var(--accent)" : undefined,
                animation: `muse-boot-glyph 420ms var(--ease-motion) ${
                  260 + i * 45
                }ms both`,
                willChange: "transform, filter",
              }}
            >
              {g.ch}
            </span>
          ))}
        </div>

        <div
          style={{
            marginTop: 16,
            fontFamily: "var(--theme-font-mono)",
            fontSize: "0.6875rem",
            letterSpacing: "0.2em",
            color: "var(--fg-dim)",
            animation: "muse-boot-caption 340ms var(--ease-motion) 720ms both",
          }}
        >
          observatory online
        </div>
      </div>
    </div>
  );
}
