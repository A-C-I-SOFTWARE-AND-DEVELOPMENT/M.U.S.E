/**
 * Approvals — the owner-gate decision surface.
 *
 * Lists pending approvals from GET /v1/cockpit/approvals (each with its proposed
 * action) and decides them via POST /v1/cockpit/approvals/{id}. APPROVE is
 * owner-gated: the exact owner authorization phrase is prompted for at the
 * moment the button is pressed (window.prompt via `promptOwnerPhrase`), sent in
 * the request body, and NEVER stored. DENY needs no phrase, but if the server
 * returns 403 on either action we re-prompt for the phrase exactly once — the
 * same contract the browser cockpit implements.
 */
import { useCallback, useEffect, useState } from "react";
import {
  decideApproval,
  getApprovals,
  getToken,
  promptOwnerPhrase,
  TOKEN_EVENT,
  type CockpitApproval,
} from "../lib/gateway";

type LoadState =
  | { kind: "loading" }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string }
  | { kind: "ready"; items: CockpitApproval[] };

export function Approvals() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string>("");

  const load = useCallback(async () => {
    if (!getToken()) {
      setState({ kind: "unauthorized" });
      return;
    }
    const r = await getApprovals();
    if (!r.ok) {
      setState(
        r.unauthorized
          ? { kind: "unauthorized" }
          : { kind: "error", message: r.error || "offline" },
      );
      return;
    }
    setState({ kind: "ready", items: r.approvals });
  }, []);

  useEffect(() => {
    void load();
    // Refresh on a gentle cadence so decisions made elsewhere reflect here,
    // and immediately when this device gains/loses its token (auto-pair).
    const t = setInterval(() => void load(), 12000);
    const refresh = () => void load();
    window.addEventListener(TOKEN_EVENT, refresh);
    return () => {
      clearInterval(t);
      window.removeEventListener(TOKEN_EVENT, refresh);
    };
  }, [load]);

  const decide = useCallback(
    async (id: string, decision: "approve" | "reject") => {
      setNotice("");
      // Approve is owner-gated → prompt for the phrase at action time.
      let authorization: string | undefined;
      if (decision === "approve") {
        const phrase = promptOwnerPhrase("Approve proposal " + id);
        if (phrase == null) return; // cancelled
        authorization = phrase;
      }
      setBusyId(id);
      let res = await decideApproval(id, decision, authorization);
      if (res.forbidden) {
        // Owner authorization required / phrase mismatch — re-prompt once.
        const retry = promptOwnerPhrase(
          "Authorization required — re-enter the exact phrase to " +
            decision +
            " " +
            id,
        );
        if (retry == null) {
          setBusyId(null);
          return;
        }
        res = await decideApproval(id, decision, retry);
      }
      setBusyId(null);
      if (!res.ok) {
        setNotice(
          "Decision failed" +
            (res.forbidden ? " — authorization rejected" : "") +
            (res.error ? " (" + res.error + ")" : "") +
            ".",
        );
      }
      void load();
    },
    [load],
  );

  return (
    <div className="view">
      <div className="section-header">
        <div>
          <div className="eyebrow">Owner gate</div>
          <h2 className="section-title">Approvals</h2>
        </div>
      </div>

      {notice && <div className="card notice danger-notice">{notice}</div>}

      {state.kind === "loading" && (
        <div className="card">
          <div className="empty muted">Loading approvals…</div>
        </div>
      )}

      {state.kind === "unauthorized" && (
        <div className="card">
          <div className="empty">Pair this device in Settings to view approvals.</div>
        </div>
      )}

      {state.kind === "error" && (
        <div className="card">
          <div className="empty">Couldn’t load approvals: {state.message}</div>
        </div>
      )}

      {state.kind === "ready" && state.items.length === 0 && (
        <div className="card">
          <div className="empty muted">No pending approvals.</div>
        </div>
      )}

      {state.kind === "ready" &&
        state.items.map((a) => {
          const id = a.id || "";
          const pending =
            String(a.status || "PENDING").toUpperCase() === "PENDING";
          const action = a.summary || a.proposed_action || "";
          return (
            <div className="card" key={id}>
              <div className="row">
                <b>{a.title || a.kind || "approval"}</b>
                <span className="grow" />
                {a.tier && <span className="pill">{a.tier}</span>}
                {a.status && <span className="pill">{a.status}</span>}
              </div>
              {action && <div className="proposed">{action}</div>}
              {pending ? (
                <div className="approval-actions">
                  <button
                    className="approve"
                    disabled={busyId === id}
                    onClick={() => void decide(id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="danger"
                    disabled={busyId === id}
                    onClick={() => void decide(id, "reject")}
                  >
                    Deny
                  </button>
                </div>
              ) : (
                <div className="hint">Decision: {a.status}</div>
              )}
            </div>
          );
        })}
    </div>
  );
}
