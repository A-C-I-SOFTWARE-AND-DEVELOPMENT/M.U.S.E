/**
 * PhaseRail — the horizontal job/phase progress indicator from the muse
 * design-language component catalog (docs/brand/muse-design-language.md §
 * "PhaseRail"). A row of nodes connected by hairline bars; the spectral ring is
 * the ONLY accent here. Done = ring-1; current = the incandescent white core;
 * failed = danger; pending = edge. This mirrors the browser cockpit's `.phaserail`
 * exactly (gateway/cockpit/static/index.html), driven by the shared
 * `phaseStates()` vocabulary in lib/gateway so client and cockpit never drift.
 *
 * Per the design language the ring is matte — the node "lit" treatment here is a
 * thin tonal node, no neon. Labels ride the value ladder: pending/done are dim,
 * the current phase brightens to full signal.
 */
import { JOB_PHASES, JOB_PHASE_LABEL, phaseStates } from "../lib/gateway";

export function PhaseRail({ status }: { status: string | undefined }) {
  const states = phaseStates(status);
  return (
    <div className="phaserail" role="list" aria-label="Job phase progression">
      {JOB_PHASES.map((ph, i) => {
        const state = states[i];
        const last = i === JOB_PHASES.length - 1;
        return (
          <span key={ph} className={"phase " + state} role="listitem">
            <span className="phase-node" aria-hidden="true" />
            <span className="phase-label">{JOB_PHASE_LABEL[ph]}</span>
            {!last && <span className="phase-bar" aria-hidden="true" />}
          </span>
        );
      })}
    </div>
  );
}
