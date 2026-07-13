import { useMemo } from 'react';
import type { GraphEdge, GraphNode, SemanticLevel } from '../semanticZoom.ts';

const LEVELS: SemanticLevel[] = ['orbital', 'deck', 'mission', 'artifact', 'signal'];

export function NeuralCoreHud({
  nodes,
  edges,
  selectedId,
  level,
  onSelect,
  onLevel,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  level: SemanticLevel;
  onSelect: (id: string | null) => void;
  onLevel: (level: SemanticLevel) => void;
}) {
  const selected = nodes.find((node) => node.id === selectedId) ?? null;
  const related = useMemo(
    () =>
      selected
        ? edges.filter((edge) => edge.source === selected.id || edge.target === selected.id)
        : [],
    [edges, selected],
  );

  return (
    <section className="neural-hud" aria-label="Neural Core accessible inspector">
      <div className="neural-hud__toolbar">
        <div>
          <p className="universe-eyebrow">Semantic depth</p>
          <div className="neural-breadcrumb" aria-label="Semantic zoom breadcrumb">
            {LEVELS.map((entry) => (
              <button
                key={entry}
                type="button"
                aria-current={entry === level ? 'step' : undefined}
                onClick={() => onLevel(entry)}
              >
                {entry}
              </button>
            ))}
          </div>
        </div>
        <span className="universe-chip">{nodes.length} reported nodes</span>
      </div>

      <div className="neural-hud__layout">
        <div className="neural-tree" role="tree" aria-label="Authoritative graph nodes" tabIndex={-1}>
          {nodes.length === 0 ? (
            <p className="universe-empty-copy">No graph records are available. Spatial proximity is not treated as an edge.</p>
          ) : (
            nodes.map((node) => (
              <button
                type="button"
                role="treeitem"
                aria-selected={node.id === selectedId}
                key={node.id}
                onClick={() => onSelect(node.id)}
                className={`neural-tree__item neural-tree__item--${node.status}`}
              >
                <span className="neural-tree__glyph" aria-hidden="true" />
                <span>
                  <strong>{node.label}</strong>
                  <small>{node.type} · {node.status}</small>
                </span>
                <span className="mono">v{node.version}</span>
              </button>
            ))
          )}
        </div>

        <aside className="neural-inspector" aria-live="polite">
          {selected ? (
            <>
              <div className="neural-inspector__heading">
                <div>
                  <p className="universe-eyebrow">Selected signal</p>
                  <h3>{selected.label}</h3>
                </div>
                <button type="button" aria-label="Close graph inspector" onClick={() => onSelect(null)}>×</button>
              </div>
              <dl className="universe-definition-grid">
                <div><dt>Type</dt><dd>{selected.type}</dd></div>
                <div><dt>Status</dt><dd>{selected.status}</dd></div>
                <div><dt>Source</dt><dd>{selected.source}</dd></div>
                <div><dt>Observed</dt><dd>{selected.observedAt || 'Not reported'}</dd></div>
                <div><dt>Confidence</dt><dd>{selected.confidence == null ? 'Not reported' : `${Math.round(selected.confidence * 100)}%`}</dd></div>
                <div><dt>Permission</dt><dd>{selected.permission ?? 'Not reported'}</dd></div>
                <div><dt>Cost</dt><dd>{selected.cost == null ? 'Not reported' : String(selected.cost)}</dd></div>
                <div><dt>Explicit edges</dt><dd>{related.length}</dd></div>
              </dl>
              <div className="neural-inspector__evidence">
                <p className="universe-eyebrow">Evidence</p>
                {selected.evidence.length > 0 ? (
                  <ul>{selected.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
                ) : (
                  <p>None reported.</p>
                )}
              </div>
              <button type="button" className="universe-button universe-button--primary" onClick={() => document.querySelector<HTMLElement>('.neural-tree')?.focus()}>
                Jump to 2D hierarchy
              </button>
            </>
          ) : (
            <div className="universe-empty-copy">
              <p className="universe-eyebrow">Inspector</p>
              <h3>Select a reported node</h3>
              <p>Type, provenance, observation time, confidence, evidence, cost, and permission fields appear here without inferred relationships.</p>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
