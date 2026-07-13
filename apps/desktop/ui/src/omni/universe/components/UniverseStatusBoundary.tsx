import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useUniverseStore, type UniverseConnection } from '../store.ts';

interface StatusCopy {
  eyebrow: string;
  title: string;
  body: string;
}

const COPY: Record<Exclude<UniverseConnection, 'online'>, StatusCopy> = {
  idle: {
    eyebrow: 'Universe link',
    title: 'Atlas is not connected',
    body: 'Connect to the authenticated universe service to load operational records.',
  },
  loading: {
    eyebrow: 'Universe link',
    title: 'Reading authoritative state',
    body: 'The last acknowledged cursor will be preserved if this request is interrupted.',
  },
  empty: {
    eyebrow: 'Authoritative empty state',
    title: 'No universe entities were reported',
    body: 'The service responded successfully, but this realm has no projected records yet.',
  },
  offline: {
    eyebrow: 'Connection interrupted',
    title: 'Working from the last acknowledged snapshot',
    body: 'No new event or command is shown as complete until the gateway reconnects.',
  },
  denied: {
    eyebrow: 'Permission boundary',
    title: 'Universe access was not authorized',
    body: 'Pair this device or request a realm role. Client-entered authority is never accepted.',
  },
  conflict: {
    eyebrow: 'Version conflict',
    title: 'Authoritative state changed',
    body: 'Refresh the current version before reviewing or retrying the same command intent.',
  },
  degraded: {
    eyebrow: 'Service degraded',
    title: 'Some Atlas services are unavailable',
    body: 'Existing evidence remains visible. Missing production APIs are not simulated.',
  },
  error: {
    eyebrow: 'Universe error',
    title: 'Atlas could not read this realm',
    body: 'The failure is preserved below with its correlation evidence when supplied.',
  },
};

export function UniverseStatusBoundary({ children }: { children: ReactNode }) {
  const connection = useUniverseStore((state) => state.connection);
  const snapshot = useUniverseStore((state) => state.snapshot);
  const problem = useUniverseStore((state) => state.problem);
  const staleAt = useUniverseStore((state) => state.staleAt);
  const refresh = useUniverseStore((state) => state.refresh);
  const connect = useUniverseStore((state) => state.connect);

  if (connection === 'online') return <>{children}</>;
  const copy = COPY[connection];
  const canRenderContent =
    connection === 'empty' ||
    connection === 'offline' ||
    connection === 'conflict' ||
    connection === 'degraded' ||
    connection === 'error';

  return (
    <div className="universe-status-stack">
      <section className={`universe-status universe-status--${connection}`} role="status" aria-live="polite">
        <div>
          <p className="universe-eyebrow">{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
          <p>{problem?.message || copy.body}</p>
          <div className="universe-status__evidence mono">
            {staleAt && <span>stale since {new Date(staleAt).toLocaleString()}</span>}
            {problem?.status != null && <span>HTTP {problem.status}</span>}
            {problem?.currentVersion != null && <span>current version {problem.currentVersion}</span>}
            {problem?.correlationId && <span>correlation {problem.correlationId}</span>}
          </div>
        </div>
        <div className="universe-status__actions">
          <button type="button" onClick={() => void (snapshot ? refresh() : connect())}>
            {connection === 'conflict' ? 'Refresh authority' : 'Retry connection'}
          </button>
          {(connection === 'denied' || connection === 'idle' || connection === 'degraded') && (
            <Link className="universe-button universe-button--quiet" to="/settings">
              Connection settings
            </Link>
          )}
        </div>
      </section>
      {canRenderContent && children}
    </div>
  );
}
