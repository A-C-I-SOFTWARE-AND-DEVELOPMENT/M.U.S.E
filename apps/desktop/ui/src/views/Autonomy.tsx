/**
 * Autonomy — view and change the agent's autonomy level.
 *
 * Reads GET /v1/cockpit/autonomy (level + capabilities) and writes
 * POST /v1/cockpit/autonomy. RAISING the level (more autonomy than current) is
 * owner-gated: the owner phrase is prompted for at action time and attached to
 * the request; LOWERING (or revoking to Assisted) is token-only. A 403 on a
 * raise re-prompts for the exact phrase once. This mirrors the browser cockpit's
 * autonomy panel, including the ranking used to detect a raise and the
 * workspace-path field for High-Autonomy Coding.
 */
import { useCallback, useEffect, useState } from "react";
import {
  AUTONOMY_LEVELS,
  getAutonomy,
  getToken,
  isAutonomyRaise,
  promptOwnerPhrase,
  revokeAutonomy,
  setAutonomy,
  TOKEN_EVENT,
  type AutonomyState,
} from "../lib/gateway";

const HIGH_AUTONOMY = "owner_high_autonomy_coding";

type LoadState =
  | { kind: "loading" }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string }
  | { kind: "ready"; state: AutonomyState };

export function Autonomy() {
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [sel, setSel] = useState<string>("");
  const [workspace, setWorkspace] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>("");

  const fetchState = useCallback(async () => {
    if (!getToken()) {
      setLoad({ kind: "unauthorized" });
      return;
    }
    const r = await getAutonomy();
    if (!r.ok) {
      setLoad(
        r.unauthorized
          ? { kind: "unauthorized" }
          : { kind: "error", message: r.error || "offline" },
      );
      return;
    }
    setLoad({ kind: "ready", state: r.state });
    setSel(String(r.state.level || ""));
    setWorkspace(String(r.state.workspace_root || ""));
  }, []);

  useEffect(() => {
    void fetchState();
    // Re-fetch when this device gains/loses its token (auto-pair / Settings).
    const refresh = () => void fetchState();
    window.addEventListener(TOKEN_EVENT, refresh);
    return () => window.removeEventListener(TOKEN_EVENT, refresh);
  }, [fetchState]);

  const current = load.kind === "ready" ? String(load.state.level || "") : "";

  const apply = useCallback(async () => {
    if (!sel) return;
    setNotice("");
    const raise = isAutonomyRaise(current, sel);
    let authorization: string | undefined;
    if (raise) {
      const phrase = promptOwnerPhrase("Raise autonomy to " + sel);
      if (phrase == null) return; // cancelled
      authorization = phrase;
    }
    setBusy(true);
    const ws = sel === HIGH_AUTONOMY ? workspace.trim() : "";
    let res = await setAutonomy(sel, {
      authorization,
      workspacePath: ws || undefined,
    });
    if (res.forbidden) {
      const retry = promptOwnerPhrase(
        "Authorization required — re-enter the exact phrase to raise autonomy",
      );
      if (retry == null) {
        setBusy(false);
        return;
      }
      res = await setAutonomy(sel, {
        authorization: retry,
        workspacePath: ws || undefined,
      });
    }
    setBusy(false);
    if (!res.ok) {
      setNotice(
        "Autonomy change failed" +
          (res.forbidden ? " — authorization rejected" : "") +
          (res.error ? " (" + res.error + ")" : "") +
          ".",
      );
    }
    void fetchState();
  }, [sel, current, workspace, fetchState]);

  const revoke = useCallback(async () => {
    setNotice("");
    setBusy(true);
    const res = await revokeAutonomy();
    setBusy(false);
    if (!res.ok) {
      setNotice("Revoke failed" + (res.error ? " (" + res.error + ")" : "") + ".");
    }
    void fetchState();
  }, [fetchState]);

  return (
    <div className="view">
      <div className="section-header">
        <div>
          <div className="eyebrow">Control</div>
          <h2 className="section-title">Autonomy</h2>
        </div>
      </div>

      {notice && <div className="card notice danger-notice">{notice}</div>}

      {load.kind === "loading" && (
        <div className="card">
          <div className="empty muted">Loading autonomy…</div>
        </div>
      )}

      {load.kind === "unauthorized" && (
        <div className="card">
          <div className="empty">Pair this device in Settings to view autonomy.</div>
        </div>
      )}

      {load.kind === "error" && (
        <div className="card">
          <div className="empty">Couldn’t load autonomy: {load.message}</div>
        </div>
      )}

      {load.kind === "ready" && (
        <AutonomyCard
          state={load.state}
          current={current}
          sel={sel}
          setSel={setSel}
          workspace={workspace}
          setWorkspace={setWorkspace}
          busy={busy}
          onApply={() => void apply()}
          onRevoke={() => void revoke()}
        />
      )}
    </div>
  );
}

function AutonomyCard({
  state,
  current,
  sel,
  setSel,
  workspace,
  setWorkspace,
  busy,
  onApply,
  onRevoke,
}: {
  state: AutonomyState;
  current: string;
  sel: string;
  setSel: (v: string) => void;
  workspace: string;
  setWorkspace: (v: string) => void;
  busy: boolean;
  onApply: () => void;
  onRevoke: () => void;
}) {
  const caps = state.capabilities || {};
  const showWorkspace = sel === HIGH_AUTONOMY;
  const dirty = sel !== current || (showWorkspace && workspace.trim() !== (state.workspace_root || ""));
  return (
    <div className="card">
      <div className="row">
        <b>Autonomy</b>
        <span className="grow" />
        <span className="pill">{state.display_name || current || "unknown"}</span>
      </div>
      <div className="muted">
        Set by {state.set_by || "owner"}
        {state.workspace_root ? " · scope " + state.workspace_root : ""}
      </div>

      <div className="row autonomy-controls">
        <span className="k">Level</span>
        <select value={sel} onChange={(e) => setSel(e.target.value)}>
          {AUTONOMY_LEVELS.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
        {showWorkspace && (
          <input
            type="text"
            placeholder="workspace path (for High-Autonomy Coding)"
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
            className="ws-input"
          />
        )}
        <button className="primary" disabled={busy || !dirty} onClick={onApply}>
          Apply
        </button>
        <button className="danger" disabled={busy} onClick={onRevoke}>
          Revoke → Assisted
        </button>
      </div>

      <div className="hint">
        Raising autonomy is owner-gated; you’ll be asked for the owner phrase.
        Lowering or revoking is token-only.
      </div>

      <div className="caps muted mono">
        <div>auto-approved: {(caps.auto_approved || []).join(", ") || "—"}</div>
        <div>requires approval: {(caps.requires_approval || []).join(", ") || "—"}</div>
        <div>always deny: {(caps.always_deny || []).join(", ") || "—"}</div>
      </div>
    </div>
  );
}
