/**
 * SacredGeometry — full galactic space-station backscene for the DESK shell.
 * Canvas pixels follow the live WebView size and DPR so the composition stays
 * sharp at 4K/8K without raster artwork or mock operational data.
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

function seededStars(count: number): Star[] {
  let seed = 0x51a7c0de;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0xffffffff;
  };
  return Array.from({ length: count }, () => ({
    x: random(),
    y: random(),
    z: 0.14 + random() * 0.86,
    size: 0.3 + random() * 1.35,
    phase: random() * TAU,
  }));
}

function drawStation(
  ctx: CanvasRenderingContext2D,
  radius: number,
  rotation: number,
  reduced: boolean,
  t: number,
) {
  // Non-rotating spine
  ctx.save();
  ctx.rotate(0.08);
  ctx.fillStyle = "rgba(127,137,145,0.55)";
  ctx.fillRect(-radius * 0.045, -radius * 1.05, radius * 0.09, radius * 2.1);

  // Counter-rotating crown rings
  for (const [scale, dir, alpha] of [
    [0.42, 1, 0.55],
    [0.58, -1, 0.42],
    [0.78, 1, 0.28],
  ] as const) {
    ctx.save();
    ctx.rotate(rotation * dir * (reduced ? 0 : 1));
    ctx.scale(1, 0.38);
    ctx.strokeStyle = `rgba(180,200,210,${alpha})`;
    ctx.lineWidth = radius * 0.018;
    ctx.beginPath();
    ctx.arc(0, 0, radius * scale, 0, TAU);
    ctx.stroke();
    // Habitats on the ring
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * TAU;
      const x = Math.cos(a) * radius * scale;
      const y = Math.sin(a) * radius * scale;
      ctx.fillStyle = i % 3 === 0 ? "rgba(194,201,202,0.7)" : "rgba(37,43,49,0.85)";
      ctx.fillRect(x - radius * 0.02, y - radius * 0.012, radius * 0.04, radius * 0.024);
    }
    ctx.restore();
  }

  // Five sector arcs
  ctx.save();
  ctx.rotate(rotation * 0.2);
  for (let i = 0; i < 5; i++) {
    const start = (i / 5) * TAU + 0.08;
    ctx.strokeStyle = i === 0 ? "rgba(174,181,184,0.55)" : "rgba(127,137,145,0.35)";
    ctx.lineWidth = radius * 0.035;
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.95, start, start + 0.72);
    ctx.stroke();
  }
  ctx.restore();

  // Dock assemblies
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * TAU + Math.PI / 4;
    const x = Math.cos(a) * radius * 1.18;
    const y = Math.sin(a) * radius * 1.18 * 0.38;
    ctx.fillStyle = "rgba(80,90,98,0.7)";
    ctx.beginPath();
    ctx.ellipse(x, y, radius * 0.08, radius * 0.04, a, 0, TAU);
    ctx.fill();
  }

  // Neural core — white singularity
  const pulse = reduced ? 1 : 1 + Math.sin(t * 1.15) * 0.08;
  const core = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 0.22 * pulse);
  core.addColorStop(0, "rgba(255,255,255,1)");
  core.addColorStop(0.14, "rgba(231,247,251,0.9)");
  core.addColorStop(0.4, "rgba(122,224,255,0.28)");
  core.addColorStop(1, "rgba(122,224,255,0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(0, 0, radius * 0.22 * pulse, 0, TAU);
  ctx.fill();

  // Spectral matte ring around the core
  const ring = ctx.createConicGradient(rotation * 2, 0, 0);
  ring.addColorStop(0, "#7ae0ff");
  ring.addColorStop(0.5, "#b388ff");
  ring.addColorStop(1, "#7ae0ff");
  ctx.strokeStyle = ring;
  ctx.globalAlpha = 0.85;
  ctx.lineWidth = Math.max(1.2, radius * 0.012);
  ctx.beginPath();
  ctx.arc(0, 0, radius * 0.26 * pulse, 0, TAU * 0.82);
  ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.restore();
}

export function SacredGeometry({ className = "", paused = false }: SacredGeometryProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true, desynchronized: true });
    if (!ctx) return;

    const stars = seededStars(280);
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let vw = 1,
      vh = 1,
      dpr = 1,
      raf = 0,
      alive = true;
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
    const leave = () => {
      pointer.tx = 0;
      pointer.ty = 0;
    };
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

      // Galactic plane wash
      const galaxy = ctx.createLinearGradient(0, vh * 0.35, vw, vh * 0.75);
      galaxy.addColorStop(0, "rgba(5,5,7,0)");
      galaxy.addColorStop(0.35, "rgba(122,224,255,0.04)");
      galaxy.addColorStop(0.55, "rgba(179,136,255,0.055)");
      galaxy.addColorStop(0.8, "rgba(122,224,255,0.03)");
      galaxy.addColorStop(1, "rgba(5,5,7,0)");
      ctx.fillStyle = galaxy;
      ctx.fillRect(0, 0, vw, vh);

      // Host world
      const wx = vw * 0.18 + pointer.x * 10;
      const wy = vh * 0.72 + pointer.y * 8;
      const wr = Math.min(vw, vh) * 0.22;
      const world = ctx.createRadialGradient(wx - wr * 0.2, wy - wr * 0.25, wr * 0.1, wx, wy, wr);
      world.addColorStop(0, "rgba(90,140,160,0.35)");
      world.addColorStop(0.45, "rgba(26,42,54,0.55)");
      world.addColorStop(1, "rgba(5,5,7,0)");
      ctx.fillStyle = world;
      ctx.beginPath();
      ctx.arc(wx, wy, wr, 0, TAU);
      ctx.fill();
      ctx.strokeStyle = "rgba(142,184,200,0.18)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(wx, wy, wr * 1.28, wr * 0.22, -0.35, 0, TAU);
      ctx.stroke();

      // Stars with parallax
      for (const star of stars) {
        const drift = reduced ? 0 : t * (0.9 + star.z * 1.8);
        const x = ((star.x * vw + pointer.x * 28 * star.z + drift) % (vw + 20)) - 10;
        const y = star.y * vh + pointer.y * 18 * star.z;
        const twinkle = 0.32 + Math.sin(t * 0.7 + star.phase) * 0.14;
        ctx.fillStyle = `rgba(220,235,255,${twinkle * star.z})`;
        ctx.beginPath();
        ctx.arc(x, y, star.size * star.z, 0, TAU);
        ctx.fill();
      }

      const compact = Math.min(vw, vh);
      const radius = Math.min(compact * 0.32, 340);
      const cx = vw * 0.58 + pointer.x * 16;
      const cy = vh * 0.44 + pointer.y * 12;
      const rotation = t * 0.04;

      ctx.save();
      ctx.translate(cx, cy);

      // Depth halo behind station
      const halo = ctx.createRadialGradient(0, 0, 0, 0, 0, radius * 1.7);
      halo.addColorStop(0, "rgba(255,255,255,.04)");
      halo.addColorStop(0.2, "rgba(122,224,255,.05)");
      halo.addColorStop(0.55, "rgba(179,136,255,.02)");
      halo.addColorStop(1, "rgba(5,5,7,0)");
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(0, 0, radius * 1.7, 0, TAU);
      ctx.fill();

      drawStation(ctx, radius, rotation, reduced, t);
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

  return (
    <div className={`sacred-geometry ${className}`} aria-hidden="true">
      <canvas ref={canvasRef} />
    </div>
  );
}

export default SacredGeometry;
