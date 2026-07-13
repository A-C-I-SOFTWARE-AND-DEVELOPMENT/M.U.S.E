/**
 * Agent Workshop — launch coding agents, view live logs, pause/resume/cancel.
 *
 * Uses the gateway's orchestrator endpoint (POST /v1/cockpit/orchestrate) to
 * create jobs, the jobs stream (GET /v1/cockpit/jobs/stream) for live updates,
 * and individual job control endpoints (pause/resume/cancel). Job logs stream
 * via the same SSE path used by the Jobs view.
 *
 * This is a route registered via the append-only registry.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  getToken,
  TOKEN_EVENT,
  subscribeJobs,
  type CockpitJob,
} from "../lib/gateway";

type LogEntry = {
  ts: string;
  level: string;
  message: string;
};

type WorkerLane = {
  id: string;
  display_name: string;
  requires_approval: boolean;
};

export function AgentWorkshop() {
  const [jobs, setJobs] = useState<CockpitJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [lanes, setLanes] = useState<WorkerLane[]>([]);
  const [laneId, setLaneId] = useState("hermes-local-planner");
  const [authorization, setAuthorization] = useState("");
  const [launching, setLaunching] = useState(false);
  const [logs, setLogs] = useState<Record<string, LogEntry[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));
  const logRef = useRef<HTMLDivElement | null>(null);

  // Subscribe to the jobs stream
  useEffect(() => {
    const refreshPaired = () => setPaired(Boolean(getToken()));
    window.addEventListener("storage", refreshPaired);
    window.addEventListener(TOKEN_EVENT, refreshPaired);

    const loadLanes = async () => {
      try {
        const r = await api("/v1/cockpit/jobs/lanes");
        const d = await r.json().catch(() => ({ lanes: [] }));
        if (r.ok && Array.isArray(d.lanes)) {
          const available = d.lanes.filter((lane: WorkerLane) => lane.id);
          setLanes(available);
          if (available.length && !available.some((lane: WorkerLane) => lane.id === laneId)) {
            setLaneId(available[0].id);
          }
        }
      } catch {
        setError("Worker lanes are unavailable. Check the local gateway.");
      }
    };
    if (getToken()) void loadLanes();

    const unsub = subscribeJobs({
      onUpsert: (job) => {
        setJobs((prev) => {
          const idx = prev.findIndex((j) => j.id === job.id);
          if (idx >= 0) {
            const next = prev.slice();
            next[idx] = { ...next[idx], ...job };
            return next;
          }
          return [...prev, job];
        });
      },
      onRemoved: (id) => {
        setJobs((prev) => prev.filter((j) => j.id !== id));
      },
    });

    return () => {
      unsub();
      window.removeEventListener("storage", refreshPaired);
      window.removeEventListener(TOKEN_EVENT, refreshPaired);
    };
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs, selectedJobId]);

  // Poll for job logs on the selected job
  useEffect(() => {
    if (!selectedJobId || !paired) return;
    let alive = true;

    const poll = async () => {
      try {
        const r = await api(`/v1/cockpit/jobs/${selectedJobId}/ledger`);
        if (!r.ok || !alive) return;
        const d = await r.json().catch(() => ({}));
        const rawEntries = Array.isArray(d.timeline)
          ? d.timeline
          : Array.isArray(d.ledger)
            ? d.ledger
            : Array.isArray(d.events)
              ? d.events
              : [];
        setLogs((prev) => ({
          ...prev,
          [selectedJobId]: rawEntries.map((e: Record<string, unknown>) => ({
            ts: String(e.ts ?? e.timestamp ?? e.created_at ?? ""),
            level: String(e.level ?? e.status ?? "info"),
            message: String(e.message ?? e.summary ?? e.kind ?? e.event ?? "Activity recorded"),
          })),
        }));
      } catch {
        /* offline or endpoint not available */
      }
    };

    void poll();
    const t = setInterval(poll, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [selectedJobId, paired]);

  const launch = useCallback(async () => {
    const p = prompt.trim();
    if (!p || launching) return;
    setLaunching(true);
    setError(null);
    try {
      const r = await api("/v1/cockpit/orchestrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: p }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(d.error || `Failed to create job (HTTP ${r.status})`);
      } else {
        const jobId = String(d.id || d.job_id || "");
        if (!jobId) throw new Error("Gateway created a job without an id");
        const run = await api(`/v1/cockpit/jobs/${jobId}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ worker_id: laneId, authorization }),
        });
        const runBody = await run.json().catch(() => ({}));
        if (!run.ok) {
          setError(runBody.error || `Job created but could not start (HTTP ${run.status})`);
        } else {
          setPrompt("");
          setAuthorization("");
          setSelectedJobId(jobId);
        }
      }
    } catch (e) {
      setError(String(e));
    }
    setLaunching(false);
  }, [prompt, launching, laneId, authorization]);

  const controlJob = useCallback(
    async (jobId: string, action: "pause" | "resume" | "cancel") => {
      try {
        const r = await api(`/v1/cockpit/jobs/${jobId}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          setError(d.error || `${action} failed (HTTP ${r.status})`);
        }
      } catch (e) {
        setError(String(e));
      }
    },
    [],
  );

  const activeJobs = jobs.filter(
    (j) =>
      j.status === "running" ||
      j.status === "pending" ||
      j.status === "queued",
  );
  const doneJobs = jobs.filter(
    (j) =>
      j.status !== "running" &&
      j.status !== "pending" &&
      j.status !== "queued",
  );

  const selectedJob = jobs.find((j) => j.id === selectedJobId);
  const selectedLogs = selectedJobId ? logs[selectedJobId] || [] : [];
  const selectedLane = lanes.find((lane) => lane.id === laneId);
  const authorizationRequired = selectedLane?.requires_approval === true;

  if (!paired) {
    return (
      <div className="view">
        <div className="card notice">
          Pair this device in <b>Settings</b> to use the Agent Workshop.
        </div>
      </div>
    );
  }

  return (
    <div className="view">
      <div className="section-header">
        <div>
          <div className="eyebrow">Agent Workshop</div>
          <h2 className="section-title">Launch & Control Coding Agents</h2>
        </div>
        <div className="trailing">
          <span className="pill accent">{activeJobs.length} active</span>
          <span className="pill">{doneJobs.length} done</span>
        </div>
      </div>

      {/* Launch form */}
      <div className="card">
        <div className="row" style={{ gap: "8px", alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label className="eyebrow">Goal / Prompt</label>
            <textarea
              rows={3}
              style={{ width: "100%", resize: "vertical" }}
              placeholder="e.g. Create a React todo app with TypeScript and Tailwind…"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  void launch();
                }
              }}
            />
          </div>
          <div style={{ minWidth: "210px" }}>
            <label className="eyebrow" htmlFor="worker-lane">Worker lane</label>
            <select
              id="worker-lane"
              value={laneId}
              onChange={(e) => setLaneId(e.target.value)}
              disabled={launching || lanes.length === 0}
              style={{ width: "100%" }}
            >
              {lanes.length === 0 ? (
                <option value="hermes-local-planner">No lanes available</option>
              ) : (
                lanes.map((lane) => (
                  <option key={lane.id} value={lane.id}>
                    {lane.display_name}{lane.requires_approval ? " · approval" : ""}
                  </option>
                ))
              )}
            </select>
            {authorizationRequired && (
              <input
                type="password"
                value={authorization}
                onChange={(e) => setAuthorization(e.target.value)}
                placeholder="Owner authorization phrase"
                autoComplete="off"
                style={{ width: "100%", marginTop: "8px" }}
              />
            )}
          </div>
          <button
            className="primary"
            onClick={() => void launch()}
            disabled={
              launching ||
              !prompt.trim() ||
              lanes.length === 0 ||
              (authorizationRequired && !authorization.trim())
            }
          >
            {launching ? "Launching…" : "Launch Agent"}
          </button>
        </div>
        {error && (
          <div className="card danger-card" style={{ marginTop: "10px" }}>
            {error}
          </div>
        )}
        <div className="hint">
          Ctrl+Enter to launch. Agents run autonomously with tool access.
        </div>
      </div>

      {/* Job list + detail split */}
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "12px", marginTop: "12px" }}>
        {/* Job list */}
        <div className="card" style={{ padding: "8px" }}>
          {jobs.length === 0 ? (
            <div className="empty" style={{ padding: "20px 10px" }}>
              No agents yet. Launch one above.
            </div>
          ) : (
            <>
              {activeJobs.length > 0 && (
                <>
                  <div className="eyebrow" style={{ padding: "6px 8px" }}>Active</div>
                  {activeJobs.map((job) => (
                    <JobRow
                      key={job.id}
                      job={job}
                      selected={job.id === selectedJobId}
                      onClick={() => setSelectedJobId(job.id)}
                      onControl={controlJob}
                    />
                  ))}
                </>
              )}
              {doneJobs.length > 0 && (
                <>
                  <div className="eyebrow" style={{ padding: "6px 8px", marginTop: "8px" }}>Completed</div>
                  {doneJobs.slice(0, 20).map((job) => (
                    <JobRow
                      key={job.id}
                      job={job}
                      selected={job.id === selectedJobId}
                      onClick={() => setSelectedJobId(job.id)}
                      onControl={controlJob}
                    />
                  ))}
                </>
              )}
            </>
          )}
        </div>

        {/* Detail / logs */}
        <div className="card" style={{ minHeight: "300px", display: "flex", flexDirection: "column" }}>
          {selectedJob ? (
            <>
              <div className="row" style={{ marginBottom: "8px" }}>
                <span className="mono" style={{ fontSize: "11px", color: "var(--signal-mute)" }}>
                  {selectedJob.id}
                </span>
                <span className={"pill " + statusPillClass(selectedJob.status)}>
                  {selectedJob.status || "unknown"}
                </span>
                {selectedJob.title && (
                  <span style={{ color: "var(--signal-dim)" }}>{selectedJob.title}</span>
                )}
                <div style={{ flex: 1 }} />
                {selectedJob.status === "running" && (
                  <>
                    <button onClick={() => void controlJob(selectedJob.id, "pause")}>
                      Pause
                    </button>
                    <button className="danger" onClick={() => void controlJob(selectedJob.id, "cancel")}>
                      Cancel
                    </button>
                  </>
                )}
                {selectedJob.status === "paused" && (
                  <button className="primary" onClick={() => void controlJob(selectedJob.id, "resume")}>
                    Resume
                  </button>
                )}
              </div>
              <div
                ref={logRef}
                style={{
                  flex: 1,
                  overflowY: "auto",
                  fontFamily: "var(--mono)",
                  fontSize: "12px",
                  background: "var(--void)",
                  borderRadius: "8px",
                  padding: "10px",
                  border: "1px solid var(--edge)",
                }}
              >
                {selectedLogs.length === 0 ? (
                  <div className="empty" style={{ color: "var(--signal-mute)" }}>
                    No logs yet. Logs appear here as the agent works.
                  </div>
                ) : (
                  selectedLogs.map((log, i) => (
                    <div key={i} style={{ marginBottom: "2px" }}>
                      {log.ts && (
                        <span style={{ color: "var(--signal-mute)" }}>
                          {log.ts.substring(11, 19)}{" "}
                        </span>
                      )}
                      <span style={{ color: levelColor(log.level) }}>
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="empty" style={{ textAlign: "center", padding: "40px" }}>
              Select a job to see its details and live logs.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function JobRow({
  job,
  selected,
  onClick,
  onControl,
}: {
  job: CockpitJob;
  selected: boolean;
  onClick: () => void;
  onControl: (id: string, action: "pause" | "resume" | "cancel") => void;
}) {
  const isActive = job.status === "running" || job.status === "pending" || job.status === "queued";
  void onControl; // reserved for inline controls in future
  return (
    <div
      onClick={onClick}
      style={{
        padding: "8px 10px",
        borderRadius: "8px",
        cursor: "pointer",
        background: selected ? "var(--void-2)" : "transparent",
        border: selected ? "1px solid var(--edge)" : "1px solid transparent",
        marginBottom: "2px",
        transition: "background 180ms",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <span
          style={{
            width: "7px",
            height: "7px",
            borderRadius: "50%",
            background: isActive ? "var(--ring-1)" : "var(--signal-mute)",
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: "12px", color: "var(--signal-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {job.title || job.id}
        </span>
      </div>
    </div>
  );
}

function statusPillClass(status?: string): string {
  switch (status) {
    case "running": return "accent";
    case "done": case "completed": case "success": return "";
    case "failed": case "error": return "";
    case "cancelled": case "canceled": return "";
    case "paused": return "";
    default: return "";
  }
}

function levelColor(level: string): string {
  switch (level.toLowerCase()) {
    case "error": return "#ff5a5a";
    case "warn": case "warning": return "#fbbf24";
    case "debug": return "var(--signal-mute)";
    default: return "var(--signal-dim)";
  }
}
