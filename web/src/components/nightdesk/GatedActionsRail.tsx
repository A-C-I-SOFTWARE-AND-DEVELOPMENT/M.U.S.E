/**
 * GatedActionsRail — Night Desk "Owner-gated actions" rail (mockup 2).
 *
 * Reads the REAL approvals store through the Night Desk API:
 *
 *   GET  /api/nightdesk/gated-actions                  → pending[] + autonomy
 *   POST /api/nightdesk/gated-actions/{id}/decide      → { decision, authorization }
 *
 * The Axiom kernel holds execution until the owner grants a bound
 * approval. Granting (or rejecting) requires typing the EXACT owner
 * authorization phrase ("Yes, with authorization.") — the backend
 * enforces it for both decisions; the rail mirrors that gate with an
 * inline confirm that keeps the decide buttons disabled until the
 * phrase matches character-for-character.
 *
 * Decide errors are surfaced inline per row: 403 (phrase mismatch),
 * 409 (state changed / superseded), 410 (expired), 404 (gone).
 *
 * Polls every 15s. Empty store → honest "no actions awaiting grant".
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, KeyRound, RotateCcw } from "lucide-react";

import { fetchJSON } from "@/lib/api";

import "./nightdesk.css";

/* ------------------------------------------------------------------ */
/*  Types (mirrors hermes_cli/web_nightdesk_api.py payload shapes)     */
/* ------------------------------------------------------------------ */

interface PendingAction {
  id: string;
  action: string;
  realm_id?: string;
  state?: string;
  issued_at?: number | string | null;
  /** Epoch seconds (grants.db REAL column) — defensive string tolerated. */
  expires_at?: number | string | null;
  subject_hash?: string;
  /** Honest null — bound approvals persist no risk classification. */
  risk_tier: string | null;
  category: string;
  category_known?: boolean;
  description: string;
}

interface AutonomyRecord {
  level: string;
  emergency_stopped: boolean;
  set_by?: string;
  updated_at?: number | string | null;
}

interface GatedActionsPayload {
  pending?: PendingAction[];
  autonomy?: AutonomyRecord | null;
  store_present?: boolean;
}

interface DecideResult {
  id: string;
  action?: string;
  state?: string;
  decision?: string;
  decided_at?: number | string | null;
  supersedes?: string[];
  superseded_by?: string | null;
}

/** The exact owner authorization phrase (jarvis_prime/owner_auth.py). */
const AUTHORIZATION_PHRASE = "Yes, with authorization.";

const POLL_MS = 15_000;

/* ------------------------------------------------------------------ */
/*  Small helpers                                                      */
/* ------------------------------------------------------------------ */

const labelStyle: React.CSSProperties = {
  fontVariantCaps: "all-small-caps",
  letterSpacing: "0.14em",
  color: "var(--fg-faint)",
};

const HAIRLINE =
  "color-mix(in srgb, var(--midground-base) 10%, transparent)";

function toDate(ts: number | string | null | undefined): Date | null {
  if (ts == null || ts === "") return null;
  const d =
    typeof ts === "number"
      ? new Date(ts * 1000) // grants.db stores REAL epoch seconds
      : new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

function fmtTime(ts: number | string | null | undefined): string | null {
  const d = toDate(ts);
  return d
    ? d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : null;
}

function riskTone(tier: string | null): { color: string; label: string } {
  if (!tier) return { color: "var(--fg-faint)", label: "unrated" };
  const k = tier.toLowerCase();
  if (k === "critical" || k === "high" || k === "severe")
    return { color: "var(--err)", label: tier };
  if (k === "medium" || k === "moderate" || k === "elevated")
    return { color: "var(--warn)", label: tier };
  if (k === "low" || k === "minor") return { color: "var(--ok)", label: tier };
  return { color: "var(--accent-dim)", label: tier };
}

/** Map a fetchJSON error ("403: {json}") to an honest inline message. */
function decideErrorMessage(raw: string): string {
  const m = raw.match(/^(\d{3}):\s*(.*)$/s);
  const status = m ? Number(m[1]) : 0;
  let detail = "";
  if (m?.[2]) {
    try {
      const body = JSON.parse(m[2]) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      detail = m[2].slice(0, 120);
    }
  }
  switch (status) {
    case 403:
      return "owner authorization required — the phrase did not match";
    case 404:
      return "approval not found — it may already be decided";
    case 409:
      return detail
        ? `approval cannot be decided — ${detail}`
        : "approval cannot be decided — its state changed on the server";
    case 410:
      return "approval expired before the decision landed";
    default:
      return detail || raw || "decision failed";
  }
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function GatedActionsRail() {
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [autonomy, setAutonomy] = useState<AutonomyRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    try {
      const p = await fetchJSON<GatedActionsPayload>(
        "/api/nightdesk/gated-actions",
      );
      if (!mountedRef.current) return;
      setPending(Array.isArray(p.pending) ? p.pending : []);
      setAutonomy(p.autonomy ?? null);
      setError(null);
      setLoaded(true);
    } catch (e) {
      if (!mountedRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(id);
    };
  }, [load]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Rail header */}
      <div
        className="shrink-0 border-b px-3 py-2"
        style={{ borderColor: HAIRLINE }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[0.66rem]" style={labelStyle}>
            owner-gated actions
          </span>
          <span
            className="ml-auto inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono-ui text-[0.62rem]"
            style={{
              borderColor: autonomy?.emergency_stopped
                ? "color-mix(in srgb, var(--err) 35%, transparent)"
                : HAIRLINE,
              color: autonomy?.emergency_stopped
                ? "var(--err)"
                : "var(--fg-dim)",
              background: autonomy?.emergency_stopped
                ? "color-mix(in srgb, var(--err) 8%, transparent)"
                : "transparent",
            }}
            title={
              autonomy
                ? `autonomy ${autonomy.level}${autonomy.set_by ? ` · set by ${autonomy.set_by}` : ""}${
                      fmtTime(autonomy.updated_at)
                        ? ` · updated ${fmtTime(autonomy.updated_at)}`
                        : ""
                    }`
                : "autonomy record unavailable"
            }
          >
            {autonomy
              ? autonomy.emergency_stopped
                ? "emergency stopped"
                : `autonomy ${autonomy.level}`
              : "autonomy —"}
          </span>
        </div>
        <p
          className="mt-0.5 text-[0.62rem]"
          style={{ color: "var(--fg-faint)" }}
        >
          Axiom kernel holds execution until phrase grant
        </p>
      </div>

      {/* Fetch error — stale rows stay visible under the banner */}
      {error && (
        <div
          role="alert"
          className="mx-3 mt-2 flex shrink-0 items-start gap-2 rounded-md border px-3 py-1.5 text-[0.7rem]"
          style={{
            borderColor: "color-mix(in srgb, var(--err) 25%, transparent)",
            background: "color-mix(in srgb, var(--err) 8%, transparent)",
            color: "var(--err)",
          }}
        >
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 flex-1 leading-relaxed">
            gated-actions feed: {error}
          </span>
          <button
            type="button"
            onClick={() => void load()}
            aria-label="Retry"
            title="Retry"
            className="muse-press flex h-5 w-5 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-current/10"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Pending list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {loaded && pending.length === 0 && !error ? (
          <p
            className="py-6 text-center text-[0.7rem]"
            style={{ color: "var(--fg-faint)" }}
          >
            no actions awaiting grant
          </p>
        ) : (
          pending.map((a) => (
            <GatedActionRow key={a.id} action={a} onSettled={load} />
          ))
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Row + inline phrase-gated confirm                                  */
/* ------------------------------------------------------------------ */

function GatedActionRow({
  action,
  onSettled,
}: {
  action: PendingAction;
  onSettled: () => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [decideError, setDecideError] = useState<string | null>(null);
  const [result, setResult] = useState<DecideResult | null>(null);

  const phraseOk = phrase === AUTHORIZATION_PHRASE;
  const risk = riskTone(action.risk_tier);
  const expiresAt = toDate(action.expires_at);
  const expired = expiresAt ? expiresAt.getTime() <= Date.now() : false;
  const expiryLabel = fmtTime(action.expires_at);

  const decide = useCallback(
    async (decision: "approve" | "reject") => {
      if (!phraseOk || submitting) return;
      setSubmitting(true);
      setDecideError(null);
      try {
        const r = await fetchJSON<DecideResult>(
          `/api/nightdesk/gated-actions/${encodeURIComponent(action.id)}/decide`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ decision, authorization: phrase }),
          },
        );
        setResult(r);
        setConfirming(false);
        // Let the owner read the outcome, then refresh the store view.
        window.setTimeout(() => void onSettled(), 1500);
      } catch (e) {
        setDecideError(
          decideErrorMessage(e instanceof Error ? e.message : String(e)),
        );
        // 404/409/410 mean the store moved on — refresh so stale rows go.
        window.setTimeout(() => void onSettled(), 2500);
      } finally {
        setSubmitting(false);
      }
    },
    [action.id, phrase, phraseOk, submitting, onSettled],
  );

  return (
    <div
      className="mb-2 rounded-md border px-2.5 py-2"
      style={{
        borderColor: HAIRLINE,
        background: "color-mix(in srgb, var(--midground-base) 2.5%, transparent)",
      }}
    >
      {/* Row 1 — mono id + risk chip */}
      <div className="flex items-center gap-2">
        <span
          className="min-w-0 flex-1 truncate font-mono-ui text-[0.66rem]"
          style={{ color: "var(--fg-dim)" }}
          title={action.id}
        >
          {action.id}
        </span>
        <span
          className="shrink-0 rounded-full border px-1.5 py-px font-mono-ui text-[0.6rem]"
          style={{
            borderColor: `color-mix(in srgb, ${risk.color} 35%, transparent)`,
            color: risk.color,
          }}
        >
          {risk.label}
        </span>
      </div>

      {/* Row 2 — category + description */}
      <div className="mt-1 flex items-baseline gap-2">
        <span
          className="shrink-0 text-[0.64rem]"
          style={{
            ...labelStyle,
            color: action.category_known === false ? "var(--fg-faint)" : "var(--fg-dim)",
          }}
        >
          {action.category}
        </span>
        {expiryLabel && (
          <span
            className="ml-auto shrink-0 font-mono-ui text-[0.6rem]"
            style={{ color: expired ? "var(--err)" : "var(--fg-faint)" }}
            title={
              expiresAt ? `expires ${expiresAt.toLocaleString()}` : undefined
            }
          >
            {expired ? "expired" : `exp ${expiryLabel}`}
          </span>
        )}
      </div>
      <p
        className="mt-0.5 text-[0.7rem] leading-relaxed"
        style={{ color: "var(--fg-dim)" }}
      >
        {action.description}
      </p>

      {/* Result banner after a successful decision */}
      {result && (
        <div
          className="mt-1.5 flex items-center gap-2 rounded border px-2 py-1 font-mono-ui text-[0.64rem]"
          style={{
            borderColor: `color-mix(in srgb, ${
              result.decision === "approve" ? "var(--ok)" : "var(--warn)"
            } 30%, transparent)`,
            color:
              result.decision === "approve" ? "var(--ok)" : "var(--warn)",
          }}
        >
          <span>
            {result.decision ?? "decided"} → {result.state ?? "recorded"}
          </span>
          {result.supersedes && result.supersedes.length > 0 && (
            <span style={{ color: "var(--fg-faint)" }}>
              supersedes {result.supersedes.length}
            </span>
          )}
        </div>
      )}

      {/* Grant button / inline phrase-gated confirm */}
      {!result && !confirming && (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="muse-press mt-1.5 inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[0.64rem] transition-colors"
          style={{
            borderColor: "color-mix(in srgb, var(--accent) 30%, transparent)",
            background: "color-mix(in srgb, var(--accent) 8%, transparent)",
            color: "var(--accent)",
            fontVariantCaps: "all-small-caps",
            letterSpacing: "0.1em",
          }}
        >
          <KeyRound className="h-3 w-3" />
          grant
        </button>
      )}

      {!result && confirming && (
        <div
          className="mt-1.5 rounded-md border px-2 py-1.5"
          style={{
            borderColor: "color-mix(in srgb, var(--accent) 20%, transparent)",
            background: "color-mix(in srgb, var(--accent) 4%, transparent)",
          }}
        >
          <label
            htmlFor={`nd-phrase-${action.id}`}
            className="block text-[0.62rem]"
            style={labelStyle}
          >
            type the authorization phrase to decide
          </label>
          <input
            id={`nd-phrase-${action.id}`}
            type="text"
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            placeholder={AUTHORIZATION_PHRASE}
            autoComplete="off"
            spellCheck={false}
            disabled={submitting}
            className="mt-1 w-full rounded border bg-transparent px-2 py-1 font-mono-ui text-[0.68rem] outline-none placeholder:text-[var(--fg-faint)]"
            style={{
              borderColor:
                phrase.length > 0
                  ? phraseOk
                    ? "color-mix(in srgb, var(--ok) 40%, transparent)"
                    : "color-mix(in srgb, var(--err) 40%, transparent)"
                  : HAIRLINE,
              color: "var(--fg)",
            }}
          />
          {phrase.length > 0 && !phraseOk && (
            <p
              className="mt-1 text-[0.62rem]"
              style={{ color: "var(--fg-faint)" }}
            >
              phrase does not match
            </p>
          )}

          {decideError && (
            <p
              role="alert"
              className="mt-1 text-[0.64rem] leading-relaxed"
              style={{ color: "var(--err)" }}
            >
              {decideError}
            </p>
          )}

          <div className="mt-1.5 flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => void decide("approve")}
              disabled={!phraseOk || submitting}
              className="muse-press rounded-md border px-2 py-1 text-[0.64rem] transition-opacity disabled:opacity-35"
              style={{
                borderColor: "color-mix(in srgb, var(--ok) 35%, transparent)",
                background: "color-mix(in srgb, var(--ok) 10%, transparent)",
                color: "var(--ok)",
                fontVariantCaps: "all-small-caps",
                letterSpacing: "0.1em",
              }}
            >
              {submitting ? "deciding…" : "approve"}
            </button>
            <button
              type="button"
              onClick={() => void decide("reject")}
              disabled={!phraseOk || submitting}
              className="muse-press rounded-md border px-2 py-1 text-[0.64rem] transition-opacity disabled:opacity-35"
              style={{
                borderColor: "color-mix(in srgb, var(--err) 30%, transparent)",
                background: "color-mix(in srgb, var(--err) 8%, transparent)",
                color: "var(--err)",
                fontVariantCaps: "all-small-caps",
                letterSpacing: "0.1em",
              }}
            >
              reject
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
                setPhrase("");
                setDecideError(null);
              }}
              disabled={submitting}
              className="muse-press ml-auto rounded px-1.5 py-1 text-[0.62rem] transition-colors hover:bg-current/5 disabled:opacity-35"
              style={{ color: "var(--fg-faint)" }}
            >
              cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
