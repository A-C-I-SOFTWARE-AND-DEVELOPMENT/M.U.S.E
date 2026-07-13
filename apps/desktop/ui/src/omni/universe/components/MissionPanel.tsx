import type { Mission } from '../types.ts';

export function MissionPanel({ mission }: { mission: Mission }) {
  const state = mission.state ?? mission.status ?? 'not reported';
  return (
    <article className="mission-panel universe-panel">
      <div>
        <p className="universe-eyebrow">{mission.mode ?? (mission.simulation ? 'simulation' : 'real')} mission · v{mission.version}</p>
        <h3>{mission.name ?? mission.id}</h3>
        <p>{mission.source_type ?? 'source not reported'} · {mission.source_id ?? 'no source id'}</p>
      </div>
      <span className={`universe-chip universe-chip--${state}`}>{state}</span>
      <div className="mission-panel__evidence">
        <span>Evidence</span>
        <strong>{mission.evidence?.length ?? 0} records</strong>
      </div>
    </article>
  );
}
