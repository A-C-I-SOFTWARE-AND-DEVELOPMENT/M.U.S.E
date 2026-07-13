import { Link } from 'react-router-dom';
import { routeForPath } from '../catalog.ts';
import { EvidencePanel } from '../components/EvidencePanel.tsx';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';

const LANES = [
  'concept', 'gdd', 'narrative', 'characters', 'systems', 'economy', 'accessibility',
  'concept_art', 'mesh', 'retopology', 'uv', 'pbr', 'rigging', 'animation', 'lod',
  'gameplay', 'ai', 'physics', 'audio', 'ui', 'save', 'multiplayer', 'analytics',
  'world_streaming', 'procedural_generation', 'tests', 'packaging', 'release',
] as const;

function laneState(record: Record<string, unknown> | null, lane: string): string {
  const lanes = record?.lanes;
  if (!lanes || typeof lanes !== 'object') return 'Not reported';
  const value = (lanes as Record<string, unknown>)[lane];
  if (value && typeof value === 'object') return String((value as Record<string, unknown>).status ?? 'Reported');
  return value == null ? 'Not reported' : String(value);
}

export default function GameFoundryPage() {
  const route = routeForPath('/game-foundry');
  const snapshot = useUniverseStore((state) => state.snapshot);
  const productions = Array.isArray(snapshot?.game_productions) ? snapshot.game_productions : [];
  const record = (productions[0] ?? null) as Record<string, unknown> | null;
  const playable = record?.playable === true && record?.engine_validation === 'passed';
  return (
    <UniversePage route={route} eyebrow="AAA Game Foundry" title="Production Evidence Matrix" description="A source-complete game is a network of explicit lanes, dependencies, engine gates, tests, budgets, packages, rights, storefronts, release channels, and rollback—not a progress animation." actions={<Link className="universe-button" to="/studio">Production Command</Link>}>
      <UniverseStatusBoundary>
        {!record && <section className="production-unavailable universe-panel"><p className="universe-eyebrow">Game production unavailable</p><h2>No Game Foundry manifest was reported</h2><p>All lanes remain “Not reported.” No synthetic scoring, placeholder progress, or playable claim is displayed.</p></section>}
        <section className="game-manifest universe-panel">
          <header><div><p className="universe-eyebrow">GDD · dependencies · complete lanes</p><h2>{typeof record?.title === 'string' ? record.title : 'No production selected'}</h2></div><span className={`universe-chip universe-chip--${playable ? 'live' : 'unavailable'}`}>{playable ? 'Playable package verified' : 'Not verified playable'}</span></header>
          <div className="game-lanes" role="list" aria-label="Game production lanes">{LANES.map((lane) => <div key={lane} role="listitem"><span>{lane.replaceAll('_', ' ')}</span><strong>{laneState(record, lane)}</strong></div>)}</div>
        </section>
        <div className="production-grid">
          <EvidencePanel title="Engine validation" eyebrow="Installed runtime evidence" record={record} fields={[{ label: 'Engine', path: 'engine_target' }, { label: 'Version', path: 'engine_version' }, { label: 'Availability', path: 'engine_availability' }, { label: 'Validation', path: 'engine_validation' }, { label: 'Build log', path: 'build_log' }, { label: 'Smoke gate', path: 'smoke_status' }]} />
          <EvidencePanel title="Performance budgets" eyebrow="Measured targets" record={record} fields={[{ label: 'Frame time', path: 'budgets.frame_time_ms' }, { label: 'Memory', path: 'budgets.memory_mb' }, { label: 'Draw calls', path: 'budgets.draw_calls' }, { label: 'Streaming', path: 'budgets.world_streaming' }, { label: 'Network', path: 'budgets.network' }, { label: 'Accessibility', path: 'accessibility_status' }]} />
          <EvidencePanel title="Asset reviews" eyebrow="Art-to-runtime chain" record={record} fields={[{ label: 'Concept art', path: 'reviews.concept_art' }, { label: 'Topology', path: 'reviews.topology' }, { label: 'UV / PBR', path: 'reviews.pbr' }, { label: 'Rig / animation', path: 'reviews.animation' }, { label: 'LOD', path: 'reviews.lod' }, { label: 'Provenance', path: 'reviews.provenance' }]} />
          <EvidencePanel title="Package artifacts" eyebrow="Build and smoke evidence" record={record} fields={[{ label: 'Platform', path: 'package.platform' }, { label: 'Artifact', path: 'package.path' }, { label: 'Hash', path: 'package.hash' }, { label: 'Unit / functional', path: 'tests' }, { label: 'Multiplayer', path: 'multiplayer_validation' }, { label: 'Playable', path: 'playable' }]} />
          <EvidencePanel title="Crash & telemetry" eyebrow="Operational quality" record={record} fields={[{ label: 'Crash reports', path: 'crash_reports' }, { label: 'Telemetry mode', path: 'telemetry_mode' }, { label: 'Save migration', path: 'save_migration' }, { label: 'Analytics consent', path: 'analytics_consent' }]} />
          <EvidencePanel title="Rights and ratings" eyebrow="Store readiness" record={record} fields={[{ label: 'Rights', path: 'rights_status' }, { label: 'Rating', path: 'rating_status' }, { label: 'Store checklist', path: 'store_readiness' }, { label: 'Release channels', path: 'release_channels' }, { label: 'Rollback', path: 'rollback' }]}><div className="universe-action-row"><button type="button" disabled={!record || !playable}>Open verified package</button><Link className="universe-button" to="/release">Release channels</Link></div></EvidencePanel>
        </div>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
