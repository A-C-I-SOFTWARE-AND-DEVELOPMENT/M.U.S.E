/**
 * Jobs — the live orchestration job list.
 *
 * Subscribes to GET /v1/cockpit/jobs/stream via the shared `subscribeJobs()`
 * client (lib/gateway), which streams Server-Sent Events over fetch +
 * ReadableStream (so it can carry the bearer token, unlike EventSource),
 * reconnects with capped backoff, and falls back to a single poll of
 * GET /v1/cockpit/jobs when the streaming primitives are unavailable. Each job
 * renders as a card with a PhaseRail (queued→running→approval→approved→
 * publishing→published), a status pill, and the worker/branch line.
 *
 * The subscription is the only source of truth for the list; we hold jobs in a
 * Map keyed by id and re-render on every upsert/removal. A small "live / polling
 * / reconnecting" indicator reflects the stream's liveness.
 */
import { useEffect, useMemo, useState } from "react";
import { PhaseRail, type PhaseState } from "../components/PhaseRail";
import {
  getToken,
  subscribeJobs,
  type CockpitJob,
} from "../lib/gateway";

const JOB_PHASES = [
  "queued",
  "running",
  "approval",
  "approved",
  "publishing",
  "published",
] as const;

function jobStatusToPhases(status: string): Array<{ id: string; label: string; state: PhaseState }> {
  const idx = JOB_PHASES.indexOf(status as (typeof JOB_PHASES)[number]);
  if (idx < 0) return JOB_PHASES.map((id, i) => ({ id, label: id, state: i === 0 ? "current" as PhaseState : "pending" as PhaseState }));
  return JOB_PHASES.map((id, i) => ({
    id,
    label: id,
    state: i < idx ? ("done" as PhaseState) : i === idx ? ("current" as PhaseState) : ("pending" as PhaseState),
  }));
}

export function Jobs() {
  // jobs keyed by id; a monotonically-bumped tick forces re-render on mutation.
  const jobsRef = useMemo(() => new Map<string, CockpitJob>(), []);
  const [, setTick] = useState(0);
  const bump = () => setTick((n) => n + 1);
  const [live, setLive] = useState(false);
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));

  useEffect(() => {
    const refresh = () => setPaired(Boolean(getToken()));
    window.addEventListener("focus", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  useEffect(() => {
    if (!paired) return;
    jobsRef.clear();
    bump();
    const dispose = subscribeJobs({
      onUpsert: (job) => {
        jobsRef.set(job.id, job);
        bump();
      },
      onRemoved: (id) => {
        jobsRef.delete(id);
        bump();
      },
      onLive: (on) => setLive(on),
    });
    return () => {
      dispose();
      setLive(false);
    };
    // jobsRef is a stable useMemo([]) handle, so re-subscribe only when the
    // pairing state flips (token gained/lost) — not on every render.
  }, [paired, jobsRef]);

  const jobs = [...jobsRef.values()];

  return (
    <div className="view">
      <div className="section-header">
        <div>
          <div className="eyebrow">Orchestration</div>
          <h2 className="section-title">Jobs</h2>
        </div>
        <span className="grow" />
        <span className={"streamdot " + (live ? "live" : "")}>
          <span className="dot-mini" />
          {live ? "live" : paired ? "reconnecting…" : "paired device required"}
        </span>
      </div>

      {!paired ? (
        <div className="card">
          <div className="empty">Pair this device in Settings to view jobs.</div>
        </div>
      ) : jobs.length === 0 ? (
        <div className="card">
          <div className="empty">
            No jobs yet. Live updates stream here over SSE.
          </div>
        </div>
      ) : (
        jobs.map((j) => (
          <div className="card" key={j.id}>
            <div className="row">
              <b>{j.title || j.id}</b>
              <span className="grow" />
              {j.status && <span className="pill">{j.status}</span>}
            </div>
            <PhaseRail phases={jobStatusToPhases(j.status || "")} />
            {(j.worker_id || j.branch) && (
              <div className="muted mono job-meta">
                {j.worker_id || ""}
                {j.branch ? " · " + j.branch : ""}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
