import { useGpuTier } from "@nous-research/ui/hooks/use-gpu-tier";

/**
 * Replicates the visual layer stack of `<Overlays dark />` from
 * `@nous-research/ui` without pulling in its leva / gsap / three peer deps.
 *
 * See `design-language/src/ui/components/overlays/index.tsx` for the source of
 * truth. Defaults match LENS_0 (the muse teal dark preset); the deep canvas
 * and the warm vignette both read theme-switchable CSS custom properties so
 * `ThemeProvider` can repaint the stack without remounting.
 *
 *   z-1   bg = `var(--background-base)`, mix-blend-mode: difference
 *   z-2   code-drawn muse texture (inline SVG), inverted, opacity 0.033,
 *         difference — replaces the old bundled engraving WebP
 *   z-99  warm top-left vignette (`var(--warm-glow)`), opacity 0.22, lighten
 *   z-101 noise grain (SVG, ~55% opacity × `--noise-opacity-mul`,
 *         color-dodge) — gated on GPU tier
 *
 * The z-2 texture is pure code, no bundled imagery: a soft low-frequency
 * feTurbulence tonal wash (the tonal role the old filler image played), a
 * fine diagonal line-field, a high-frequency grain, and a faint M.U.S.E.
 * concentric-ring sigil right-of-center (mirroring the Observatory sigil's
 * placement so the content column stays readable). It is authored on a
 * near-white field so the layer's CSS `invert` lands it on the Singularity
 * void; the ring strokes use the complement of the `--accent` violet so
 * they read as a violet whisper after inversion. At 0.033 opacity with
 * difference blending it reads as grain/texture, never as imagery.
 *
 * `useGpuTier` returns 0 when WebGL is unavailable, the renderer is a
 * software rasterizer (SwiftShader/llvmpipe), or the user has
 * `prefers-reduced-motion: reduce` set. We skip the animated noise layer
 * in that case so low-power / accessibility-conscious sessions stay crisp,
 * mirroring the DS `<Noise />` component's own opt-out.
 */
export function Backdrop() {
  const gpuTier = useGpuTier();

  return (
    <>
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[1]"
        style={{
          backgroundColor: "var(--background-base)",
          mixBlendMode: "difference",
        }}
      />

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[2]"
        style={
          {
            // Themes can override the filler layer by setting
            // `assets.bg` — the default texture hides itself when a CSS bg
            // is set so the two don't double-darken. CSS var fallbacks keep
            // the default behaviour unchanged when no theme customises these.
            mixBlendMode:
              "var(--component-backdrop-filler-blend-mode, difference)",
            opacity: "var(--component-backdrop-filler-opacity, 0.033)",
            backgroundImage: "var(--theme-asset-bg)",
            backgroundSize: "var(--component-backdrop-background-size, cover)",
            backgroundPosition:
              "var(--component-backdrop-background-position, center)",
          } as unknown as React.CSSProperties
        }
      >
        <svg
          aria-hidden="true"
          focusable="false"
          className="h-[150dvh] w-full min-w-[100dvw] invert theme-default-filler"
          viewBox="0 0 1600 1000"
          preserveAspectRatio="xMinYMin slice"
        >
          <defs>
            {/* Broad low-frequency tonal drift — the soft mid-tone wash the
                old filler image supplied, so the layer keeps its organic
                depth without any pictorial content. */}
            <filter
              id="muse-filler-clouds"
              x="0"
              y="0"
              width="100%"
              height="100%"
            >
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.004 0.006"
                numOctaves="4"
                seed="11"
                stitchTiles="stitch"
              />
              <feColorMatrix
                type="matrix"
                values="0 0 0 0 0.10  0 0 0 0 0.09  0 0 0 0 0.14  0.9 0.9 0.9 0 -1.35"
              />
            </filter>
            {/* Fine high-frequency grain — breaks up the flat field the way
                an engraving's hatching grain did. */}
            <filter
              id="muse-filler-grain"
              x="0"
              y="0"
              width="100%"
              height="100%"
            >
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.9"
                numOctaves="2"
                seed="4"
                stitchTiles="stitch"
              />
              <feColorMatrix
                type="matrix"
                values="0 0 0 0 0.16  0 0 0 0 0.14  0 0 0 0 0.20  0 0 0 0.9 -0.42"
              />
            </filter>
            {/* Fine diagonal line-field. */}
            <pattern
              id="muse-filler-lines"
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(28)"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="6"
                stroke="#231e2c"
                strokeWidth="0.55"
              />
            </pattern>
          </defs>

          {/* Pre-inversion field: near-white → post-inversion Singularity
              void (#050507 family). */}
          <rect width="1600" height="1000" fill="#f5f3f8" />
          <rect
            width="1600"
            height="1000"
            filter="url(#muse-filler-clouds)"
            opacity="0.7"
          />
          <rect
            width="1600"
            height="1000"
            fill="url(#muse-filler-lines)"
            opacity="0.22"
          />

          {/* M.U.S.E. concentric-ring sigil, right-of-center. Stroke hue is
              the complement of the Singularity violet so the layer's invert
              lands it in the --accent family. */}
          <g fill="none" stroke="#2b4a08">
            <circle cx="1150" cy="370" r="70" strokeWidth="1.1" opacity="0.5" />
            <circle cx="1150" cy="370" r="120" strokeWidth="1" opacity="0.44" />
            <circle cx="1150" cy="370" r="185" strokeWidth="0.95" opacity="0.38" />
            <circle cx="1150" cy="370" r="265" strokeWidth="0.9" opacity="0.32" />
            <circle cx="1150" cy="370" r="360" strokeWidth="0.85" opacity="0.26" />
            <circle cx="1150" cy="370" r="470" strokeWidth="0.8" opacity="0.2" />
            <circle cx="1150" cy="370" r="595" strokeWidth="0.75" opacity="0.15" />
            <circle cx="1150" cy="370" r="735" strokeWidth="0.7" opacity="0.11" />
            {/* Observatory-instrument ticks on the third ring. */}
            <g strokeWidth="0.9" opacity="0.42">
              <line x1="1150" y1="179" x2="1150" y2="191" />
              <line x1="1150" y1="549" x2="1150" y2="561" />
              <line x1="959" y1="370" x2="971" y2="370" />
              <line x1="1329" y1="370" x2="1341" y2="370" />
              <line x1="1015.1" y1="235.1" x2="1023.6" y2="243.6" />
              <line x1="1276.4" y1="496.4" x2="1284.9" y2="504.9" />
              <line x1="1276.4" y1="243.6" x2="1284.9" y2="235.1" />
              <line x1="1015.1" y1="504.9" x2="1023.6" y2="496.4" />
            </g>
            <circle cx="1150" cy="370" r="2.6" fill="#2b4a08" stroke="none" opacity="0.55" />
          </g>

          <rect
            width="1600"
            height="1000"
            filter="url(#muse-filler-grain)"
            opacity="0.5"
          />
        </svg>
      </div>

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[99]"
        style={{
          background:
            "radial-gradient(ellipse at 0% 0%, transparent 60%, var(--warm-glow) 100%)",
          mixBlendMode: "lighten",
          opacity: 0.22,
        }}
      />

      {gpuTier > 0 && (
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 z-[101]"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' fill='%23eaeaea' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E\")",
            backgroundSize: "512px 512px",
            mixBlendMode: "color-dodge",
            opacity: "calc(0.55 * var(--noise-opacity-mul, 1))",
          }}
        />
      )}
    </>
  );
}
