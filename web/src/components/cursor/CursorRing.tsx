import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";

import { createCursorTrail } from "./trail";

/**
 * Custom cursor layer for the M.U.S.E. dashboard (animation-spec §5, §6).
 *
 * The native cursor stays visible — this layer AUGMENTS it with:
 *
 *  1. A 28px ring (1.5px var(--accent) border) that follows the pointer via
 *     rAF lerp (factor 0.35 — fast follow), plus a tiny center dot that
 *     tracks the pointer instantly.
 *  2. Ring expansion to ~44px with an accent-soft background over any
 *     interactive element (a, button, [role="button"], input, select,
 *     textarea, label, [data-magnetic]) via mouseover/mouseout delegation +
 *     closest() matching. Size/background transitions run 300ms on
 *     --ease-motion; on pointerdown the ring contracts (scale .98, 150ms,
 *     plus a 4px shrink on the 300ms size channel).
 *  3. A fading violet glow trail (≤12 dots, canvas 2D — see ./trail.ts).
 *  4. Magnetic hover: [data-magnetic] elements translate up to 6px toward
 *     the pointer while hovered and spring back on leave with --ease-motion.
 *     Original inline transform/transition are captured and restored.
 *
 * Renders NOTHING unless (pointer: fine) matches and prefers-reduced-motion
 * is not set (re-evaluated live). Everything is position:fixed,
 * pointer-events-none, zIndex 9999 (trail canvas 9998), aria-hidden, and
 * every listener/timer/rAF is cleaned up on unmount.
 */

const EASE_MOTION = "cubic-bezier(.2,1,.2,1)";

const RING_SIZE = 28;
const RING_SIZE_HOVER = 44;
const RING_PRESS_SHRINK = 4;
const RING_PRESS_SCALE = 0.98;
const RING_LERP = 0.35;

const MAGNETIC_RANGE = 6;
const MAGNETIC_PULL = 0.25;
const MAGNETIC_TRACK_MS = 150;
const MAGNETIC_RELEASE_MS = 400;

const INTERACTIVE_SELECTOR =
  'a,button,[role="button"],input,select,textarea,label,[data-magnetic]';
const MAGNETIC_SELECTOR = "[data-magnetic]";

/** Live media gate: fine pointer AND no reduced-motion preference. */
function useCursorLayerEnabled(): boolean {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const fine = window.matchMedia("(pointer: fine)");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setEnabled(fine.matches && !reduced.matches);
    update();
    fine.addEventListener("change", update);
    reduced.addEventListener("change", update);
    return () => {
      fine.removeEventListener("change", update);
      reduced.removeEventListener("change", update);
    };
  }, []);

  return enabled;
}

export function CursorRing(): JSX.Element | null {
  const enabled = useCursorLayerEnabled();
  if (!enabled) return null;
  return <CursorLayer />;
}

function CursorLayer(): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ringRef = useRef<HTMLDivElement>(null); // translated by rAF
  const innerRef = useRef<HTMLDivElement>(null); // sized/styled, CSS transitions
  const dotRef = useRef<HTMLDivElement>(null); // translated by rAF, instant

  useEffect(() => {
    const canvas = canvasRef.current;
    const ring = ringRef.current;
    const inner = innerRef.current;
    const dot = dotRef.current;
    if (!canvas || !ring || !inner || !dot) return;

    const trail = createCursorTrail(canvas);

    const pointer = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const ringPos = { x: pointer.x, y: pointer.y };
    const state = { hovering: false, pressed: false, seen: false };
    let rafId = 0;

    const setLayerOpacity = (opacity: string) => {
      ring.style.opacity = opacity;
      dot.style.opacity = opacity;
    };

    const applyRingStyle = () => {
      const base = state.hovering ? RING_SIZE_HOVER : RING_SIZE;
      const size = state.pressed ? base - RING_PRESS_SHRINK : base;
      inner.style.width = `${size}px`;
      inner.style.height = `${size}px`;
      inner.style.backgroundColor = state.hovering
        ? "color-mix(in srgb, var(--accent) 14%, transparent)"
        : "transparent";
      inner.style.transform = `translate(-50%, -50%) scale(${
        state.pressed ? RING_PRESS_SCALE : 1
      })`;
    };
    applyRingStyle();

    // ---- magnetic hover -------------------------------------------------

    interface MagneticOriginal {
      transform: string;
      transition: string;
      restoreTimer: number;
    }
    let magneticEl: HTMLElement | null = null;
    const originals = new WeakMap<HTMLElement, MagneticOriginal>();
    const touched = new Set<HTMLElement>();

    const attachMagnetic = (el: HTMLElement) => {
      const pending = originals.get(el);
      if (pending) window.clearTimeout(pending.restoreTimer);
      originals.set(el, {
        // Re-entry mid-spring: keep the true originals, not our spring values.
        transform: pending ? pending.transform : el.style.transform,
        transition: pending ? pending.transition : el.style.transition,
        restoreTimer: 0,
      });
      touched.add(el);
      el.style.transition = `transform ${MAGNETIC_TRACK_MS}ms ${EASE_MOTION}`;
      magneticEl = el;
    };

    const releaseMagnetic = (el: HTMLElement) => {
      const orig = originals.get(el);
      el.style.transition = `transform ${MAGNETIC_RELEASE_MS}ms ${EASE_MOTION}`;
      el.style.transform = orig?.transform ?? "";
      const timer = window.setTimeout(() => {
        el.style.transition = orig?.transition ?? "";
        originals.delete(el);
        touched.delete(el);
      }, MAGNETIC_RELEASE_MS + 20);
      if (orig) orig.restoreTimer = timer;
    };

    const updateMagnetic = (target: EventTarget | null) => {
      const el =
        target instanceof Element
          ? target.closest<HTMLElement>(MAGNETIC_SELECTOR)
          : null;
      const next = el instanceof HTMLElement ? el : null;
      if (next === magneticEl) return;
      if (magneticEl) releaseMagnetic(magneticEl);
      magneticEl = null;
      if (next) attachMagnetic(next);
    };

    const moveMagnetic = (clientX: number, clientY: number) => {
      const el = magneticEl;
      if (!el) return;
      if (!el.isConnected) {
        magneticEl = null;
        return;
      }
      const rect = el.getBoundingClientRect();
      const dx = clientX - (rect.left + rect.width / 2);
      const dy = clientY - (rect.top + rect.height / 2);
      const tx = Math.max(
        -MAGNETIC_RANGE,
        Math.min(MAGNETIC_RANGE, dx * MAGNETIC_PULL),
      );
      const ty = Math.max(
        -MAGNETIC_RANGE,
        Math.min(MAGNETIC_RANGE, dy * MAGNETIC_PULL),
      );
      el.style.transform = `translate3d(${tx}px, ${ty}px, 0)`;
    };

    // ---- pointer / hover tracking ----------------------------------------

    const updateHover = (target: EventTarget | null) => {
      const hovering =
        target instanceof Element &&
        target.closest(INTERACTIVE_SELECTOR) !== null;
      if (hovering === state.hovering) return;
      state.hovering = hovering;
      applyRingStyle();
    };

    const onPointerMove = (e: PointerEvent) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      if (!state.seen) {
        // Snap the ring onto the pointer on first sight instead of
        // lerping in from the viewport center.
        state.seen = true;
        ringPos.x = pointer.x;
        ringPos.y = pointer.y;
        setLayerOpacity("1");
      }
      trail.spawn(e.clientX, e.clientY);
      moveMagnetic(e.clientX, e.clientY);
    };

    const onMouseOver = (e: MouseEvent) => {
      updateHover(e.target);
      updateMagnetic(e.target);
    };

    const onMouseOut = (e: MouseEvent) => {
      // relatedTarget is where the pointer is going (null when leaving the
      // window) — evaluating it keeps hover state correct with zero flicker.
      updateHover(e.relatedTarget);
      updateMagnetic(e.relatedTarget);
    };

    const onPointerDown = () => {
      if (state.pressed) return;
      state.pressed = true;
      applyRingStyle();
    };

    const onPointerUp = () => {
      if (!state.pressed) return;
      state.pressed = false;
      applyRingStyle();
    };

    const onDocumentLeave = () => setLayerOpacity("0");
    const onDocumentEnter = () => {
      if (state.seen) setLayerOpacity("1");
    };

    // ---- rAF follow + trail loop ------------------------------------------

    const frame = (now: number) => {
      ringPos.x += (pointer.x - ringPos.x) * RING_LERP;
      ringPos.y += (pointer.y - ringPos.y) * RING_LERP;
      ring.style.transform = `translate3d(${ringPos.x}px, ${ringPos.y}px, 0)`;
      dot.style.transform = `translate3d(${pointer.x}px, ${pointer.y}px, 0)`;
      trail.render(now);
      rafId = requestAnimationFrame(frame);
    };
    rafId = requestAnimationFrame(frame);

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerdown", onPointerDown, { passive: true });
    window.addEventListener("pointerup", onPointerUp, { passive: true });
    window.addEventListener("pointercancel", onPointerUp, { passive: true });
    window.addEventListener("blur", onPointerUp);
    window.addEventListener("mouseover", onMouseOver, { passive: true });
    window.addEventListener("mouseout", onMouseOut, { passive: true });
    document.addEventListener("mouseleave", onDocumentLeave);
    document.addEventListener("mouseenter", onDocumentEnter);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
      window.removeEventListener("blur", onPointerUp);
      window.removeEventListener("mouseover", onMouseOver);
      window.removeEventListener("mouseout", onMouseOut);
      document.removeEventListener("mouseleave", onDocumentLeave);
      document.removeEventListener("mouseenter", onDocumentEnter);
      // Restore any element still under magnetic influence.
      for (const el of touched) {
        const orig = originals.get(el);
        if (orig) {
          window.clearTimeout(orig.restoreTimer);
          el.style.transform = orig.transform;
          el.style.transition = orig.transition;
        }
      }
      touched.clear();
      trail.destroy();
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        aria-hidden
        style={{
          position: "fixed",
          inset: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: 9998,
        }}
      />
      <div
        ref={ringRef}
        aria-hidden
        style={{
          position: "fixed",
          left: 0,
          top: 0,
          pointerEvents: "none",
          zIndex: 9999,
          opacity: 0,
          transition: "opacity 200ms ease-out",
          willChange: "transform",
        }}
      >
        <div
          ref={innerRef}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: RING_SIZE,
            height: RING_SIZE,
            boxSizing: "border-box",
            border: "1.5px solid var(--accent)",
            borderRadius: "50%",
            transform: "translate(-50%, -50%) scale(1)",
            transition: `width 300ms ${EASE_MOTION}, height 300ms ${EASE_MOTION}, background-color 300ms ${EASE_MOTION}, transform 150ms ${EASE_MOTION}`,
          }}
        />
      </div>
      <div
        ref={dotRef}
        aria-hidden
        style={{
          position: "fixed",
          left: 0,
          top: 0,
          width: 4,
          height: 4,
          marginLeft: -2,
          marginTop: -2,
          borderRadius: "50%",
          backgroundColor: "var(--accent)",
          pointerEvents: "none",
          zIndex: 9999,
          opacity: 0,
          transition: "opacity 200ms ease-out",
          willChange: "transform",
        }}
      />
    </>
  );
}
