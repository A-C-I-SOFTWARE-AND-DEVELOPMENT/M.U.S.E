import { formatRelativeTime, useNightdeskOverview } from "./useNightdesk";
import type { NightdeskLedgerEntry } from "./useNightdesk";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Overview · Decision ledger card
// data.ledger → newest decision-ledger entries across sessions
// [{id: "session:stem", title, session, ts}] via the shared
// useNightdeskOverview poller. Entries are real decision files surfaced
// read-only — no actions. Ids render mono with middle truncation; ts is
// unix seconds shown relative. Empty state stays honest.
// ---------------------------------------------------------------------------

/** Rows shown before the "+N earlier decisions" note (mockup density). */
const MAX_ROWS = 6;

/** Middle-truncate a long id, keeping both ends legible: "abcd…wxyz". */
function truncateMiddle(s: string, max = 30): string {
  if (s.length <= max) return s;
  const keep = max - 1;
  const head = Math.ceil(keep / 2);
  const tail = Math.floor(keep / 2);
  return `${s.slice(0, head)}…${s.slice(s.length - tail)}`;
}

function LedgerRow({ entry }: { entry: NightdeskLedgerEntry }) {
  return (
    <li className="flex min-h-[44px] items-center gap-3 border-b border-white/[0.05] py-1.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12px] text-white/80">{entry.title}</div>
        <div
          className="mt-0.5 truncate font-mono text-[10px] text-white/30"
          title={entry.id}
        >
          {truncateMiddle(entry.id)}
        </div>
      </div>
      <span className="nd-num flex-none text-[10px] text-white/35">
        {formatRelativeTime(entry.ts)}
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
          <div className="min-w-0 flex-1">
            <div className="h-2.5 w-2/3 animate-pulse rounded-full bg-white/[0.06]" />
            <div className="mt-1.5 h-2 w-1/3 animate-pulse rounded-full bg-white/[0.04]" />
          </div>
          <div className="h-2 w-10 flex-none animate-pulse rounded-full bg-white/[0.05]" />
        </div>
      ))}
    </div>
  );
}

export default function LedgerCard() {
  const { data, error, loading, refresh } = useNightdeskOverview();
  const entries = data?.ledger;
  const list = entries ?? [];
  const shown = list.slice(0, MAX_ROWS);
  const overflow = list.length - shown.length;

  return (
    <section className="nd-panel flex flex-col">
      <header className="nd-panel-head">
        <div className="min-w-0">
          <h2 className="nd-label">Decision ledger</h2>
          <p className="nd-sub mt-0.5">tamper-evident · hash-chained</p>
        </div>
        {entries && (
          <span className="nd-num flex-none text-[11px] text-white/40">
            {list.length} latest
          </span>
        )}
      </header>

      <div className="nd-panel-body flex-1">
        {loading && !entries ? (
          <SkeletonRows />
        ) : error && !entries ? (
          <div className="nd-empty">
            <p>ledger unavailable — {error}</p>
            <button type="button" className="nd-button mt-3" onClick={refresh}>
              retry
            </button>
          </div>
        ) : list.length === 0 ? (
          <div className="nd-empty">no decisions recorded yet</div>
        ) : (
          <>
            <ul>
              {shown.map((entry) => (
                <LedgerRow key={entry.id} entry={entry} />
              ))}
            </ul>
            {overflow > 0 && (
              <p className="pt-2 text-center font-mono text-[10px] text-white/30">
                +{overflow} earlier decisions
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
