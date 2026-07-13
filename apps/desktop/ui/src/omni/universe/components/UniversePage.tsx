import type { ReactNode } from 'react';
import type { UniverseRoute } from '../catalog.ts';
import { useUniverseStore } from '../store.ts';

export function UniversePage({
  route,
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  route: UniverseRoute;
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const connection = useUniverseStore((state) => state.connection);
  const cursor = useUniverseStore((state) => state.cursor);
  return (
    <div className="universe-page" data-station={route.station} data-room={route.room}>
      <header className="universe-page__hero">
        <div className="universe-page__identity">
          <p className="universe-eyebrow">{eyebrow} · {route.deck} deck</p>
          <h1>{title}</h1>
          <p>{description}</p>
          <p className="universe-page__accessible-summary">2D equivalent: {route.accessibleSummary}</p>
        </div>
        <div className="universe-page__telemetry">
          <span className={`universe-chip universe-chip--${connection}`}>{connection}</span>
          <span className="mono">cursor {cursor}</span>
          {actions}
        </div>
      </header>
      {children}
    </div>
  );
}
