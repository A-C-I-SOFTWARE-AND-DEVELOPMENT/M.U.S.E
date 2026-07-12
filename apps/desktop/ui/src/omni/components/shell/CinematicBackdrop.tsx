// Global cinematic atmosphere — the cockpit "Singularity" depth field. A fixed,
// pointer-events-none layer behind all app content (z-index:-1 via
// .cinematic-backdrop in tokens.css): ONE broad cool atmospheric depth pool
// (top-centre cyan→violet ring wash, not a stack), faint matte aurora drift, a
// depth vignette, and a fine film grain — exactly as the cockpit shell paints it.
//
// On top of that token-driven base we add ONE optional, very-subtle scanline
// veil (the cockpit's interlace texture) authored inline here so it stays inside
// this owned file. Everything is decorative (hidden from assistive tech) and
// fully neutralised under prefers-reduced-motion: the scanline drift is killed
// by the global reduced-motion block in tokens.css, and the veil opacity is low
// enough to read as texture, never UI.

// Scoped scanline keyframe + reduced-motion guard. Defined here so the backdrop
// is self-contained and tokens.css remains the single source of token VALUES.
const SCANLINE_CSS = `
@keyframes nexus-scan { to { transform: translateY(50%); } }
.nexus-scanline { animation: nexus-scan 9s linear infinite; }
@media (prefers-reduced-motion: reduce) { .nexus-scanline { animation: none; } }
`;

export function CinematicBackdrop() {
  return (
    <div className="cinematic-backdrop" aria-hidden="true">
      <div className="cb-aurora cb-aurora-1" />
      <div className="cb-aurora cb-aurora-2" />
      <div className="cb-aurora cb-aurora-3" />
      <div className="cb-vignette" />
      <div className="cb-grain" />
      {/* Subtle interlace scanline veil — matte, near-invisible, drifts slowly. */}
      <style>{SCANLINE_CSS}</style>
      <div
        className="nexus-scanline"
        style={{
          position: 'absolute',
          inset: 0,
          height: '200%',
          opacity: 0.02,
          background:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.7) 0, rgba(255,255,255,0.7) 1px, transparent 1px, transparent 3px)',
        }}
      />
    </div>
  );
}
