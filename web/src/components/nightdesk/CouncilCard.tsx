import { Link } from "react-router-dom";
import { useNightdeskOverview } from "./useNightdesk";
import type { CouncilMember } from "./useNightdesk";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Overview · AOS Enterprise Council card
// data.council → { total, members: [{id, role, owner_gated}], available? }
// via the shared useNightdeskOverview poller (GET /api/nightdesk/overview).
// Member rows: ◉ sigil + id (mono) + one-line role mandate + state chip
// (owner_gated → amber 'hold', else green 'approve'). Empty/unavailable
// states are honest — no fabricated roster.
// ---------------------------------------------------------------------------

/** Rows shown before the "+N more roles" overflow note (mockup density). */
const MAX_ROWS = 6;

function MemberRow({ member }: { member: CouncilMember }) {
  const gated = member.owner_gated;
  return (
    <li className="flex min-h-[44px] items-center gap-3 border-b border-white/[0.05] py-1.5 last:border-b-0">
      <span
        aria-hidden="true"
        className="flex-none text-[11px] leading-none"
        style={{ color: gated ? "var(--nd-standby)" : "var(--nd-online)" }}
      >
        ◉
      </span>
      <span className="max-w-[136px] flex-none truncate font-mono text-[11px] text-white/80">
        {member.id}
      </span>
      <span className="min-w-0 flex-1 truncate text-[11px] text-white/45">
        {member.role || "—"}
      </span>
      <span className="nd-chip flex-none" data-status={gated ? "standby" : "online"}>
        {gated ? "hold" : "approve"}
      </span>
    </li>
  );
}

function SkeletonRows() {
  return (
    <div aria-hidden="true">
      {Array.from({ length: 4 }, (_, i) => (
        <div
          key={i}
          className="flex min-h-[44px] items-center gap-3 border-b border-white/[0.05] last:border-b-0"
        >
          <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-white/[0.06]" />
          <div className="h-2 w-24 animate-pulse rounded-full bg-white/[0.06]" />
          <div className="h-2 flex-1 animate-pulse rounded-full bg-white/[0.04]" />
        </div>
      ))}
    </div>
  );
}

export default function CouncilCard() {
  const { data, error, loading, refresh } = useNightdeskOverview();
  const council = data?.council;
  const members = council?.members ?? [];
  const total = council?.total ?? members.length;
  const shown = members.slice(0, MAX_ROWS);
  const overflow = members.length - shown.length;

  return (
    <section className="nd-panel flex flex-col">
      <header className="nd-panel-head">
        <h2 className="nd-label">AOS Enterprise Council</h2>
        <div className="flex flex-none items-baseline gap-2">
          <span className="nd-num text-[22px] leading-none text-white/90">
            {loading && !council ? "—" : total}
          </span>
          <span className="nd-sub">registered roles</span>
        </div>
      </header>

      <div className="nd-panel-body flex-1">
        {loading && !council ? (
          <SkeletonRows />
        ) : error && !council ? (
          <div className="nd-empty">
            <p>council unavailable — {error}</p>
            <button type="button" className="nd-button mt-3" onClick={refresh}>
              retry
            </button>
          </div>
        ) : members.length === 0 ? (
          <div className="nd-empty">
            {council?.available === false
              ? "council registry unavailable"
              : "no council roles registered"}
          </div>
        ) : (
          <ul>
            {shown.map((m) => (
              <MemberRow key={m.id} member={m} />
            ))}
            {overflow > 0 && (
              <li className="pt-2 text-center font-mono text-[10px] text-white/30">
                +{overflow} more roles
              </li>
            )}
          </ul>
        )}
      </div>

      <footer className="flex items-center justify-between gap-3 border-t border-white/[0.05] px-3.5 py-2.5">
        <span className="text-[10px] text-white/30">Fusion council live</span>
        <Link
          to="/fusion"
          className="font-mono text-[10.5px] text-violet-400 transition-colors hover:text-violet-300"
        >
          /fusion
        </Link>
      </footer>
    </section>
  );
}
