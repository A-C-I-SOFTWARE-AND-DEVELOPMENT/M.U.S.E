import { useEffect, useMemo, useState } from "react";
import { fetchJSON } from "@/lib/api";
import { formatRelativeTime, normalizeNdStatus } from "./useNightdesk";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Model router · Orchestration
// GET /api/nightdesk/orchestration → {jobs, subagents, kanban, note}
// Active job section (running first) with status chips; subagent roster
// (sa- delegation ids in mono + state chips); kanban counts summary.
// Empty states stay honest — no fabricated activity.
// ---------------------------------------------------------------------------

interface OrchJob {
  id: string;
  title: string;
  status: string;
  created_at: number | null;
  updated_at: number | null;
  source: string;
}

interface SubagentRow {
  delegation_id: string;
  origin_session: string | null;
  state: string;
  dispatched_at: number | null;
  completed_at: number | null;
}

interface KanbanSummary {
  available: boolean;
  path?: string;
  counts?: Record<string, number>;
  total?: number;
}

interface OrchestrationPayload {
  jobs: OrchJob[];
  subagents: SubagentRow[];
  kanban: KanbanSummary;
  note?: string;
}

const RUNNING = new Set(["running", "in_progress", "active", "dispatched"]);
const WAITING = new Set(["queued", "pending", "created"]);

function jobRank(status: string): number {
  const s = status.toLowerCase();
  if (RUNNING.has(s)) return 0;
  if (WAITING.has(s)) return 1;
  return 2;
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h3 className="nd-label" style={{ margin: "0 0 6px", fontSize: 9 }}>
      {children}
    </h3>
  );
}

const rowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  padding: "5px 0",
  borderBottom: "1px solid var(--nd-hairline)",
};

export default function OrchestrationCard() {
  const [data, setData] = useState<OrchestrationPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJSON<OrchestrationPayload>("/api/nightdesk/orchestration")
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const jobs = useMemo(() => {
    return [...(data?.jobs ?? [])].sort((a, b) => {
      const r = jobRank(a.status) - jobRank(b.status);
      if (r !== 0) return r;
      return (b.created_at ?? 0) - (a.created_at ?? 0);
    });
  }, [data]);

  const subagents = data?.subagents ?? [];
  const kanban = data?.kanban;
  const kanbanCounts = Object.entries(kanban?.counts ?? {});

  return (
    <section className="nd-panel">
      <header className="nd-panel-head">
        <h2 className="nd-label">Orchestration</h2>
        {data && (
          <span className="nd-sub" style={{ fontSize: 10 }}>
            <span className="nd-num">{jobs.length}</span> jobs ·{" "}
            <span className="nd-num">{subagents.length}</span> subagents
          </span>
        )}
      </header>
      <div className="nd-panel-body">
        {error ? (
          <p className="nd-empty">orchestration unavailable — {error}</p>
        ) : !data ? (
          <p className="nd-empty">loading orchestration…</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* jobs — running first */}
            <div>
              <SectionLabel>Jobs</SectionLabel>
              {jobs.length === 0 ? (
                <p className="nd-empty" style={{ padding: "10px 0" }}>
                  no orchestration jobs yet — start one from the TUI
                </p>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {jobs.slice(0, 8).map((job) => (
                    <li key={`${job.source}:${job.id}`} style={rowStyle}>
                      <span
                        className="nd-chip"
                        data-status={normalizeNdStatus(job.status)}
                      >
                        {job.status}
                      </span>
                      <span
                        style={{
                          flex: 1,
                          minWidth: 0,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          fontSize: 11,
                          color: "var(--nd-fg)",
                        }}
                        title={job.title || job.id}
                      >
                        {job.title || job.id}
                      </span>
                      <span
                        className="nd-mono"
                        style={{
                          flex: "none",
                          fontSize: 9,
                          letterSpacing: "0.12em",
                          textTransform: "uppercase",
                          color: "var(--nd-fg-faint)",
                        }}
                      >
                        {job.source}
                      </span>
                      <span
                        className="nd-num"
                        style={{
                          width: 64,
                          flex: "none",
                          textAlign: "right",
                          fontSize: 10,
                          color: "var(--nd-fg-faint)",
                        }}
                      >
                        {formatRelativeTime(job.updated_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {jobs.length > 8 && (
                <p className="nd-sub" style={{ marginTop: 4, fontSize: 9 }}>
                  showing 8 of {jobs.length}
                </p>
              )}
            </div>

            {/* subagent roster */}
            <div>
              <SectionLabel>Subagent roster</SectionLabel>
              {subagents.length === 0 ? (
                <p className="nd-empty" style={{ padding: "10px 0" }}>
                  no subagent delegations recorded
                </p>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {subagents.slice(0, 6).map((sa) => (
                    <li key={sa.delegation_id} style={rowStyle}>
                      <span
                        className="nd-mono"
                        style={{ flex: "none", color: "var(--nd-fg)" }}
                      >
                        {sa.delegation_id}
                      </span>
                      <span
                        className="nd-chip"
                        data-status={normalizeNdStatus(sa.state)}
                      >
                        {sa.state}
                      </span>
                      <span
                        className="nd-mono"
                        style={{
                          flex: 1,
                          minWidth: 0,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          fontSize: 10,
                          color: "var(--nd-fg-faint)",
                        }}
                        title={sa.origin_session ?? undefined}
                      >
                        {sa.origin_session ?? ""}
                      </span>
                      <span
                        className="nd-num"
                        style={{
                          width: 64,
                          flex: "none",
                          textAlign: "right",
                          fontSize: 10,
                          color: "var(--nd-fg-faint)",
                        }}
                      >
                        {formatRelativeTime(sa.dispatched_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {subagents.length > 6 && (
                <p className="nd-sub" style={{ marginTop: 4, fontSize: 9 }}>
                  showing 6 of {subagents.length}
                </p>
              )}
            </div>

            {/* kanban summary */}
            <div>
              <SectionLabel>Kanban</SectionLabel>
              {!kanban?.available ? (
                <p className="nd-empty" style={{ padding: "10px 0" }}>
                  kanban unavailable — no kanban.db found
                </p>
              ) : kanbanCounts.length === 0 ? (
                <p className="nd-empty" style={{ padding: "10px 0" }}>
                  kanban empty — no tasks tracked
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  {kanbanCounts.map(([status, n]) => (
                    <span className="nd-chip" key={status}>
                      {status}
                      <span className="nd-num" style={{ color: "var(--nd-fg)" }}>
                        {n}
                      </span>
                    </span>
                  ))}
                  <span
                    className="nd-sub"
                    style={{ marginLeft: 4, fontSize: 10 }}
                  >
                    total{" "}
                    <span className="nd-num">
                      {kanban.total ??
                        kanbanCounts.reduce((s, [, n]) => s + n, 0)}
                    </span>
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
        {data?.note && !error && (
          <p
            className="nd-sub"
            style={{
              marginTop: 10,
              paddingTop: 8,
              borderTop: "1px solid var(--nd-hairline)",
              fontSize: 10,
              lineHeight: 1.5,
            }}
          >
            {data.note}
          </p>
        )}
      </div>
    </section>
  );
}
