/**
 * PhaseRail — the Singularity milestone tracker.
 *
 * Mirrors the cockpit's phase rail: a row of nodes connected by bars.
 * States: done (spectral ring), current (incandescent core), pending (void),
 * failed (danger). Done bars shimmer with the spectral gradient.
 *
 * Usage:
 *   <PhaseRail
 *     phases={[
 *       { id: "concept", label: "Concept", state: "done" },
 *       { id: "prototype", label: "Prototype", state: "current" },
 *       { id: "vertical", label: "Vertical Slice", state: "pending" },
 *       { id: "alpha", label: "Alpha", state: "pending" },
 *       { id: "beta", label: "Beta", state: "pending" },
 *       { id: "gold", label: "Gold", state: "pending" },
 *       { id: "launch", label: "Launch", state: "pending" },
 *     ]}
 *   />
 */
import { useMemo } from "react";
import "./PhaseRail.css";

export type PhaseState = "done" | "current" | "pending" | "failed";

export interface PhaseRailProps {
  /** Array of phases in order. */
  phases: Array<{
    id: string;
    label: string;
    state: PhaseState;
  }>;
  /** Optional className for the container. */
  className?: string;
}

export function PhaseRail({ phases, className }: PhaseRailProps) {
  const nodes = useMemo(
    () =>
      phases.map((p, i) => ({
        ...p,
        isLast: i === phases.length - 1,
      })),
    [phases]
  );

  return (
    <div className={`phaserail ${className || ""}`} role="list" aria-label="Milestone phases">
      {nodes.map((phase) => (
        <div key={phase.id} className="phase" role="listitem">
          <span
            className={`phase-node ${phase.state}`}
            aria-label={`${phase.label}: ${phase.state}`}
          />
          {phase.state === "done" && (
            <span className="phase-bar" aria-hidden="true" />
          )}
          <span className={`phase-label ${phase.state}`}>{phase.label}</span>
        </div>
      ))}
    </div>
  );
}

export default PhaseRail;