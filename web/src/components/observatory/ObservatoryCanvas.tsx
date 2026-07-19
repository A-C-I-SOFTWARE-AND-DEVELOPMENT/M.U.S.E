/**
 * ObservatoryCanvas — WebGL ambient background for the M.U.S.E. dashboard.
 * animation-spec.md §1–§4 (binding contract).
 *
 * A fixed, full-viewport, pointer-events-none, aria-hidden canvas at z-index 3
 * — ABOVE the Backdrop base/filler layers (z-1 opaque var(--background-base),
 * z-2 filler, which would otherwise hide it) and BELOW the Backdrop warm
 * vignette (z-99) + noise grain (z-101), so grain keeps painting over the
 * glow (film look). App content sits at z-10+ (sidebar z-50, header z-40).
 * No props; mount once near the app root.
 *
 * Degradation contract (§4):
 *   - `useGpuTier() === 0` (no WebGL / software rasterizer) → renders null,
 *     the plain Backdrop fallback stays.
 *   - `prefers-reduced-motion: reduce` → renders exactly one static frame,
 *     no rAF loop, no drift, no parallax (resize re-renders one frame so the
 *     canvas never stretches).
 *
 * Precedence note: the design-system `useGpuTier()` ALSO folds
 * prefers-reduced-motion into tier 0, so the reduced-motion branch must be
 * evaluated FIRST — otherwise the static frame would be unreachable and
 * reduced-motion users would silently get the tier-0 (null) path instead.
 */
import { useEffect, useRef, useSyncExternalStore } from "react";
import type { JSX } from "react";

import { useGpuTier } from "@nous-research/ui/hooks/use-gpu-tier";

import { createObservatoryScene } from "./scene";
import type { ObservatorySceneHandle } from "./scene";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      const mql = window.matchMedia(REDUCED_MOTION_QUERY);
      mql.addEventListener("change", onStoreChange);
      return () => mql.removeEventListener("change", onStoreChange);
    },
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
}

export function ObservatoryCanvas(): JSX.Element | null {
  const gpuTier = useGpuTier();
  const reducedMotion = usePrefersReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Reduced motion still gets the static frame (see precedence note above);
  // tier 0 without reduced motion means WebGL is unusable → render nothing.
  const shouldRender = reducedMotion || gpuTier > 0;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!shouldRender || !canvas) return;

    let handle: ObservatorySceneHandle;
    try {
      handle = createObservatoryScene(canvas);
    } catch {
      // WebGL context creation failed despite the tier probe — degrade to
      // nothing rather than throwing through the dashboard.
      return;
    }

    const resize = (): void => {
      handle.resize(window.innerWidth, window.innerHeight);
    };
    resize();
    window.addEventListener("resize", resize);

    if (reducedMotion) {
      // Static contract: one frame, then stop. No loop, no pointer/wheel.
      handle.renderFrame(0, 1 / 60);
      return () => {
        window.removeEventListener("resize", resize);
        handle.dispose();
      };
    }

    let rafId = 0;
    let last = performance.now();
    const start = last;

    function frame(now: number): void {
      // Clamp long gaps (tab jank) so breathing/parallax never jump.
      const deltaSeconds = Math.min((now - last) / 1000, 0.1);
      last = now;
      handle.renderFrame((now - start) / 1000, deltaSeconds);
      rafId = requestAnimationFrame(frame);
    }

    const startLoop = (): void => {
      if (rafId === 0) {
        last = performance.now();
        rafId = requestAnimationFrame(frame);
      }
    };

    const onPointerMove = (event: PointerEvent): void => {
      handle.setPointer(
        (event.clientX / window.innerWidth) * 2 - 1,
        -((event.clientY / window.innerHeight) * 2 - 1),
      );
    };
    const onWheel = (event: WheelEvent): void => {
      handle.nudgeZoom(event.deltaY * 0.01);
    };
    // document.hidden pauses rAF (contract §4); state resumes cleanly.
    const onVisibilityChange = (): void => {
      if (document.hidden) {
        cancelAnimationFrame(rafId);
        rafId = 0;
      } else {
        startLoop();
      }
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("wheel", onWheel, { passive: true });
    document.addEventListener("visibilitychange", onVisibilityChange);
    startLoop();

    return () => {
      cancelAnimationFrame(rafId);
      rafId = 0;
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("wheel", onWheel);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      handle.dispose();
    };
  }, [shouldRender, reducedMotion]);

  if (!shouldRender) return null;

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 3,
        pointerEvents: "none",
        width: "100%",
        height: "100%",
      }}
    />
  );
}
