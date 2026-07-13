import { Link } from 'react-router-dom';
import { routeForPath } from '@/universe/catalog';
import { EvidencePanel } from '@/universe/components/EvidencePanel';
import { UniversePage } from '@/universe/components/UniversePage';
import { UniverseStatusBoundary } from '@/universe/components/UniverseStatusBoundary';
import { useUniverseStore } from '@/universe/store';

const STAGES = [
  ['fabrication', '/fabrication'],
  ['game foundry', '/game-foundry'],
  ['cinema stage', '/cinema'],
  ['release dock', '/release'],
] as const;

export default function StudioPage() {
  const route = routeForPath('/studio');
  const snapshot = useUniverseStore((state) => state.snapshot);
  const records = [
    ...(Array.isArray(snapshot?.fabrication_sessions) ? snapshot.fabrication_sessions : []),
    ...(Array.isArray(snapshot?.game_productions) ? snapshot.game_productions : []),
    ...(Array.isArray(snapshot?.cinematic_shots) ? snapshot.cinematic_shots : []),
    ...(Array.isArray(snapshot?.releases) ? snapshot.releases : []),
  ] as Array<Record<string, unknown>>;
  const project = records[0] ?? null;
  return (
    <UniversePage route={route} eyebrow="Foundry deck" title="Production Command" description="One truthful project slate across source fabrication, game production, native-stereo cinema, verification, rights, budgets, and release promotion.">
      <UniverseStatusBoundary>
        {!project && <section className="production-unavailable universe-panel"><p className="universe-eyebrow">No active production</p><h2>The current Universe snapshot reported no project slate</h2><p>Choose a production deck to inspect its requirements. No placeholder project or running pipeline is displayed.</p></section>}
        <section className="studio-pipeline universe-panel">
          <header><div><p className="universe-eyebrow">Project slate</p><h2>{typeof project?.name === 'string' ? project.name : typeof project?.project_id === 'string' ? project.project_id : 'No project selected'}</h2></div><span className={`universe-chip universe-chip--${project ? 'observed' : 'unavailable'}`}>{project ? 'Authoritative record' : 'Unavailable'}</span></header>
          <div className="studio-pipeline__stages">{STAGES.map(([label, path], index) => { const stageRecord = records.find((entry) => String(entry.entity_type ?? '').includes(label.split(' ')[0] ?? '')); return <Link key={path} to={path}><span>{String(index + 1).padStart(2, '0')}</span><strong>{label}</strong><small>{stageRecord ? String(stageRecord.status ?? stageRecord.state ?? 'reported') : 'not reported'}</small></Link>; })}</div>
        </section>
        <div className="production-grid">
          <EvidencePanel title="Budget & rights" eyebrow="Production constraints" record={project} fields={[{ label: 'Budget', path: 'budget' }, { label: 'Actual cost', path: 'actual_cost' }, { label: 'Rights', path: 'rights_status' }, { label: 'Provenance', path: 'provenance' }]} />
          <EvidencePanel title="Verification" eyebrow="Evidence gates" record={project} fields={[{ label: 'Tests', path: 'verification.tests' }, { label: 'Security', path: 'verification.security' }, { label: 'Accessibility', path: 'verification.accessibility' }, { label: 'Performance', path: 'verification.performance' }]} />
          <EvidencePanel title="Release posture" eyebrow="Private → durable" record={project} fields={[{ label: 'Visibility', path: 'visibility' }, { label: 'Stage', path: 'state' }, { label: 'Approval', path: 'approval_id' }, { label: 'Rollback', path: 'rollback' }]} />
        </div>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
