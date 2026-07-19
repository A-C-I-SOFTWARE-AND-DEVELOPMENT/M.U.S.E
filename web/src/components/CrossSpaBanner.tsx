/**
 * CrossSpaBanner — shown only on non-main SPA routes (/omni, /musehq, /nexus).
 *
 * Gives the user a one-click way back to the main MUSE Dashboard so they
 * don't get lost when crossing between the four different React SPAs that
 * share the same origin.
 *
 * Without this banner, switching from /chat (main) to /omni (omni cockpit)
 * to /nexus (M.U.S.E console) leaves the user with no shared nav and three
 * different brand identities — this is the lightweight fix for that UX gap.
 */
import { useLocation } from "react-router-dom";
import { X, ArrowLeft } from "lucide-react";
import { useState, useEffect } from "react";

// Singularity contract: ONE accent for all chrome. The per-SPA colors were
// hardcoded rgba values (incl. the old teal rgba(0,200,180,.6)) that ignored
// the theme engine — route through var(--accent) via color-mix instead.
const ACCENT_GLOW = "color-mix(in srgb, var(--accent) 60%, transparent)";

const CROSS_SPA_PATHS: Record<string, { name: string; accent: string }> = {
  "/omni":  { name: "omni live harness",  accent: ACCENT_GLOW },
  "/musehq": { name: "musehq cockpit",    accent: ACCENT_GLOW },
  "/nexus": { name: "M.U.S.E. console",   accent: ACCENT_GLOW },
};

export function CrossSpaBanner() {
  const { pathname } = useLocation();
  const normalized = pathname.replace(/\/$/, "") || "/";
  const meta = CROSS_SPA_PATHS[normalized];
  const [dismissed, setDismissed] = useState(false);

  // Reset dismissed state when the user navigates to a different cross-SPA route
  useEffect(() => {
    setDismissed(false);
  }, [normalized]);

  if (!meta || dismissed) return null;

  return (
    <div
      role="status"
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between gap-3 border-b border-current/20 px-4 py-2 text-[0.75rem] backdrop-blur"
      style={{
        background:
          "linear-gradient(90deg, color-mix(in srgb, var(--bg-elev) 95%, transparent), color-mix(in srgb, var(--bg) 92%, transparent))",
        boxShadow: `0 0 24px -8px ${meta.accent}`,
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: meta.accent, boxShadow: `0 0 8px ${meta.accent}` }}
        />
        <span className="opacity-70">You&apos;re in</span>
        <span className="font-bold" style={{ color: meta.accent }}>
          {meta.name}
        </span>
        <span className="opacity-40">— different from the main MUSE dashboard</span>
      </div>
      <div className="flex items-center gap-2">
        <a
          href="/chat"
          className="flex items-center gap-1.5 rounded border border-current/30 px-2.5 py-1 font-medium tracking-[0.05em] transition-colors hover:bg-white/[0.06]"
        >
          <ArrowLeft className="h-3 w-3" />
          <span>Back to MUSE</span>
        </a>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Dismiss banner"
          className="rounded p-1 opacity-40 transition-opacity hover:opacity-80"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
