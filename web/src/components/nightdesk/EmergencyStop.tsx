import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { fetchJSON } from "@/lib/api";
import type { EmergencyStopResult } from "./useNightdesk";
import { useNightdeskOverview } from "./useNightdesk";

/* ------------------------------------------------------------------ */
/* EmergencyStop — the red rail button.                                */
/*                                                                     */
/* Shows autonomy state from the overview poller. When the backend has */
/* latched an emergency stop, the rail renders a locked STOPPED state. */
/* Otherwise the button opens a type-to-confirm dialog (type STOP) —   */
/* the POST NEVER fires without that explicit confirmation. On success */
/* the result (cancelled_jobs count etc.) is surfaced in the dialog    */
/* and the shared overview poller is refreshed.                        */
/* ------------------------------------------------------------------ */

const CONFIRM_WORD = "STOP";
const STOP_REASON = "manual stop from the Night Desk console";

type Phase = "idle" | "confirming" | "posting" | "result" | "failed";

export default function EmergencyStop() {
  const { data, refresh } = useNightdeskOverview(30000);
  const autonomy = data?.kpis?.autonomy ?? null;
  const stopped = autonomy?.emergency_stopped === true;

  const [phase, setPhase] = useState<Phase>("idle");
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<EmergencyStopResult | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const dialogOpen = phase === "confirming" || phase === "posting" || phase === "result" || phase === "failed";

  useEffect(() => {
    if (phase === "confirming") inputRef.current?.focus();
  }, [phase]);

  useEffect(() => {
    if (!dialogOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phase !== "posting") closeDialog();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dialogOpen, phase]);

  function openDialog() {
    setTyped("");
    setResult(null);
    setPostError(null);
    setPhase("confirming");
  }

  function closeDialog() {
    setPhase("idle");
    setTyped("");
  }

  async function fireStop() {
    if (phase !== "confirming" || typed.trim().toUpperCase() !== CONFIRM_WORD) return;
    setPhase("posting");
    try {
      const res = await fetchJSON<EmergencyStopResult>(
        "/api/nightdesk/emergency-stop",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: STOP_REASON }),
        },
      );
      setResult(res);
      setPhase("result");
      refresh();
    } catch (err) {
      setPostError(err instanceof Error ? err.message : String(err));
      setPhase("failed");
    }
  }

  /* Latched state — the backend says autonomy is emergency-stopped. */
  if (stopped) {
    return (
      <div className="nd-stop">
        <div className="nd-stop-latched" role="status">
          <span className="nd-stop-state">Stopped</span>
          <span className="nd-sub">
            emergency stop latched
            {autonomy?.level ? ` · autonomy ${autonomy.level}` : ""}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="nd-stop">
      <button
        type="button"
        className="nd-stop-button"
        onClick={openDialog}
        aria-haspopup="dialog"
      >
        Emergency stop
      </button>
      <span className="nd-sub">
        {autonomy ? `autonomy ${autonomy.level}` : "autonomy state unavailable"}
      </span>

      {dialogOpen &&
        createPortal(
          <div
            className="nd-dialog-overlay"
            role="dialog"
            aria-modal="true"
            aria-labelledby="nd-stop-title"
            onClick={(e) => {
              if (e.target === e.currentTarget && phase !== "posting") closeDialog();
            }}
          >
            <div className="nd-dialog">
              <div className="nd-dialog-head">
                <span className="nd-dialog-title" id="nd-stop-title">
                  Emergency stop
                </span>
              </div>

              <div className="nd-dialog-body">
                {(phase === "confirming" || phase === "posting") && (
                  <>
                    <span>
                      This halts the proactive runtime, clears owner gates and
                      branch leases, cancels every non-terminal queued job, and
                      latches autonomy to the safe floor.
                    </span>
                    <span>
                      Type <strong className="nd-mono">{CONFIRM_WORD}</strong> to
                      confirm.
                    </span>
                    <input
                      ref={inputRef}
                      className="nd-dialog-input"
                      value={typed}
                      disabled={phase === "posting"}
                      onChange={(e) => setTyped(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void fireStop();
                      }}
                      placeholder={CONFIRM_WORD}
                      autoComplete="off"
                      spellCheck={false}
                      aria-label={`Type ${CONFIRM_WORD} to confirm emergency stop`}
                    />
                  </>
                )}

                {phase === "posting" && <span>halting runtime…</span>}

                {phase === "result" && result && (
                  <>
                    <span>Emergency stop engaged.</span>
                    <div className="nd-stop-result">
                      {[
                        `cancelled jobs: ${result.cancelled_count}`,
                        `cleared gates: ${result.cleared_actions?.length ?? 0}`,
                        `branch leases cleared: ${result.branch_leases_cleared}`,
                        `proactive tick disabled: ${result.tick_disabled ? "yes" : "no"}`,
                        result.autonomy_level
                          ? `autonomy level: ${result.autonomy_level}`
                          : null,
                        result.skipped_effects?.length
                          ? `skipped effects: ${result.skipped_effects.join(", ")}`
                          : null,
                        result.errors?.length
                          ? `errors: ${result.errors.join(" · ")}`
                          : null,
                      ]
                        .filter(Boolean)
                        .join("\n")}
                    </div>
                  </>
                )}

                {phase === "failed" && (
                  <>
                    <span>The stop request failed — nothing was halted.</span>
                    <div className="nd-stop-result" data-tone="error">
                      {postError ?? "unknown error"}
                    </div>
                  </>
                )}
              </div>

              <div className="nd-dialog-actions">
                {(phase === "confirming" || phase === "posting") && (
                  <>
                    <button
                      type="button"
                      className="nd-button"
                      onClick={closeDialog}
                      disabled={phase === "posting"}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="nd-button nd-button-danger"
                      onClick={() => void fireStop()}
                      disabled={
                        phase === "posting" ||
                        typed.trim().toUpperCase() !== CONFIRM_WORD
                      }
                    >
                      {phase === "posting" ? "Stopping…" : "Engage stop"}
                    </button>
                  </>
                )}
                {(phase === "result" || phase === "failed") && (
                  <button type="button" className="nd-button" onClick={closeDialog}>
                    Close
                  </button>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
