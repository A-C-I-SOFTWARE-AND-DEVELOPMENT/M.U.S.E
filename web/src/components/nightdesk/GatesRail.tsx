/**
 * GatesRail — Night Desk "Verification gates" rail (mockup 2).
 *
 * Static display of the REAL Axiom pre/post execution pipeline:
 *
 *   GET /api/nightdesk/gates → gates[8] { name, description }
 *                              validation { publish_allowed, status_counts } | null
 *
 * The eight gate names come straight from the engine
 * (hermes_cli.jarvis_prime.gates.GATES): planning, build, review, test,
 * security, release, owner_approval, rollback — rendered as a numbered
 * 2-col grid (G1–G8) with gate glyphs. No fake live state: nothing here
 * pulses, simulates, or invents per-gate outcomes; the only runtime
 * evidence shown is the validation artifact when the backend reports
 * one (<repo>/validation/results.json), otherwise an honest
 * "no gate runs recorded".
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";

import { fetchJSON } from "@/lib/api";

import "./nightdesk.css";

/* ------------------------------------------------------------------ */
/*  Types (mirrors hermes_cli/web_nightdesk_api.py payload shapes)     */
/* ------------------------------------------------------------------ */

interface GateRow {
  name: string;
  description: string | null;
}

interface GateValidation {
  publish_allowed: boolean | null;
  status_counts: Record<string, number>;
  total_checks?: number;
}

interface GatesPayload {
  gates?: GateRow[];
  validation?: GateValidation | null;
}

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

/** One glyph per gate of the real pipeline (index fallback for unknowns). */
const GATE_GLYPHS: Record<string, string> = {
  planning: "◇",
  build: "△",
  review: "◎",
  test: "⊡",
  security: "⬡",
  release: "▲",
  owner_approval: "◈",
  rollback: "↺",
};
const FALLBACK_GLYPHS = ["◇", "△", "◎", "⊡", "⬡", "▲", "◈", "↺"];

function gateGlyph(name: string, index: number): string {
  return (
    GATE_GLYPHS[name.toLowerCase()] ??
    FALLBACK_GLYPHS[index % FALLBACK_GLYPHS.length]
  );
}

function statusTone(status: string): string {
  const k = status.toLowerCase();
  if (k === "pass" || k === "passed" || k === "ok") return "var(--ok)";
  if (k === "fail" || k === "failed" || k === "error") return "var(--err)";
  if (k === "skip" || k === "skipped" || k === "warn" || k === "warning")
    return "var(--warn)";
  return "var(--fg-dim)";
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function GatesRail() {
  const [gates, setGates] = useState<GateRow[]>([]);
  const [validation, setValidation] = useState<GateValidation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const mountedRef = useRef(true);

  // Static pipeline — one honest fetch on mount (the validation artifact
  // only changes when a gate run happens out-of-band; no fake polling).
  const load = useCallback(async () => {
    try {
      const p = await fetchJSON<GatesPayload>("/api/nightdesk/gates");
      if (!mountedRef.current) return;
      setGates(Array.isArray(p.gates) ? p.gates : []);
      setValidation(p.validation ?? null);
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
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  const statusEntries = validation
    ? Object.entries(validation.status_counts ?? {}).sort((a, b) =>
        a[0].localeCompare(b[0]),
      )
    : [];

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Rail header */}
      <div
        className="shrink-0 border-b px-3 py-2"
        style={{ borderColor: HAIRLINE }}
      >
        <span className="text-[0.66rem]" style={labelStyle}>
          verification gates
        </span>
        <p
          className="mt-0.5 text-[0.62rem]"
          style={{ color: "var(--fg-faint)" }}
        >
          Axiom pre/post execution pipeline
        </p>
      </div>

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
            gates feed: {error}
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

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {/* G1–G8 numbered 2-col grid */}
        {loaded && gates.length === 0 && !error ? (
          <p
            className="py-6 text-center text-[0.7rem]"
            style={{ color: "var(--fg-faint)" }}
          >
            no gates reported by the engine
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-1.5">
            {gates.map((g, i) => (
              <div
                key={`${g.name}-${i}`}
                className="rounded-md border px-2 py-1.5"
                style={{
                  borderColor: HAIRLINE,
                  background:
                    "color-mix(in srgb, var(--midground-base) 2.5%, transparent)",
                }}
              >
                <div className="flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className="font-mono-ui text-[0.72rem] leading-none"
                    style={{ color: "var(--accent-dim)" }}
                  >
                    {gateGlyph(g.name, i)}
                  </span>
                  <span
                    className="font-mono-ui text-[0.6rem]"
                    style={{ color: "var(--fg-faint)" }}
                  >
                    G{i + 1}
                  </span>
                  <span
                    className="min-w-0 flex-1 truncate font-mono-ui text-[0.66rem]"
                    style={{ color: "var(--fg-dim)" }}
                    title={g.name}
                  >
                    {g.name.replace(/_/g, " ")}
                  </span>
                </div>
                {g.description ? (
                  <p
                    className="mt-1 text-[0.62rem] leading-relaxed"
                    style={{ color: "var(--fg-faint)" }}
                  >
                    {g.description}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        )}

        {/* Validation artifact — only real gate-run evidence */}
        <div
          className="mt-2 rounded-md border px-2.5 py-2"
          style={{
            borderColor: HAIRLINE,
            background:
              "color-mix(in srgb, var(--midground-base) 2.5%, transparent)",
          }}
        >
          <span className="text-[0.62rem]" style={labelStyle}>
            validation
          </span>
          {validation ? (
            <div className="mt-1.5">
              <div className="flex items-center gap-2">
                <span
                  className="rounded-full border px-2 py-0.5 font-mono-ui text-[0.62rem]"
                  style={{
                    borderColor:
                      validation.publish_allowed == null
                        ? HAIRLINE
                        : `color-mix(in srgb, ${
                            validation.publish_allowed
                              ? "var(--ok)"
                              : "var(--err)"
                          } 35%, transparent)`,
                    color:
                      validation.publish_allowed == null
                        ? "var(--fg-faint)"
                        : validation.publish_allowed
                          ? "var(--ok)"
                          : "var(--err)",
                    background:
                      validation.publish_allowed == null
                        ? "transparent"
                        : `color-mix(in srgb, ${
                            validation.publish_allowed
                              ? "var(--ok)"
                              : "var(--err)"
                          } 8%, transparent)`,
                  }}
                >
                  {validation.publish_allowed == null
                    ? "publish undetermined"
                    : validation.publish_allowed
                      ? "publish allowed"
                      : "publish blocked"}
                </span>
                {typeof validation.total_checks === "number" && (
                  <span
                    className="font-mono-ui text-[0.62rem]"
                    style={{ color: "var(--fg-faint)" }}
                  >
                    {validation.total_checks} checks
                  </span>
                )}
              </div>
              {statusEntries.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {statusEntries.map(([status, count]) => (
                    <span
                      key={status}
                      className="rounded border px-1.5 py-px font-mono-ui text-[0.62rem]"
                      style={{
                        borderColor: `color-mix(in srgb, ${statusTone(status)} 30%, transparent)`,
                        color: statusTone(status),
                      }}
                    >
                      {status} ×{count}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p
              className="mt-1 text-[0.66rem]"
              style={{ color: "var(--fg-faint)" }}
            >
              no gate runs recorded
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
