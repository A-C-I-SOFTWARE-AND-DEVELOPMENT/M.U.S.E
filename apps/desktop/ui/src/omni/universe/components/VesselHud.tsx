import { PLAYER_MODES } from '../catalog.ts';
import { useUniverseStore } from '../store.ts';
import type { Vessel } from '../types.ts';
import { unavailableVesselSystems, vesselClassOf, vesselSystemValue, VESSEL_SYSTEM_MAP } from '../vessel.ts';

export function VesselHud({
  vessel,
  onBoard,
  onCustomize,
}: {
  vessel: Vessel | null;
  onBoard?: (vessel: Vessel) => void;
  onCustomize?: (vessel: Vessel) => void;
}) {
  const mode = useUniverseStore((state) => state.playerMode);
  const setMode = useUniverseStore((state) => state.setPlayerMode);
  if (!vessel) {
    return (
      <section className="vessel-hud universe-panel" aria-label="Vessel controls unavailable">
        <p className="universe-eyebrow">Flight deck</p>
        <h2>No vessel projection reported</h2>
        <p className="universe-empty-copy">Board, pilot, fleet, and director controls remain unavailable until the realm reports a vessel and its binding.</p>
      </section>
    );
  }
  const unavailable = unavailableVesselSystems(vessel);
  return (
    <section className="vessel-hud universe-panel" aria-label={`Vessel controls for ${vessel.cosmetics?.name ?? vessel.name ?? vessel.id}`}>
      <div className="vessel-hud__header">
        <div>
          <p className="universe-eyebrow">{vesselClassOf(vessel)} class · v{vessel.version}</p>
          <h2>{vessel.cosmetics?.name ?? vessel.name ?? vessel.id}</h2>
          <p className="mono">last observed {vessel.updated_at || 'not reported'}</p>
        </div>
        <span className={`universe-chip universe-chip--${vessel.simulation ? 'simulated' : 'observed'}`}>
          {vessel.simulation ? 'Simulation' : 'Authoritative'}
        </span>
      </div>

      <div className="player-mode-switcher" role="group" aria-label="Player navigation mode">
        {PLAYER_MODES.map((entry) => (
          <button
            type="button"
            key={entry.id}
            aria-pressed={mode === entry.id}
            aria-label={`${entry.label} mode: ${entry.summary}`}
            onClick={() => setMode(entry.id)}
          >
            <strong>{entry.label}</strong>
            <small>{entry.summary}</small>
          </button>
        ))}
      </div>

      <dl className="vessel-systems">
        {(Object.keys(VESSEL_SYSTEM_MAP) as Array<keyof typeof VESSEL_SYSTEM_MAP>).map((system) => {
          const value = vesselSystemValue(vessel, system);
          return (
            <div key={system} className={value == null ? 'is-unavailable' : ''}>
              <dt>{system.replace(/([A-Z])/g, ' $1')}</dt>
              <dd>{value == null ? 'Not reported' : Array.isArray(value) ? `${value.length} entries` : typeof value === 'object' ? 'Reported' : String(value)}</dd>
              <small>{VESSEL_SYSTEM_MAP[system]}</small>
            </div>
          );
        })}
      </dl>

      {unavailable.length > 0 && (
        <p className="universe-inline-warning">{unavailable.length} vessel systems are degraded or unreported. No damage state is inferred.</p>
      )}
      <div className="universe-action-row">
        <button type="button" className="universe-button universe-button--primary" disabled={!onBoard} onClick={() => onBoard?.(vessel)}>
          Board through airlock
        </button>
        <button type="button" className="universe-button" disabled={!onCustomize} onClick={() => onCustomize?.(vessel)}>
          Open Shipyard
        </button>
      </div>
    </section>
  );
}
