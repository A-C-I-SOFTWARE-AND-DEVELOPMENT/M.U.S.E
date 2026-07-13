/**
 * SacredGeometry — a resolution-independent, interactive cinematic depth field.
 * Canvas pixels follow the live WebView size and DPR, so the composition remains
 * razor sharp on 4K/8K displays without shipping raster artwork or mock data.
 */
import { useEffect, useRef } from "react";
import "./SacredGeometry.css";

export interface SacredGeometryProps {
  width?: number;
  height?: number;
  className?: string;
  paused?: boolean;
}

type Star = { x: number; y: number; z: number; size: number; phase: number };
const TAU = Math.PI * 2;
const PALETTE = ["#7ae0ff", "#b388ff", "#5b8cff"] as const;

function polygon(ctx: CanvasRenderingContext2D, sides: number, radius: number, rotation: number) {
  ctx.beginPath();
  for (let i = 0; i < sides; i++) {
    const a = rotation + (i / sides) * TAU - Math.PI / 2;
    const x = Math.cos(a) * radius;
    const y = Math.sin(a) * radius;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.closePath();
}

function seededStars(count: number): Star[] {
  let seed = 0x51a7c0de;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0xffffffff;
  };
  return Array.from({ length: count }, () => ({
    x: random(), y: random(), z: 0.18 + random() * 0.82,
    size: 0.35 + random() * 1.15, phase: random() * TAU,
  }));
}

export function SacredGeometry({ className = "", paused = false }: SacredGeometryProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true, desynchronized: true });
    if (!ctx) return;

    const stars = seededStars(190);
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let vw = 1, vh = 1, dpr = 1, raf = 0, alive = true;
    const started = performance.now();

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      vw = Math.max(1, rect.width || window.innerWidth);
      vh = Math.max(1, rect.height || window.innerHeight);
      dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      canvas.width = Math.round(vw * dpr);
      canvas.height = Math.round(vh * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const move = (event: PointerEvent) => {
      pointer.tx = (event.clientX / Math.max(vw, 1) - 0.5) * 2;
      pointer.ty = (event.clientY / Math.max(vh, 1) - 0.5) * 2;
    };
    const leave = () => { pointer.tx = 0; pointer.ty = 0; };
    resize();
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave, { passive: true });

    const draw = (now: number) => {
      if (!alive) return;
      const t = paused || reduced ? 0 : (now - started) / 1000;
      pointer.x += (pointer.tx - pointer.x) * 0.035;
      pointer.y += (pointer.ty - pointer.y) * 0.035;
      ctx.clearRect(0, 0, vw, vh);

      // Deep, deterministic stellar parallax. It responds to the real pointer;
      // there are no sampled or fabricated application metrics in this layer.
      for (const star of stars) {
        const drift = reduced ? 0 : t * (1.1 + star.z * 2.1);
        const x = ((star.x * vw + pointer.x * 24 * star.z + drift) % (vw + 20)) - 10;
        const y = star.y * vh + pointer.y * 16 * star.z;
        const twinkle = 0.34 + Math.sin(t * 0.7 + star.phase) * 0.12;
        ctx.fillStyle = `rgba(220,235,255,${twinkle * star.z})`;
        ctx.beginPath();
        ctx.arc(x, y, star.size * star.z, 0, TAU);
        ctx.fill();
      }

      const compact = Math.min(vw, vh);
      const radius = Math.min(compact * 0.29, 310);
      const cx = vw * 0.55 + pointer.x * 18;
      const cy = vh * 0.47 + pointer.y * 13;
      const rotation = t * 0.035;
      ctx.save();
      ctx.translate(cx, cy);

      // Volumetric halo and horizon rings imply depth without costly WebGL.
      const halo = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 1.55);
      halo.addColorStop(0, "rgba(255,255,255,.035)");
      halo.addColorStop(.22, "rgba(122,224,255,.045)");
      halo.addColorStop(.58, "rgba(179,136,255,.018)");
      halo.addColorStop(1, "rgba(5,5,7,0)");
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(0, 0, radius * 1.55, 0, TAU); ctx.fill();

      for (let ring = 4; ring >= 1; ring--) {
        ctx.save();
        ctx.rotate(rotation * (ring % 2 ? 1 : -0.7));
        ctx.scale(1, 0.34 + ring * 0.035);
        ctx.strokeStyle = ring % 2 ? "rgba(122,224,255,.10)" : "rgba(179,136,255,.08)";
        ctx.lineWidth = 0.7;
        ctx.beginPath(); ctx.arc(0, 0, radius * (0.45 + ring * 0.17), 0, TAU); ctx.stroke();
        ctx.restore();
      }

      const gradient = ctx.createConicGradient(rotation * 2, 0, 0);
      gradient.addColorStop(0, PALETTE[0]);
      gradient.addColorStop(1 / 3, PALETTE[1]);
      gradient.addColorStop(2 / 3, PALETTE[2]);
      gradient.addColorStop(1, PALETTE[0]);

      // Layered polyhedra move at different angular velocities for true parallax.
      const shapes: Array<[number, number, number, number]> = [
        [6, 1, 0.95, .16], [3, .84, 1.35, .28], [4, .61, -.9, .33], [5, .39, .55, .42],
      ];
      for (const [sides, scale, speed, alpha] of shapes) {
        ctx.strokeStyle = gradient;
        ctx.globalAlpha = alpha;
        ctx.lineWidth = sides === 6 ? 0.75 : 1.15;
        polygon(ctx, sides, radius * scale, rotation * speed);
        ctx.stroke();
      }

      // Flower-of-life orbital cells.
      ctx.strokeStyle = "rgba(122,224,255,.18)";
      ctx.lineWidth = 0.55;
      const cell = radius * 0.17;
      for (let ring = 0; ring < 3; ring++) {
        const count = ring === 0 ? 1 : ring * 6;
        for (let i = 0; i < count; i++) {
          const a = (i / count) * TAU + rotation * (ring ? .4 : 0);
          const distance = ring * cell;
          ctx.beginPath();
          ctx.arc(Math.cos(a) * distance, Math.sin(a) * distance, cell, 0, TAU);
          ctx.stroke();
        }
      }

      // The white core owns the highest value in the composition.
      ctx.globalAlpha = 1;
      const pulse = reduced ? 1 : 1 + Math.sin(t * 1.2) * .09;
      const core = ctx.createRadialGradient(0, 0, 0, 0, 0, 28 * pulse);
      core.addColorStop(0, "rgba(255,255,255,1)");
      core.addColorStop(.12, "rgba(255,255,255,.82)");
      core.addColorStop(.38, "rgba(122,224,255,.18)");
      core.addColorStop(1, "rgba(122,224,255,0)");
      ctx.fillStyle = core;
      ctx.beginPath(); ctx.arc(0, 0, 28 * pulse, 0, TAU); ctx.fill();
      ctx.restore();

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
    };
  }, [paused]);

  return <div className={`sacred-geometry ${className}`} aria-hidden="true"><canvas ref={canvasRef} /></div>;
}

export default SacredGeometry;
