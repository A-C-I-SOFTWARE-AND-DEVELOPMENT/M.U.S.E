import { Link } from 'react-router-dom';
import { DECKS, routeForPath, STATIONS } from '../catalog.ts';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';

export default function AtlasPage() {
  const snapshot = useUniverseStore((state) => state.snapshot);
  const realmId = useUniverseStore((state) => state.realmId);
  const lastAcknowledgedAt = useUniverseStore((state) => state.lastAcknowledgedAt);
  const select = useUniverseStore((state) => state.select);
  const route = routeForPath('/atlas');
  const entityCount = snapshot
    ? Object.values(snapshot).reduce<number>(
        (sum, value) => sum + (Array.isArray(value) ? value.length : 0),
        0,
      )
    : 0;
  const projectedRealm = (Array.isArray(snapshot?.realms) ? snapshot.realms : [])
    .find((entry) => entry.id === (snapshot?.realm_id ?? realmId));
  return (
    <UniversePage
      route={route}
      eyebrow="Muse Neural Core"
      title="Atlas Crown"
      description="A non-rotating command spine, counter-rotating crown habitats, five operational sectors, and one luminous Neural Core—rendered from original procedural aerospace geometry."
      actions={<Link className="universe-button" to="/observatory">Enter Neural Core</Link>}
    >
      <UniverseStatusBoundary>
        <section className="atlas-overview">
          <div className="atlas-overview__core universe-panel">
            <div className="atlas-core-mark" aria-hidden="true"><span /></div>
            <div>
              <p className="universe-eyebrow">Authoritative realm projection</p>
              <h2>{projectedRealm?.name ?? projectedRealm?.id ?? 'No realm reported'}</h2>
              <p>{entityCount} projected records · {snapshot?.viewer?.display_name ?? snapshot?.viewer?.actor_id ?? 'viewer identity not reported'}</p>
              <p className="mono">{snapshot?.generated_at ? `observed ${snapshot.generated_at}` : lastAcknowledgedAt ? `acknowledged ${lastAcknowledgedAt}` : 'snapshot timestamp not reported'}</p>
            </div>
          </div>
          <div className="atlas-decks">
            {DECKS.map((deck) => {
              const stations = STATIONS.filter((station) => station.deck === deck.id);
              return (
                <article key={deck.id} className="atlas-deck universe-panel">
                  <header><span>{deck.sector}</span><div><p className="universe-eyebrow">Sector arc</p><h3>{deck.label}</h3></div></header>
                  <p>{deck.purpose}</p>
                  <div className="atlas-deck__routes">
                    {stations.map((station) => <Link key={station.id} to={station.route} onClick={() => select(station.id)}>{station.label}<span>→</span></Link>)}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
