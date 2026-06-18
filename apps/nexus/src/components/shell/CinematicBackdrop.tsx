// Global cinematic atmosphere — the "belongs in a movie" finish. A fixed,
// pointer-events-none layer behind all app content: slow-drifting volumetric
// aurora light, a depth vignette, and a fine film grain. All styling lives in
// styles/tokens.css (`.cinematic-backdrop` and friends) and is fully
// neutralized under prefers-reduced-motion. Purely decorative, so it is hidden
// from assistive tech.
export function CinematicBackdrop() {
  return (
    <div className="cinematic-backdrop" aria-hidden="true">
      <div className="cb-aurora cb-aurora-1" />
      <div className="cb-aurora cb-aurora-2" />
      <div className="cb-aurora cb-aurora-3" />
      <div className="cb-vignette" />
      <div className="cb-grain" />
    </div>
  );
}
