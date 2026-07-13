/**
 * The muse mark — one blazing white core in the void, encircled by a single
 * thin matte spectral ring with a gap, rotated -32° so the gap sits lower-right.
 *
 * This mirrors the cockpit header glyph (gateway/cockpit/index.html) and
 * the canonical favicon (website/static/img/favicon.svg), with the favicon's
 * stacked cool-white bloom halos so the core reads incandescent. Per the design
 * language: bloom the core ONLY; keep the ring matte (no glow/neon); no lens
 * flare, no drop-shadows. The whole ring+core group spins; the bloom rides with
 * it. `prefers-reduced-motion` stops the spin (handled in app.css).
 *
 * viewBox is a normalized 48-unit square (the cockpit header geometry); set
 * `size` for the rendered pixel box.
 */
type GlyphProps = {
  size?: number;
  /** Whether the ring slowly rotates. Defaults to true. */
  spin?: boolean;
  className?: string;
};

export function Glyph({ size = 28, spin = true, className }: GlyphProps) {
  // Deterministic, locally-scoped gradient ids so multiple glyphs on a page
  // never collide.
  const rid = "muse-ring";
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label="muse"
    >
      <defs>
        <linearGradient id={rid} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#7ae0ff" />
          <stop offset="1" stopColor="#b388ff" />
        </linearGradient>
        {/* Stacked cool-white bloom — bright-tight center → wide-faint edge. */}
        <radialGradient id="muse-halo2" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#d4f2ff" stopOpacity="0.2" />
          <stop offset="1" stopColor="#7ae0ff" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="muse-halo1" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.6" />
          <stop offset="0.55" stopColor="#e6f7ff" stopOpacity="0.26" />
          <stop offset="1" stopColor="#e0f8ff" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="muse-corehot" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffffff" stopOpacity="1" />
          <stop offset="0.62" stopColor="#f2fbff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#eafaff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g className={spin ? "glyph-spin" : undefined}>
        {/* Soft glow behind the whole glyph (matches cockpit header). */}
        <span
          style={{
            position: "absolute",
            inset: -14,
            borderRadius: "50%",
            pointerEvents: "none" as const,
            background:
              "radial-gradient(circle at 50% 50%, rgba(122,224,255,0.10) 0%, rgba(122,224,255,0) 70%)",
          }}
        />
        {/* Matte spectral ring (gap via dasharray), rotated -32°. */}
        <circle
          cx="24"
          cy="24"
          r="15"
          fill="none"
          stroke={`url(#${rid})`}
          strokeWidth="1.6"
          strokeDasharray="66 28"
          strokeLinecap="round"
          transform="rotate(-32 24 24)"
        />
        {/* Bloom halos (core only). */}
        <circle cx="24" cy="24" r="10.4" fill="url(#muse-halo2)" />
        <circle cx="24" cy="24" r="7.4" fill="url(#muse-halo1)" />
        <circle cx="24" cy="24" r="5.8" fill="url(#muse-corehot)" />
        {/* The incandescent core. */}
        <circle cx="24" cy="24" r="3.1" fill="#ffffff" />
      </g>
    </svg>
  );
}