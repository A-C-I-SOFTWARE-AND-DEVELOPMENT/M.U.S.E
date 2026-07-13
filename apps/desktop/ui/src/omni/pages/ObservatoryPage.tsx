import { useMemo, useState } from 'react';
import { routeForPath } from '@/universe/catalog';
import { EvidencePanel } from '@/universe/components/EvidencePanel';
import { MissionPanel } from '@/universe/components/MissionPanel';
import { NeuralCoreHud } from '@/universe/components/NeuralCoreHud';
import { UniversePage } from '@/universe/components/UniversePage';
import { UniverseStatusBoundary } from '@/universe/components/UniverseStatusBoundary';
import { projectUniverseGraph, type SemanticLevel } from '@/universe/semanticZoom';
import { useUniverseStore } from '@/universe/store';
import type { Mission, UniverseEntity } from '@/universe/types';
import { useNexusStore } from '@/store/useNexusStore';

export default function ObservatoryPage() {
  const route = routeForPath('/observatory');
  const wallpaper = useNexusStore((state) => state.wallpaper);
  const setWallpaper = useNexusStore((state) => state.setWallpaper);
  const snapshot = useUniverseStore((state) => state.snapshot);
  const connection = useUniverseStore((state) => state.connection);
  const cursor = useUniverseStore((state) => state.cursor);
  const lastAcknowledgedAt = useUniverseStore((state) => state.lastAcknowledgedAt);
  const refresh = useUniverseStore((state) => state.refresh);
  const [semanticLevel, setSemanticLevel] = useState<SemanticLevel>('orbital');
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const graph = useMemo(() => projectUniverseGraph(snapshot), [snapshot]);
  const missions = (Array.isArray(snapshot?.missions) ? snapshot.missions : []) as Mission[];
  const stations = (Array.isArray(snapshot?.stations) ? snapshot.stations : []) as UniverseEntity[];
  const loading = connection === 'idle' || connection === 'loading';
  const graphEvidence: Record<string, unknown> = {
    node_count: graph.nodes.length,
    explicit_edge_count: graph.edges.length,
    cursor,
    last_acknowledged_at: lastAcknowledgedAt,
  };

  const inspector = (
    <NeuralCoreHud
      nodes={graph.nodes}
      edges={graph.edges}
      selectedId={selectedNode}
      level={semanticLevel}
      onSelect={setSelectedNode}
      onLevel={setSemanticLevel}
    />
  );

  if (wallpaper) {
    return (
      <div className="fixed inset-0 z-50 overflow-auto p-4" style={{ background: 'rgba(2,3,6,.68)' }}>
        <header className="mx-auto mb-3 flex w-full max-w-[1120px] items-center justify-between gap-4">
          <div>
            <p className="universe-eyebrow">Shared authenticated projection</p>
            <h1 className="m-0 text-[20px] font-semibold">Muse Neural Core</h1>
            <p className="mono m-0 text-[9px] text-[var(--ink-faint)]">{connection} · cursor {cursor} · {graph.edges.length} explicit edges</p>
          </div>
          <button type="button" onClick={() => setWallpaper(false)} className="universe-button">Exit focus view</button>
        </header>
        <div className="mx-auto w-full max-w-[1120px]">{inspector}</div>
      </div>
    );
  }

  return (
    <UniversePage
      route={route}
      eyebrow="Muse Neural Core"
      title="Neural Observatory"
      description="The spatial Core and accessible hierarchy share one authenticated Universe snapshot. Only reported graph edges appear; proximity never becomes an invented relationship."
      actions={
        <>
          <button type="button" className="universe-button" onClick={() => setWallpaper(true)}>Focus view</button>
          <button type="button" className="universe-button" disabled={loading} onClick={() => void refresh()}>{loading ? 'Reading…' : 'Refresh from cursor'}</button>
        </>
      }
    >
      <UniverseStatusBoundary>
        <div className="production-grid">
          <EvidencePanel
            title="Projection evidence"
            eyebrow="Same state as the spatial Core"
            record={graphEvidence}
            fields={[
              { label: 'Reported nodes', path: 'node_count' },
              { label: 'Explicit edges', path: 'explicit_edge_count' },
              { label: 'Reconnect cursor', path: 'cursor' },
              { label: 'Last acknowledgement', path: 'last_acknowledged_at' },
            ]}
          />
          <EvidencePanel
            title="Station signal"
            eyebrow="Authoritative station projection"
            record={(stations[0] as Record<string, unknown> | undefined) ?? null}
            fields={[
              { label: 'Station', path: 'name' },
              { label: 'Identifier', path: 'id' },
              { label: 'State', path: 'status' },
              { label: 'Observed', path: 'updated_at' },
            ]}
          />
        </div>

        <div className="mt-3">{inspector}</div>

        <section className="mt-3" aria-labelledby="observatory-missions">
          <div className="mb-2 flex items-center justify-between">
            <div><p className="universe-eyebrow">Execution signals</p><h2 id="observatory-missions" className="m-0 text-[16px]">Reported missions</h2></div>
            <span className="universe-chip">{missions.length} records</span>
          </div>
          {missions.length > 0 ? (
            <div className="mission-grid">{missions.slice(0, 6).map((mission) => <MissionPanel key={mission.id} mission={mission} />)}</div>
          ) : (
            <div className="universe-panel universe-empty-copy">No mission records were reported by the current snapshot.</div>
          )}
        </section>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
