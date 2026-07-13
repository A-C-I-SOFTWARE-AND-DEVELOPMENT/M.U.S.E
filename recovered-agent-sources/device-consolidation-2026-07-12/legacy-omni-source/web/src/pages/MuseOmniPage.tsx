import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

type ApiStatus = {
  version?: string;
  release_date?: string;
  hermes_home?: string;
  config_path?: string;
  gateway_running?: boolean;
  gateway_state?: string | null;
  active_sessions?: number;
};

type ModelInfo = {
  model?: string;
  provider?: string;
  effective_context_length?: number;
  capabilities?: Record<string, unknown>;
};

type SessionItem = {
  id?: string;
  title?: string;
  model?: string;
  message_count?: number;
  source?: string;
  started_at?: number;
  last_active?: number;
};

type SkillItem = { name: string; description?: string; enabled?: boolean; category?: string | null };
type PluginItem = { name: string; label?: string; description?: string; version?: string };
type CronJob = { id?: string; name?: string; schedule?: string; enabled?: boolean; next_run?: string };
type Analytics = {
  totals?: {
    total_sessions?: number | null;
    total_input?: number | null;
    total_output?: number | null;
    total_estimated_cost?: number | null;
  };
  by_model?: Array<{ model?: string; total_tokens?: number; tokens?: number; sessions?: number; cost?: number }>;
};

type RepoInfo = {
  root?: string;
  web_dist?: string;
  branch?: string;
  commit?: string;
  commit_subject?: string;
  dirty?: boolean;
  changed_count?: number;
  changed_preview?: string[];
  packages?: Record<string, { name?: string; version?: string; scripts?: string[]; dependencies?: number; dev_dependencies?: number }>;
  counts?: Record<string, number>;
  surfaces?: Record<string, boolean>;
};

type DashboardData = {
  status: ApiStatus | null;
  model: ModelInfo | null;
  sessions: SessionItem[];
  skills: SkillItem[];
  plugins: PluginItem[];
  cron: CronJob[];
  analytics: Analytics | null;
  repo: RepoInfo | null;
  logs: string[];
};

async function api<T>(path: string): Promise<T | null> {
  const fetchWithTimeout = async (headers?: HeadersInit) => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4_000);
    try {
      return await fetch(path, { headers, signal: controller.signal });
    } finally {
      window.clearTimeout(timeout);
    }
  };

  try {
    let res = await fetchWithTimeout();
    if (res.status === 401) {
      const bearer = typeof window !== "undefined"
        ? ((window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string) || ""
        : "";
      if (bearer) res = await fetchWithTimeout({ Authorization: `Bearer ${bearer}` });
    }
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function fmt(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

const nav = [
  ["dashboard", "🏠", "Dashboard"],
  ["chat", "💬", "Chat"],
  ["studio", "🎬", "Studio"],
  ["repo", "🧭", "Local Repo"],
  ["fusion", "🧬", "Fusion"],
  ["sessions", "📋", "Sessions"],
  ["models", "🧠", "Models"],
  ["skills", "🧩", "Skills"],
  ["plugins", "🔌", "Plugins"],
  ["cron", "⏱", "Cron"],
  ["logs", "📜", "Logs"],
  ["config", "⚙", "Config"],
] as const;

const panelRoutes: Record<string, string> = {
  chat: "/chat",
  studio: "/studio",
  sessions: "/sessions",
  models: "/models",
  skills: "/skills",
  plugins: "/plugins",
  cron: "/cron",
  logs: "/logs",
  config: "/config",
};

export default function MuseOmniPage() {
  const navigate = useNavigate();
  const [active, setActive] = useState<(typeof nav)[number][0]>("dashboard");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [data, setData] = useState<DashboardData>({
    status: null,
    model: null,
    sessions: [],
    skills: [],
    plugins: [],
    cron: [],
    analytics: null,
    repo: null,
    logs: [],
  });

  const refresh = useCallback(async () => {
    // Fetch critical readouts first. Some optional repo/log endpoints can be
    // slow inside the Docker dashboard; if they are requested concurrently on
    // first paint they can starve the model/status calls and leave Omni with
    // placeholder values. This ordering keeps the cockpit useful immediately.
    const [status, model, skills, cron] = await Promise.all([
      api<ApiStatus>("/api/status"),
      api<ModelInfo>("/api/model/info"),
      api<SkillItem[]>("/api/skills"),
      api<CronJob[]>("/api/cron/jobs"),
    ]);
    setData((prev) => ({
      ...prev,
      status,
      model,
      skills: Array.isArray(skills) ? skills : [],
      cron: Array.isArray(cron) ? cron : [],
    }));
    setLastUpdated(new Date());
    setLoading(false);

    const [sessions, plugins, analytics, repo, logs] = await Promise.all([
      api<SessionItem[]>("/api/sessions"),
      api<PluginItem[]>("/api/dashboard/plugins"),
      api<Analytics>("/api/analytics/usage"),
      api<RepoInfo>("/api/muse/repo"),
      api<{ lines?: string[] }>("/api/logs?limit=24"),
    ]);
    setData((prev) => ({
      ...prev,
      sessions: Array.isArray(sessions) ? sessions : [],
      plugins: Array.isArray(plugins) ? plugins : [],
      analytics,
      repo,
      logs: logs?.lines ?? [],
    }));
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const enabledSkills = data.skills.filter((s) => s.enabled !== false).length;
  const activeCron = data.cron.filter((j) => j.enabled).length;
  const totalTokens = (data.analytics?.totals?.total_input ?? 0) + (data.analytics?.totals?.total_output ?? 0);
  const modelName = data.model?.model || "unknown";
  const repoCounts = data.repo?.counts ?? {};

  const modelRows = useMemo(() => {
    const configured = data.analytics?.by_model ?? [];
    if (configured.length) return configured.slice(0, 5);
    return [
      { model: data.model?.model, sessions: data.sessions.length, total_tokens: totalTokens, cost: data.analytics?.totals?.total_estimated_cost ?? 0 },
    ];
  }, [data.analytics, data.model?.model, data.sessions.length, totalTokens]);

  const handleNav = (panel: (typeof nav)[number][0]) => {
    const route = panelRoutes[panel];
    if (route) navigate(route);
    else setActive(panel);
  };

  return (
    <div className="omni-live-shell">
      <style>{css}</style>
      <aside className="omni-rail">
        <div className="omni-brand">
          <div className="muse-orb" />
          <div>
            <div className="omni-wordmark">muse<span>omni</span></div>
            <div className="omni-subword">live local harness</div>
          </div>
        </div>
        <div className="omni-status-bar">
          <span className={`omni-dot ${data.status?.gateway_running ? "live" : "idle"}`} />
          {data.status?.gateway_state || (data.status?.gateway_running ? "running" : "stopped")}
          <span className="omni-version">v{data.status?.version || "—"}</span>
        </div>
        <div className="omni-nav-scroll">
          <div className="omni-group-label">Live Muse</div>
          {nav.map(([id, icon, label]) => (
            <button key={id} className={`omni-nav-item ${active === id ? "active" : ""}`} onClick={() => handleNav(id)}>
              <span className="omni-nav-icon">{icon}</span>{label}
              {id === "chat" && <span className="omni-nav-badge">{data.status?.active_sessions ?? 0}</span>}
              {id === "skills" && <span className="omni-nav-badge">{enabledSkills}</span>}
            </button>
          ))}
        </div>
        <div className="omni-rail-footer">
          <span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Syncing…"}</span>
          <button onClick={refresh}>Refresh</button>
        </div>
      </aside>

      <main className="omni-main">
        <header className="omni-topbar">
          <div>
            <div className="omni-topbar-title">Muse Omni</div>
            <div className="omni-topbar-breadcrumb">{data.repo?.root || "connected to local M.U.S.E repo"}</div>
          </div>
          <div className="omni-topbar-actions">
            <button className="omni-chip accent" onClick={() => navigate("/chat")}>Open Chat</button>
            <button className="omni-chip" onClick={() => navigate("/studio")}>Studio</button>
            <button className="omni-chip" onClick={refresh}>Live Refresh</button>
          </div>
        </header>

        <section className="omni-content">
          <div className="omni-content-inner">
            {loading ? <Loading /> : null}
            {!loading && active === "dashboard" && (
              <>
                <Hero modelName={modelName} repo={data.repo} status={data.status} />
                <div className="omni-grid-4">
                  <Metric label="Active sessions" value={fmt(data.status?.active_sessions)} tone="accent" />
                  <Metric label="Skills enabled" value={`${enabledSkills}/${data.skills.length}`} tone="ok" />
                  <Metric label="Cron live" value={`${activeCron}/${data.cron.length}`} tone="warn" />
                  <Metric label="Tokens observed" value={fmt(totalTokens)} tone="accent" />
                </div>
                <div className="omni-grid-2">
                  <Panel title="Fusion + Delegation" desc="Live dashboard config; no Anthropic active chain.">
                    <table className="omni-table"><tbody>
                      <Row k="Primary" v={`${data.model?.provider || "—"} / ${data.model?.model || "—"}`} />
                      <Row k="Context" v={`${fmt(data.model?.effective_context_length)} tokens`} />
                      <Row k="Tools" v={data.model?.capabilities?.supports_tools ? "enabled" : "unknown"} />
                      <Row k="Reasoning" v={data.model?.capabilities?.supports_reasoning ? "enabled" : "unknown"} />
                    </tbody></table>
                  </Panel>
                  <Panel title="Local Repo Health" desc="Read directly from the mounted M.U.S.E checkout.">
                    <table className="omni-table"><tbody>
                      <Row k="Branch" v={data.repo?.branch || "—"} />
                      <Row k="Commit" v={`${data.repo?.commit || "—"} ${data.repo?.commit_subject || ""}`} />
                      <Row k="Working tree" v={data.repo?.dirty ? `${data.repo.changed_count} changes` : "clean"} />
                      <Row k="Dashboard dist" v={data.repo?.surfaces?.dashboard_dist ? "built" : "missing"} />
                    </tbody></table>
                  </Panel>
                </div>
                <Panel title="Surfaces" desc="Everything here is connected to actual repo paths or dashboard APIs.">
                  <div className="omni-grid">
                    {Object.entries(data.repo?.surfaces ?? {}).map(([key, ok]) => (
                      <div className="omni-card" key={key}><div className="omni-card-title">{key}</div><span className={`omni-pill ${ok ? "ok" : "danger"}`}>{ok ? "available" : "missing"}</span></div>
                    ))}
                  </div>
                </Panel>
              </>
            )}
            {!loading && active === "repo" && (
              <>
                <h1 className="omni-panel-title">Local M.U.S.E Repository</h1>
                <p className="omni-panel-desc">Direct readout from the mounted local repository. No mock build/version/counter values.</p>
                <div className="omni-grid-3">
                  {Object.entries(repoCounts).map(([key, value]) => <Metric key={key} label={key} value={fmt(value)} tone="accent" />)}
                </div>
                <div className="omni-grid-2">
                  {Object.entries(data.repo?.packages ?? {}).map(([name, pkg]) => (
                    <Panel key={name} title={`${name} package`} desc={`${pkg.name || "unnamed"} ${pkg.version || ""}`}>
                      <div className="omni-actions small">
                        {(pkg.scripts ?? []).slice(0, 12).map((s) => <span className="omni-chip" key={s}>{s}</span>)}
                      </div>
                      <div className="omni-card-meta">dependencies {pkg.dependencies ?? 0} · dev {pkg.dev_dependencies ?? 0}</div>
                    </Panel>
                  ))}
                </div>
                {data.repo?.changed_preview?.length ? <Panel title="Working tree preview" desc="First local changes from git status --short."><pre className="omni-code">{data.repo.changed_preview.join("\n")}</pre></Panel> : null}
              </>
            )}
            {!loading && active === "fusion" && (
              <>
                <h1 className="omni-panel-title">Fusion Harness</h1>
                <p className="omni-panel-desc">Primary model and observed usage from live APIs.</p>
                <div className="omni-grid-2">
                  <Panel title="Runtime Model" desc="/api/model/info">
                    <table className="omni-table"><tbody>
                      <Row k="Provider" v={data.model?.provider || "—"} />
                      <Row k="Model" v={data.model?.model || "—"} />
                      <Row k="Context" v={fmt(data.model?.effective_context_length)} />
                    </tbody></table>
                  </Panel>
                  <Panel title="Usage by Model" desc="/api/analytics/usage">
                    <table className="omni-table"><tbody>{modelRows.map((m, i) => <Row key={i} k={m.model || "unknown"} v={`${fmt(m.total_tokens ?? m.tokens)} tokens · ${m.sessions ?? 0} sessions`} />)}</tbody></table>
                  </Panel>
                </div>
              </>
            )}
            {!loading && active === "logs" && (
              <Panel title="Live Logs" desc="Latest dashboard log lines."><div>{data.logs.map((line, i) => <div className="omni-log-line" key={i}><span className="omni-log-time">{i + 1}</span><span className="omni-log-msg">{line}</span></div>)}</div></Panel>
            )}
            {!loading && active !== "dashboard" && active !== "repo" && active !== "fusion" && active !== "logs" && (
              <Panel title={active} desc="This surface opens as a first-class dashboard route.">
                <button className="omni-action-btn" onClick={() => navigate(panelRoutes[active] || "/chat")}>Open {active}<span>↗</span></button>
              </Panel>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function Loading() {
  return <div className="omni-grid-3"><div className="omni-card shimmer"/><div className="omni-card shimmer"/><div className="omni-card shimmer"/></div>;
}
function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="omni-card metric"><div className={`metric-value ${tone}`}>{value}</div><div className="metric-label">{label}</div></div>;
}
function Panel({ title, desc, children }: { title: string; desc?: string; children: ReactNode }) {
  return <section className="omni-card panel"><h2 className="omni-card-title">{title}</h2>{desc ? <p className="omni-card-meta">{desc}</p> : null}<div className="panel-body">{children}</div></section>;
}
function Row({ k, v }: { k: string; v: ReactNode }) { return <tr><th>{k}</th><td>{v}</td></tr>; }
function Hero({ modelName, repo, status }: { modelName: string; repo: RepoInfo | null; status: ApiStatus | null }) {
  return <section className="omni-hero">
    <div className="hero-copy">
      <div className="hero-kicker"><span className="kicker-dot"/>Private AI Command Center</div>
      <h1>Muse Omni</h1>
      <p>The live cockpit for M.U.S.E: chat, studio, models, repo intelligence, skills, jobs, and local runtime fused into one luminous operating surface.</p>
      <div className="omni-actions">
        <span className="omni-chip accent">{modelName}</span>
        <span className="omni-chip">{repo?.branch || "repo"}@{repo?.commit || "—"}</span>
        <span className={`omni-chip ${status?.gateway_running ? "ok" : ""}`}>{status?.gateway_running ? "gateway live" : "gateway stopped"}</span>
      </div>
    </div>
    <div className="hero-visual" aria-hidden="true">
      <div className="sacred-grid"><span/><span/><span/><span/><span/><span/></div>
      <div className="muse-orb hero-orb" />
      <div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="orbit orbit-c"/>
      <div className="hero-node n1"/><div className="hero-node n2"/><div className="hero-node n3"/>
    </div>
  </section>;
}

const css = `
:root{--void:#020305;--void-2:#06090d;--void-3:#0d1219;--glass:rgba(12,18,28,.62);--glass-strong:rgba(16,24,38,.78);--edge:rgba(203,225,255,.14);--edge-strong:rgba(203,225,255,.28);--core:#fffdf8;--signal:#f5f8ff;--signal-dim:#b8c4d8;--signal-mute:#76829a;--ring-1:#55f3ff;--ring-2:#b888ff;--ring-3:#ffd28a;--ring-4:#6dffa8;--ok:#65f2ad;--warn:#ffd166;--danger:#ff6575;--ring-grad:linear-gradient(120deg,var(--ring-1),var(--ring-2) 48%,var(--ring-3));--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:20px;--space-6:24px;--space-8:32px;--space-10:40px;--radius-sm:10px;--radius-md:16px;--radius-lg:24px;--radius-xl:34px;--radius-pill:9999px;--sans:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;--duration-fast:150ms;--duration:260ms;--easing-standard:cubic-bezier(.2,0,0,1)}
.omni-live-shell{position:relative;display:grid;grid-template-columns:304px minmax(0,1fr);height:100dvh;overflow:hidden;background:radial-gradient(circle at 16% 10%,rgba(85,243,255,.20),transparent 28%),radial-gradient(circle at 82% 14%,rgba(184,136,255,.18),transparent 30%),radial-gradient(circle at 58% 104%,rgba(255,210,138,.12),transparent 34%),linear-gradient(135deg,#020305 0%,#061017 46%,#020305 100%);color:var(--signal);font-family:var(--sans);font-size:14px;line-height:1.5;text-transform:none;isolation:isolate}.omni-live-shell::before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.022) 1px,transparent 1px);background-size:72px 72px;mask-image:radial-gradient(circle at 50% 20%,#000 0 54%,transparent 82%);opacity:.55;z-index:-2}.omni-live-shell::after{content:"";position:absolute;inset:-20%;pointer-events:none;background:conic-gradient(from 100deg at 50% 50%,transparent 0 16%,rgba(85,243,255,.11),transparent 29% 45%,rgba(184,136,255,.12),transparent 58% 100%);filter:blur(48px);animation:omniAurora 18s linear infinite;z-index:-3}.omni-live-shell *{box-sizing:border-box;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.18) transparent}.omni-live-shell button{font:inherit;color:inherit}.omni-live-shell button:focus-visible{outline:2px solid rgba(85,243,255,.65);outline-offset:3px}
.muse-orb{width:30px;height:30px;border-radius:var(--radius-pill);flex:none;background:radial-gradient(circle at 48% 38%,#fff 0 15%,rgba(255,255,255,.86) 21%,rgba(85,243,255,.45) 38%,transparent 62%);box-shadow:0 0 0 1px rgba(85,243,255,.42),0 0 28px rgba(85,243,255,.42),0 0 58px rgba(184,136,255,.28);position:relative}.muse-orb::before{content:"";position:absolute;inset:-8px;border:1px solid rgba(255,255,255,.16);border-radius:50%}.muse-orb::after{content:"";position:absolute;inset:-7px;border-radius:var(--radius-pill);background:conic-gradient(from 210deg,var(--ring-1),var(--ring-2),var(--ring-3),var(--ring-1));opacity:.38;filter:blur(7px);z-index:-1;animation:orbSpin 9s linear infinite}
.omni-rail{display:flex;flex-direction:column;min-height:0;margin:14px 0 14px 14px;border:1px solid var(--edge);border-radius:28px;background:linear-gradient(180deg,rgba(10,16,25,.86),rgba(7,9,14,.74));box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 24px 80px rgba(0,0,0,.44);backdrop-filter:blur(24px) saturate(150%);overflow:hidden}.omni-brand{display:flex;align-items:center;gap:var(--space-3);padding:22px 20px;border-bottom:1px solid var(--edge);background:linear-gradient(180deg,rgba(255,255,255,.055),transparent)}.omni-wordmark{font-weight:780;font-size:1.15rem;color:var(--signal);letter-spacing:-.035em}.omni-wordmark span{background:var(--ring-grad);-webkit-background-clip:text;background-clip:text;color:transparent;margin-left:4px}.omni-subword{font-size:10px;color:var(--signal-mute);letter-spacing:.14em;text-transform:uppercase}.omni-status-bar{display:flex;align-items:center;gap:var(--space-2);margin:14px 14px 8px;padding:10px 12px;border:1px solid var(--edge);border-radius:999px;background:rgba(255,255,255,.04);font-size:11px;color:var(--signal-dim);box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}.omni-dot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--signal-mute)}.omni-dot.live{background:var(--ok);box-shadow:0 0 0 5px rgba(101,242,173,.10),0 0 18px var(--ok);animation:livePulse 2.4s ease-in-out infinite}.omni-dot.idle{background:var(--warn);box-shadow:0 0 14px rgba(255,209,102,.4)}.omni-version{margin-left:auto;opacity:.72;font-family:var(--mono)}.omni-nav-scroll{flex:1 1 auto;min-height:0;overflow-y:auto;padding:8px 10px 14px}.omni-group-label{padding:12px 12px 8px;font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:var(--signal-mute)}.omni-nav-item{position:relative;width:100%;display:flex;align-items:center;gap:11px;padding:11px 12px;margin:3px 0;border:1px solid transparent;border-radius:16px;background:transparent;color:var(--signal-dim);cursor:pointer;text-align:left;transition:transform var(--duration) var(--easing-standard),background var(--duration) var(--easing-standard),border-color var(--duration) var(--easing-standard),color var(--duration) var(--easing-standard),box-shadow var(--duration) var(--easing-standard)}.omni-nav-item::before{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(120deg,rgba(85,243,255,.16),rgba(184,136,255,.13));opacity:0;transition:opacity var(--duration) var(--easing-standard)}.omni-nav-item:hover{transform:translateX(4px);color:var(--signal);background:rgba(255,255,255,.045);border-color:rgba(255,255,255,.08)}.omni-nav-item.active{color:var(--core);border-color:rgba(85,243,255,.34);background:linear-gradient(120deg,rgba(85,243,255,.14),rgba(184,136,255,.12));box-shadow:0 12px 32px rgba(85,243,255,.08),inset 0 1px 0 rgba(255,255,255,.08)}.omni-nav-item.active::before{opacity:1}.omni-nav-icon,.omni-nav-badge{position:relative}.omni-nav-icon{font-size:16px}.omni-nav-badge{margin-left:auto;min-width:22px;padding:1px 7px;border-radius:999px;background:rgba(255,255,255,.08);font-family:var(--mono);font-size:10px;color:var(--signal)}.omni-rail-footer{display:flex;align-items:center;gap:10px;padding:14px;border-top:1px solid var(--edge);color:var(--signal-mute);font-size:11px}.omni-rail-footer span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.omni-rail-footer button,.omni-chip,.omni-action-btn{border:1px solid var(--edge);border-radius:999px;background:rgba(255,255,255,.055);box-shadow:inset 0 1px 0 rgba(255,255,255,.08);cursor:pointer;transition:transform var(--duration) var(--easing-standard),border-color var(--duration) var(--easing-standard),box-shadow var(--duration) var(--easing-standard),background var(--duration) var(--easing-standard)}.omni-rail-footer button{margin-left:auto;padding:7px 10px;color:var(--signal-dim)}.omni-rail-footer button:hover,.omni-chip:hover,.omni-action-btn:hover{transform:translateY(-1px);border-color:var(--edge-strong);box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 12px 30px rgba(85,243,255,.08)}
.omni-main{min-width:0;display:flex;flex-direction:column;min-height:0;padding:14px}.omni-topbar{height:76px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 10px 14px}.omni-topbar-title{font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:var(--signal-mute);font-weight:720}.omni-topbar-breadcrumb{max-width:72vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--signal-dim);font-family:var(--mono);font-size:12px}.omni-topbar-actions{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.omni-chip{display:inline-flex;align-items:center;gap:8px;padding:9px 13px;color:var(--signal-dim);font-size:12px;white-space:nowrap}.omni-chip.accent{color:#041014;border-color:rgba(85,243,255,.55);background:linear-gradient(120deg,var(--ring-1),var(--ring-2));box-shadow:0 18px 42px rgba(85,243,255,.18)}.omni-chip.ok{color:#052115;border-color:rgba(101,242,173,.55);background:linear-gradient(120deg,var(--ok),#b5ffd1)}.omni-content{min-height:0;flex:1;overflow:auto;border:1px solid var(--edge);border-radius:34px;background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.025));box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 30px 100px rgba(0,0,0,.38);backdrop-filter:blur(24px) saturate(160%)}.omni-content-inner{max-width:1480px;margin:0 auto;padding:24px;width:100%;animation:pageIn .44s var(--easing-standard)}
.omni-hero{position:relative;display:grid;grid-template-columns:minmax(0,1.12fr) minmax(330px,.88fr);gap:24px;min-height:360px;margin-bottom:22px;padding:34px;border:1px solid rgba(255,255,255,.12);border-radius:34px;background:radial-gradient(circle at 22% 18%,rgba(85,243,255,.24),transparent 35%),radial-gradient(circle at 92% 20%,rgba(184,136,255,.24),transparent 34%),linear-gradient(135deg,rgba(255,255,255,.10),rgba(255,255,255,.035));box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 30px 90px rgba(0,0,0,.32);overflow:hidden}.omni-hero::before{content:"";position:absolute;inset:1px;border-radius:33px;border:1px solid rgba(255,255,255,.06);pointer-events:none}.hero-copy{position:relative;z-index:2;align-self:center}.hero-kicker{display:inline-flex;align-items:center;gap:9px;margin-bottom:16px;padding:7px 11px;border:1px solid rgba(255,255,255,.12);border-radius:999px;background:rgba(255,255,255,.06);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--signal-dim)}.kicker-dot{width:7px;height:7px;border-radius:50%;background:var(--ring-1);box-shadow:0 0 18px var(--ring-1)}.omni-hero h1{margin:0;font-size:clamp(56px,8vw,116px);line-height:.86;letter-spacing:-.095em;font-weight:850;background:linear-gradient(100deg,#fff,var(--ring-1) 34%,var(--ring-2) 68%,#fff0d1);-webkit-background-clip:text;background-clip:text;color:transparent;text-shadow:0 0 70px rgba(85,243,255,.22)}.omni-hero p{max-width:720px;margin:22px 0 24px;color:var(--signal-dim);font-size:clamp(16px,1.5vw,21px);line-height:1.65}.omni-actions{display:flex;flex-wrap:wrap;gap:10px}.hero-visual{position:relative;min-height:290px;display:grid;place-items:center}.hero-orb{width:118px;height:118px;box-shadow:0 0 0 1px rgba(85,243,255,.58),0 0 70px rgba(85,243,255,.62),0 0 150px rgba(184,136,255,.45)}.hero-orb::before{inset:-18px}.hero-orb::after{inset:-22px;filter:blur(18px)}.orbit{position:absolute;border-radius:50%;border:1px solid rgba(255,255,255,.16);box-shadow:inset 0 0 60px rgba(85,243,255,.04)}.orbit-a{width:230px;height:230px;animation:orbSpin 22s linear infinite}.orbit-b{width:320px;height:150px;transform:rotate(-26deg);border-color:rgba(85,243,255,.23);animation:orbitWobble 13s ease-in-out infinite}.orbit-c{width:160px;height:330px;transform:rotate(32deg);border-color:rgba(255,210,138,.18);animation:orbitWobble 16s ease-in-out infinite reverse}.sacred-grid{position:absolute;inset:18px;opacity:.55}.sacred-grid span{position:absolute;width:98px;height:98px;border:1px solid rgba(255,255,255,.10);border-radius:50%;mix-blend-mode:screen}.sacred-grid span:nth-child(1){left:34%;top:18%}.sacred-grid span:nth-child(2){left:45%;top:18%}.sacred-grid span:nth-child(3){left:39%;top:34%}.sacred-grid span:nth-child(4){left:28%;top:34%}.sacred-grid span:nth-child(5){left:50%;top:34%}.sacred-grid span:nth-child(6){left:39%;top:50%}.hero-node{position:absolute;width:10px;height:10px;border-radius:50%;background:#fff;box-shadow:0 0 18px currentColor}.n1{color:var(--ring-1);top:22%;left:29%;animation:float 5.5s ease-in-out infinite}.n2{color:var(--ring-2);right:18%;top:46%;animation:float 6s ease-in-out infinite .6s}.n3{color:var(--ring-3);bottom:20%;left:49%;animation:float 7s ease-in-out infinite 1.2s}
.omni-grid,.omni-grid-2,.omni-grid-3,.omni-grid-4{display:grid;gap:16px}.omni-grid{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}.omni-grid-2{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:16px}.omni-grid-3{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:16px}.omni-grid-4{grid-template-columns:repeat(4,minmax(0,1fr));margin-top:16px}.omni-card{position:relative;min-width:0;border:1px solid var(--edge);border-radius:24px;background:linear-gradient(180deg,rgba(255,255,255,.075),rgba(255,255,255,.035));box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 18px 48px rgba(0,0,0,.24);overflow:hidden}.omni-card::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 24% 0,rgba(85,243,255,.10),transparent 36%);opacity:.75;pointer-events:none}.omni-card.metric{padding:22px;transition:transform var(--duration) var(--easing-standard),border-color var(--duration) var(--easing-standard),background var(--duration) var(--easing-standard)}.omni-card.metric:hover{transform:translateY(-3px);border-color:var(--edge-strong);background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.04))}.metric-value{position:relative;font-size:clamp(30px,3.8vw,48px);line-height:1;font-weight:820;letter-spacing:-.07em;color:var(--signal)}.metric-value.accent{background:var(--ring-grad);-webkit-background-clip:text;background-clip:text;color:transparent}.metric-value.ok{color:var(--ok)}.metric-value.warn{color:var(--warn)}.metric-label{position:relative;margin-top:8px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--signal-mute)}.panel{padding:22px}.omni-card-title{position:relative;margin:0;color:var(--signal);font-size:18px;letter-spacing:-.025em;font-weight:760}.omni-card-meta{position:relative;margin:7px 0 0;color:var(--signal-mute);font-size:12px}.panel-body{position:relative;margin-top:18px}.omni-panel-title{margin:0 0 8px;font-size:clamp(34px,4vw,62px);line-height:1;letter-spacing:-.06em}.omni-panel-desc{margin:0 0 20px;color:var(--signal-dim);font-size:16px}.omni-table{width:100%;border-collapse:collapse}.omni-table th,.omni-table td{padding:12px 0;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top}.omni-table tr:last-child th,.omni-table tr:last-child td{border-bottom:0}.omni-table th{text-align:left;color:var(--signal-mute);font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:650}.omni-table td{text-align:right;color:var(--signal);font-family:var(--mono);font-size:12px;max-width:420px;overflow-wrap:anywhere}.omni-pill{display:inline-flex;padding:6px 10px;border-radius:999px;border:1px solid var(--edge);font-size:11px;color:var(--signal-dim);background:rgba(255,255,255,.05)}.omni-pill.ok{color:var(--ok);border-color:rgba(101,242,173,.28);background:rgba(101,242,173,.08)}.omni-pill.danger{color:var(--danger);border-color:rgba(255,101,117,.28);background:rgba(255,101,117,.08)}.omni-actions.small{gap:8px}.omni-actions.small .omni-chip{padding:6px 9px;font-size:11px}.omni-code{margin:0;padding:16px;border:1px solid rgba(255,255,255,.10);border-radius:18px;background:rgba(0,0,0,.32);color:var(--signal-dim);font-family:var(--mono);font-size:12px;overflow:auto}.omni-log-line{display:grid;grid-template-columns:42px minmax(0,1fr);gap:12px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.07);font-family:var(--mono);font-size:12px}.omni-log-line:last-child{border-bottom:0}.omni-log-time{color:var(--ring-1);opacity:.8}.omni-log-msg{color:var(--signal-dim);overflow-wrap:anywhere}.omni-action-btn{display:inline-flex;align-items:center;gap:12px;padding:13px 16px;border-radius:16px;color:var(--signal);background:linear-gradient(120deg,rgba(85,243,255,.12),rgba(184,136,255,.10))}.shimmer{height:170px;background:linear-gradient(90deg,rgba(255,255,255,.04),rgba(255,255,255,.10),rgba(255,255,255,.04));background-size:220% 100%;animation:shimmer 1.3s linear infinite}
@keyframes omniAurora{to{transform:rotate(360deg)}}@keyframes orbSpin{to{transform:rotate(360deg)}}@keyframes livePulse{0%,100%{transform:scale(1);box-shadow:0 0 0 4px rgba(101,242,173,.09),0 0 18px var(--ok)}50%{transform:scale(1.18);box-shadow:0 0 0 8px rgba(101,242,173,.05),0 0 24px var(--ok)}}@keyframes pageIn{from{opacity:0;transform:translateY(10px) scale(.995)}to{opacity:1;transform:none}}@keyframes shimmer{to{background-position:-220% 0}}@keyframes float{0%,100%{transform:translate3d(0,0,0)}50%{transform:translate3d(0,-14px,0)}}@keyframes orbitWobble{0%,100%{scale:1;opacity:.9}50%{scale:1.04;opacity:.62}}
@media (max-width:1180px){.omni-live-shell{grid-template-columns:248px minmax(0,1fr)}.omni-hero{grid-template-columns:1fr}.hero-visual{min-height:240px}.omni-grid-4{grid-template-columns:repeat(2,minmax(0,1fr))}.omni-grid-2{grid-template-columns:1fr}}
@media (max-width:780px){.omni-live-shell{display:block;overflow:auto;height:auto;min-height:100dvh}.omni-rail{margin:10px;border-radius:24px;max-height:none}.omni-main{padding:10px}.omni-topbar{height:auto;align-items:flex-start;flex-direction:column;padding:4px 4px 12px}.omni-content{border-radius:26px}.omni-content-inner{padding:14px}.omni-hero{padding:22px;border-radius:26px}.omni-hero h1{font-size:56px}.hero-visual{display:none}.omni-grid-3,.omni-grid-4{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){.omni-live-shell::after,.muse-orb::after,.orbit,.hero-node,.omni-dot.live,.shimmer{animation:none!important}.omni-nav-item,.omni-chip,.omni-card.metric,.omni-action-btn{transition:none!important}}

`;
