import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { routeForPath, stationById, STATIONS } from '../catalog.ts';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';
import type { UniverseEntity } from '../types.ts';

function value(entity: UniverseEntity | undefined, key: string): string {
  const current = entity?.[key];
  if (current == null || current === '') return 'Not reported';
  if (Array.isArray(current)) return current.join(', ') || 'None reported';
  if (typeof current === 'object') return 'Reported';
  return String(current);
}

export default function StationsPage() {
  const { stationId } = useParams();
  const [query, setQuery] = useState('');
  const [navigation, setNavigation] = useState<{ origin: string; destination: string; mode: 'manual' | 'autopilot' } | null>(null);
  const snapshot = useUniverseStore((state) => state.snapshot);
  const projected = Array.isArray(snapshot?.stations) ? snapshot.stations : [];
  const route = routeForPath(stationId ? `/stations/${stationId}` : '/stations');
  const selected = stationById(stationId);
  const filtered = useMemo(
    () => STATIONS.filter((station) => `${station.label} ${station.purpose}`.toLowerCase().includes(query.toLowerCase())),
    [query],
  );
  const currentOrigin = typeof snapshot?.navigation_origin === 'string' ? snapshot.navigation_origin : 'Atlas Crown';

  return (
    <UniversePage route={route} eyebrow="Celestial transit" title={selected?.label ?? 'Station Network'} description={selected?.purpose ?? 'Eleven functional stations remain directly reachable through search and buttons, independent of 3D flight controls.'} actions={selected && <Link className="universe-button" to="/stations">All stations</Link>}>
      <UniverseStatusBoundary>
        <div className="stations-layout">
          <section className="station-directory universe-panel">
            <label className="universe-search">Search stations<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or service" /></label>
            <div className="station-directory__list">
              {filtered.map((station) => {
                const entity = projected.find((entry) => entry.id === station.backendId || entry.id === station.id);
                return (
                  <Link key={station.id} to={`/stations/${station.id}`} className="station-row">
                    <span className="station-row__index">{String(STATIONS.indexOf(station) + 1).padStart(2, '0')}</span>
                    <span><strong>{station.label}</strong><small>{station.purpose}</small></span>
                    <span className={`universe-chip universe-chip--${entity ? 'observed' : 'unavailable'}`}>{entity ? value(entity, 'status') : 'Not reported'}</span>
                  </Link>
                );
              })}
            </div>
          </section>

          <aside className="station-inspector universe-panel">
            {selected ? (() => {
              const entity = projected.find((entry) => entry.id === selected.backendId || entry.id === selected.id);
              return <>
                <p className="universe-eyebrow">{selected.deck} deck · {selected.room}</p><h2>{selected.label}</h2><p>{selected.purpose}</p>
                <dl className="universe-definition-grid">
                  <div><dt>Service state</dt><dd>{value(entity, 'status')}</dd></div>
                  <div><dt>Availability</dt><dd>{value(entity, 'service_availability')}</dd></div>
                  <div><dt>Distance</dt><dd>{value(entity, 'distance')}</dd></div>
                  <div><dt>Route</dt><dd>{value(entity, 'route')}</dd></div>
                  <div><dt>Permission</dt><dd>{selected.requiredScope ?? 'No special scope reported'}</dd></div>
                  <div><dt>Observed</dt><dd>{entity?.updated_at ?? 'Not reported'}</dd></div>
                </dl>
                <div className="universe-action-row">
                  <Link className="universe-button universe-button--primary" to={selected.route}>Open operational controls</Link>
                  <button type="button" onClick={() => setNavigation({ origin: currentOrigin, destination: selected.label, mode: 'manual' })}>Manual flight simulation</button>
                  <button type="button" onClick={() => setNavigation({ origin: currentOrigin, destination: selected.label, mode: 'autopilot' })}>Autopilot simulation</button>
                </div>
              </>;
            })() : <div className="universe-empty-copy"><p className="universe-eyebrow">Direct navigation</p><h2>Select a station</h2><p>The accessible directory always remains available, even when celestial rendering is disabled.</p></div>}
          </aside>
        </div>
        {navigation && <section className="navigation-simulation" role="status"><div><p className="universe-eyebrow">Navigation simulation · no operational mutation</p><strong>{navigation.origin} → {navigation.destination}</strong><span>{navigation.mode}</span></div><button type="button" onClick={() => setNavigation(null)}>Cancel simulation</button></section>}
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
