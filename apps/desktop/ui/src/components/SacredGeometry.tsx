/** SacredGeometry — the living Flower of Life in the void.
 *
 * Ported from the muse cockpit (C:\Users\Echer\Downloads\muse_Cockpit_page.html).
 * One canvas, self-contained: conic-gradient rim, rotating polyhedral lattice,
 * Flower of Life centers, breathing core. No external deps.
 */
import { useEffect, useRef, useMemo } from "react";
import "./SacredGeometry.css";

export interface SacredGeometryProps {
  /** Canvas width in CSS pixels. Default 520. */
  width?: number;
  /** Canvas height in CSS pixels. Default 480. */
  height?: number;
  /** Optional className for the canvas wrapper. */
  className?: string;
  /** If true, pause the animation. */
  paused?: boolean;
}

const PALETTE = ["#7ae0ff", "#b388ff", "#5b8cff"] as const;
const POLY = (ctx: CanvasRenderingContext2D, sides: number, rad: number, rot: number) => {
  ctx.beginPath();
  for (let i = 0; i < sides; i++) {
    const a = rot + (i / sides) * Math.PI * 2 - Math.PI / 2;
    const x = Math.cos(a) * rad;
    const y = Math.sin(a) * rad;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.closePath();
};

export function SacredGeometry({
  width = 520,
  height = 480,
  className = "",
  paused = false,
}: SacredGeometryProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);
  const t0Ref = useRef<number>(performance.now());

  // Pre-compute Flower of Life centers (cached)
  const centers = useMemo(() => {
    const c: number[][] = [[0, 0]];
    for (let ring = 1; ring <= 2; ring++) {
      const count = ring * 6;
      for (let i = 0; i < count; i++) {
        const a = (i / count) * Math.PI * 2 - Math.PI / 2;
        c.push([Math.cos(a) * ring, Math.sin(a) * ring]);
      }
    }
    return c;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true, desynchronized: true }) as
      | CanvasRenderingContext2D
      | null;
    if (!ctx) return;

    let alive = true;
    let dpr = 1;

    const hasConic = typeof ctx.createConicGradient === "function";

    const resize = () => {
      if (!canvas) return;
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const frame = (now: number) => {
      if (!alive || paused) {
        rafRef.current = requestAnimationFrame(frame);
        return;
      }

      const t = (now - t0Ref.current) / 1000;
      const cx = width * 0.6;
      const cy = height * 0.46;
      const m = Math.min(width, height);

      // Clear
      ctx.clearRect(0, 0, width, height);

      // ---- Conic gradient rim (the spectral ring) ----
      const rimGrad = hasConic
        ? (ctx as CanvasRenderingContext2D & { createConicGradient: (a: number, x: number, y: number) => CanvasGradient }).createConicGradient(t * 2, cx, cy)
        : ctx.createLinearGradient(-m, 0, m, 0);
      if (rimGrad.addColorStop) {
        rimGrad.addColorStop(0, PALETTE[0]);
        rimGrad.addColorStop(1 / 3, PALETTE[1]);
        rimGrad.addColorStop(2 / 3, PALETTE[2]);
        rimGrad.addColorStop(1, PALETTE[0]);
      }

      // Outer hexagonal lattice (breathing)
      const r0 = t * 0.04;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(r0 * 0.6);

      // Lattice of hexagons
      const cell = m * 0.072;
      ctx.strokeStyle = rimGrad;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.08;

      // Flower of Life circles
      ctx.strokeStyle = "#7ae0ff";
      ctx.lineWidth = 0.5;
      ctx.globalAlpha = 0.15;

      const rCircle = cell * 0.9;
      for (const [x, y] of centers) {
        ctx.beginPath();
        ctx.arc(x * cell, y * cell, rCircle, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Rotating polyhedra (triangle, square, pentagon)
      const polyRad = m * 0.22;
      const polyGrad = hasConic
        ? (ctx as CanvasRenderingContext2D & { createConicGradient: (a: number, x: number, y: number) => CanvasGradient }).createConicGradient(t * 2, cx, cy)
        : ctx.createLinearGradient(-polyRad, 0, polyRad, 0);
      if (polyGrad.addColorStop) {
        polyGrad.addColorStop(0, PALETTE[0]);
        polyGrad.addColorStop(0.33, PALETTE[1]);
        polyGrad.addColorStop(0.66, PALETTE[2]);
        polyGrad.addColorStop(1, PALETTE[0]);
      }
      ctx.strokeStyle = polyGrad;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.35;

      POLY(ctx, 3, polyRad, r0 * 1.2);
      ctx.stroke();
      POLY(ctx, 4, polyRad * 0.68, -r0 * 0.8);
      ctx.stroke();
      POLY(ctx, 5, polyRad * 0.42, r0 * 0.5);
      ctx.stroke();

      // Central core — the white point
      ctx.beginPath();
      ctx.arc(0, 0, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.globalAlpha = 1;
      ctx.fill();

      // Soft glow behind core
      const coreGlow = ctx.createRadialGradient(0, 0, 0, 0, 0, m * 0.18);
      coreGlow.addColorStop(0, "rgba(122,224,255,0.25)");
      coreGlow.addColorStop(0.5, "rgba(179,136,255,0.10)");
      coreGlow.addColorStop(1, "rgba(91,140,255,0)");
      ctx.fillStyle = coreGlow;
      ctx.beginPath();
      ctx.arc(0, 0, m * 0.18, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();

      rafRef.current = requestAnimationFrame(frame);
    };

    rafRef.current = requestAnimationFrame(frame);

    return () => {
      alive = false;
      window.removeEventListener("resize", resize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [width, height, paused, centers]);

  // Layout belongs to the stylesheet: the wrapper is a fixed, full-viewport,
  // pointer-transparent layer BEHIND the app shell (.sacred-geometry — see
  // SacredGeometry.css / app.css). No inline position/size here: an inline
  // `position: relative` would put the wrapper back into normal flow and
  // shove the whole app shell down by the canvas height.
  return (
    <div className={`sacred-geometry ${className}`} aria-hidden="true">
      <canvas ref={canvasRef} width={width} height={height} />
    </div>
  );
}

export default SacredGeometry;