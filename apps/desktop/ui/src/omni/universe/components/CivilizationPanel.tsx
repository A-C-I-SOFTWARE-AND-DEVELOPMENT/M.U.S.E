import type { Civilization, UniverseEntity } from '../types.ts';

export function CivilizationPanel({
  civilization,
  memberships,
  proposals,
}: {
  civilization: Civilization;
  memberships: UniverseEntity[];
  proposals: UniverseEntity[];
}) {
  const members = memberships.filter((membership) => membership.civilization_id === civilization.id);
  const governance = proposals.filter((proposal) => proposal.civilization_id === civilization.id);
  return (
    <article className="civilization-panel universe-panel">
      <header>
        <div><p className="universe-eyebrow">Civilization · v{civilization.version}</p><h3>{civilization.name ?? civilization.id}</h3></div>
        <span className={`universe-chip universe-chip--${civilization.simulation ? 'simulated' : 'observed'}`}>{civilization.simulation ? 'Simulation' : 'Authoritative'}</span>
      </header>
      <p>{civilization.charter || 'No charter text was reported.'}</p>
      <dl className="universe-definition-grid">
        <div><dt>Active members</dt><dd>{members.filter((entry) => entry.status === 'active').length}</dd></div>
        <div><dt>Open proposals</dt><dd>{governance.filter((entry) => entry.status !== 'executed').length}</dd></div>
        <div><dt>Observed</dt><dd>{civilization.updated_at}</dd></div>
        <div><dt>Governance</dt><dd>{civilization.governance ? 'Reported' : 'Not reported'}</dd></div>
      </dl>
    </article>
  );
}
