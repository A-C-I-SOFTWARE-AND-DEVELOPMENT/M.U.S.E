/**
 * M.U.S.E. "Observatory" — global motion tokens + entrance helper
 * (animation-spec §6). CSS-driven: the classes referenced here live in
 * `src/styles/motion.css`; this module only exposes the shared easing
 * strings for JS-driven animation (canvas, rAF, inline styles) and a
 * tiny hook that maps the stagger contract onto class names. No
 * framer/motion/gsap dependency.
 */

/** Primary UI curve — entrances, hovers, magnetic pull. */
export const EASE_MOTION = "cubic-bezier(.2,1,.2,1)";

/** Symmetric curve — smooth continuous motion (shimmer, drift). */
export const EASE_SMOOTH = "cubic-bezier(1,0,0,1)";

/** Stagger delay classes defined in motion.css, 40ms steps. */
const STAGGER_CLASSES = [
  "muse-enter-d1",
  "muse-enter-d2",
  "muse-enter-d3",
  "muse-enter-d4",
  "muse-enter-d5",
] as const;

export interface EntranceClasses {
  /** Class for a single (unstaggered) entering section. */
  readonly base: string;
  /**
   * Class for the n-th item in a staggered group (0-based). Indexes
   * beyond the five defined steps clamp to the last (200ms) delay.
   * When `stagger` is false this returns the base class unchanged.
   */
  readonly item: (index: number) => string;
}

/**
 * Returns the class names implementing the spec §6 page-entrance
 * contract (fade + translateY(8px→0), 0.4s var(--ease-motion), 40ms
 * stagger via .muse-enter-d1..d5). Pure mapping — safe to call in any
 * component; no state, no effects, no library.
 */
export function useEntrance(stagger: boolean = false): EntranceClasses {
  return {
    base: "muse-enter",
    item: (index: number) => {
      if (!stagger) return "muse-enter";
      const clamped = Math.min(Math.max(Math.trunc(index), 0), STAGGER_CLASSES.length - 1);
      return `muse-enter ${STAGGER_CLASSES[clamped]}`;
    },
  };
}
