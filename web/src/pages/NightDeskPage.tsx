import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "@/components/nightdesk/nightdesk.css";
import { useNightdeskOverview } from "@/components/nightdesk/useNightdesk";
import KpiStrip from "@/components/nightdesk/KpiStrip";
import TickerStrip from "@/components/nightdesk/TickerStrip";
import BackendsGrid from "@/components/nightdesk/BackendsGrid";
import EmergencyStop from "@/components/nightdesk/EmergencyStop";
/* Sibling components landed — real imports (contract: default export, no props). */
import ThroughputChart from "@/components/nightdesk/ThroughputChart";
import CostByProvider from "@/components/nightdesk/CostByProvider";
import PathwaysTable from "@/components/nightdesk/PathwaysTable";
import OrchestrationCard from "@/components/nightdesk/OrchestrationCard";
import MindStream from "@/components/nightdesk/MindStream";
import GatedActionsRail from "@/components/nightdesk/GatedActionsRail";
import CouncilCard from "@/components/nightdesk/CouncilCard";
import AutomationsCard from "@/components/nightdesk/AutomationsCard";
import LedgerCard from "@/components/nightdesk/LedgerCard";
import GatesRail from "@/components/nightdesk/GatesRail";

/* Sibling contract (ND-SHELL): every component above is a default-export
   React component taking NO props (self-fetching), built by parallel
   agents against the shared useNightdeskOverview data hook. */

/* ── In-page views + rail model ─────────────────────────────────────── */

type NightDeskView = "overview" | "mindstream" | "router" | "orchestration";

const VIEW_ITEMS: { id: NightDeskView; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "mindstream", label: "Mind stream" },
  { id: "router", label: "Model router" },
  { id: "orchestration", label: "Orchestration" },
];

/** Visual mode chips — 'Companion' is the active default per the mockups. */
const MODES = ["Companion", "Strategy", "Critic", "Operator", "Builder"] as const;
const ACTIVE_MODE = "Companion";

export default function NightDeskPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<NightDeskView>("overview");
  const [query, setQuery] = useState("");

  // Shared poller — the header Axion chip rides the same overview fetch
  // as every other Night Desk component on the page.
  const { data } = useNightdeskOverview(60000);
  const axion = data?.axion ?? null;

  /** Anchor targets live inside the overview view — switch first, then scroll. */
  const goOverviewAnchor =
    (anchorId: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
      e.preventDefault();
      setView("overview");
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          document
            .getElementById(anchorId)
            ?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      });
    };

  const onSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const q = query.trim();
    navigate(q ? `/sessions?q=${encodeURIComponent(q)}` : "/sessions");
  };

  return (
    <div className="nightdesk">
      {/* ── Top header ─────────────────────────────────────────────── */}
      <header className="nd-header">
        <div className="nd-wordmark">
          <span className="nd-wordmark-name">◉ muse</span>
          <span className="nd-wordmark-sub">Multi-Use Synaptic Entity</span>
        </div>

        <span className="nd-label" style={{ flex: "none" }}>
          Night Desk
        </span>

        <div className="nd-header-spacer" />

        <form className="nd-search-form" onSubmit={onSearch} role="search">
          <input
            className="nd-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sessions…"
            aria-label="Search sessions"
          />
        </form>

        <span
          className="nd-axion"
          data-wired={axion?.wired ? "true" : "false"}
          title={axion?.identity_excerpt ?? "Axion identity unavailable"}
        >
          Axion · {axion?.wired ? "wired" : "unwired"}
        </span>
      </header>

      {/* ── Body: slim left rail + content ─────────────────────────── */}
      <div className="nd-body">
        <aside className="nd-rail" aria-label="Night Desk navigation">
          <nav className="nd-rail-group">
            <span className="nd-label">Night Desk</span>
            {VIEW_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                className="nd-rail-item"
                data-active={view === item.id}
                onClick={() => setView(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <nav className="nd-rail-group">
            <span className="nd-label">Jump to</span>
            <Link className="nd-rail-item" to="/analytics">
              Memory &amp; Graph
            </Link>
            <Link className="nd-rail-item" to="/fusion">
              Council
            </Link>
            <Link className="nd-rail-item" to="/cron">
              Automations
            </Link>
            <a
              className="nd-rail-item"
              href="#nd-ledger"
              onClick={goOverviewAnchor("nd-ledger")}
            >
              Decision ledger
            </a>
            <a
              className="nd-rail-item"
              href="#nd-backends"
              onClick={goOverviewAnchor("nd-backends")}
            >
              Backends &amp; gateways
            </a>
          </nav>

          <div className="nd-rail-stop">
            <EmergencyStop />
          </div>
        </aside>

        <main className="nd-content">
          {/* Modes row — visual chips, no backend wiring yet. */}
          <div className="nd-modes" role="group" aria-label="Modes">
            <span className="nd-label">Mode</span>
            {MODES.map((mode) => (
              <span
                key={mode}
                className="nd-mode-chip"
                data-active={mode === ACTIVE_MODE}
              >
                {mode}
              </span>
            ))}
          </div>

          {view === "overview" && (
            <div className="nd-stack">
              <KpiStrip />
              <TickerStrip />
              <div className="nd-grid-3">
                <CouncilCard />
                <AutomationsCard />
                <div id="nd-ledger">
                  <LedgerCard />
                </div>
              </div>
              <div id="nd-backends">
                <BackendsGrid />
              </div>
            </div>
          )}

          {view === "mindstream" && (
            <div className="nd-stack">
              <MindStream />
              <div className="nd-grid-2">
                <GatedActionsRail />
                <GatesRail />
              </div>
            </div>
          )}

          {view === "router" && (
            <div className="nd-stack">
              <div className="nd-grid-2">
                <ThroughputChart />
                <CostByProvider />
              </div>
              <PathwaysTable />
            </div>
          )}

          {view === "orchestration" && (
            <div className="nd-stack">
              <OrchestrationCard />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
