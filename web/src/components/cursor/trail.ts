/**
 * Fading violet glow trail for the custom cursor (animation-spec §5).
 *
 * Canvas-2D implementation — one full-screen, pointer-events-none canvas
 * hosted by <CursorRing />. At most 12 dots are alive at any moment; each
 * dot is spawned on pointermove (throttled to ~16 ms) and animates opacity
 * + scale out over ~400 ms inside the host's rAF loop, so a moving pointer
 * sits at steady state near the 12-dot cap with zero DOM churn.
 *
 * The accent color is resolved once at construction — repainting it per
 * frame would thrash style resolution, and a theme switch simply applies
 * on the next mount.
 */

const MAX_DOTS = 12;
const LIFE_MS = 400;
const SPAWN_INTERVAL_MS = 16;
const MAX_DPR = 2;
const FALLBACK_ACCENT = "#d8b4fe";

interface TrailDot {
  x: number;
  y: number;
  born: number;
}

export interface CursorTrail {
  /** Queue a dot at client coords; internally throttled to ~16 ms. */
  spawn(x: number, y: number): void;
  /** Advance and paint one frame. Call from the host rAF loop. */
  render(now: number): void;
  /** Remove listeners, drop dots, and clear the canvas. */
  destroy(): void;
}

export function createCursorTrail(canvas: HTMLCanvasElement): CursorTrail {
  const ctx = canvas.getContext("2d");
  const dots: TrailDot[] = [];
  let lastSpawn = -Infinity;
  let dpr = 1;

  const accent =
    getComputedStyle(document.documentElement)
      .getPropertyValue("--accent")
      .trim() || FALLBACK_ACCENT;

  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
  };
  resize();
  window.addEventListener("resize", resize);

  return {
    spawn(x, y) {
      const now = performance.now();
      if (now - lastSpawn < SPAWN_INTERVAL_MS) return;
      lastSpawn = now;
      dots.push({ x, y, born: now });
      if (dots.length > MAX_DOTS) dots.shift();
    },

    render(now) {
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      ctx.fillStyle = accent;
      ctx.shadowColor = accent;
      for (let i = dots.length - 1; i >= 0; i--) {
        const dot = dots[i];
        const age = now - dot.born;
        if (age >= LIFE_MS) {
          // Stale after a background-tab rAF pause too — sweep and move on.
          dots.splice(i, 1);
          continue;
        }
        const k = age / LIFE_MS; // 0 → 1 over the dot's life
        ctx.globalAlpha = 0.45 * (1 - k); // fade out
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(dot.x, dot.y, 2.5 + 3.5 * k, 0, Math.PI * 2); // scale out
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
    },

    destroy() {
      window.removeEventListener("resize", resize);
      dots.length = 0;
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    },
  };
}
