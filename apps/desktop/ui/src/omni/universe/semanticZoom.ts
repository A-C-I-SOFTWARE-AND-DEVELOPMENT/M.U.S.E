import type { UniverseEntity, UniverseSnapshot } from './types.ts';

export type SemanticLevel = 'orbital' | 'deck' | 'mission' | 'artifact' | 'signal';
export type GraphStatus = 'observed' | 'inferred' | 'stale' | 'simulated' | 'contested';

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  position: [number, number, number];
  status: GraphStatus;
  observedAt: string;
  source: string;
  confidence: number | null;
  version: number;
  evidence: string[];
  cost?: string | number | null;
  permission?: string | null;
  parentId?: string | null;
  contestedAlternatives?: string[];
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  status: GraphStatus;
  observedAt: string;
  evidence: string[];
  weight?: number;
}

export interface VisibleGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusters: Array<{ id: string; label: string; nodeIds: string[] }>;
}

function stablePosition(id: string, index: number): [number, number, number] {
  let hash = 2166136261;
  for (const character of id) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  const angle = ((hash >>> 0) / 0xffffffff) * Math.PI * 2 + index * 0.37;
  const radius = 2.2 + ((hash >>> 8) % 100) / 36;
  return [
    Math.cos(angle) * radius,
    (((hash >>> 16) % 100) / 100 - 0.5) * 4.2,
    Math.sin(angle) * radius,
  ];
}

function statusOf(entity: UniverseEntity): GraphStatus {
  if (entity.simulation) return 'simulated';
  if (entity.status === 'contested') return 'contested';
  if (entity.status === 'stale') return 'stale';
  if (entity.status === 'inferred') return 'inferred';
  return 'observed';
}

export function projectUniverseGraph(snapshot: UniverseSnapshot | null): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (!snapshot) return { nodes: [], edges: [] };
  const collections = Object.values(snapshot).filter(Array.isArray) as unknown[][];
  const entities = collections.flat().filter(
    (value): value is UniverseEntity =>
      Boolean(value) && typeof value === 'object' && typeof (value as UniverseEntity).id === 'string',
  );
  const nodes = entities.slice(0, 96).map((entity, index): GraphNode => ({
    id: entity.id,
    label: entity.name ?? entity.id,
    type: entity.entity_type || 'entity',
    position: stablePosition(entity.id, index),
    status: statusOf(entity),
    observedAt: entity.updated_at,
    source: 'muse-universe projection',
    confidence: 1,
    version: entity.version,
    evidence: [`realm:${entity.realm_id}`, `version:${entity.version}`],
  }));
  const rawEdges = Array.isArray(snapshot.graph_edges) ? snapshot.graph_edges : [];
  const edges = rawEdges.flatMap((value, index): GraphEdge[] => {
    if (!value || typeof value !== 'object') return [];
    const record = value as Record<string, unknown>;
    if (typeof record.source !== 'string' || typeof record.target !== 'string') return [];
    return [{
      id: typeof record.id === 'string' ? record.id : `edge-${index}`,
      source: record.source,
      target: record.target,
      type: typeof record.type === 'string' ? record.type : 'reported',
      status: record.status === 'contested' ? 'contested' : 'observed',
      observedAt: typeof record.observed_at === 'string' ? record.observed_at : snapshot.generated_at ?? '',
      evidence: Array.isArray(record.evidence) ? record.evidence.map(String) : [],
      weight: typeof record.weight === 'number' ? record.weight : undefined,
    }];
  });
  return buildVisibleGraph(nodes, edges);
}

export function levelForDistance(distance: number): SemanticLevel {
  if (distance > 900) return 'orbital';
  if (distance > 300) return 'deck';
  if (distance > 90) return 'mission';
  if (distance > 20) return 'artifact';
  return 'signal';
}

function clusterKey(node: GraphNode): string {
  const parent = node.parentId?.trim();
  if (parent) return `parent:${parent}`;
  return `type:${node.type || 'unknown'}`;
}

export function buildVisibleGraph(nodes: GraphNode[], edges: GraphEdge[]): VisibleGraph {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const validEdges = edges.filter(
    (edge) => edge.id && byId.has(edge.source) && byId.has(edge.target),
  );
  const clustered = new Map<string, string[]>();
  for (const node of nodes) {
    const key = clusterKey(node);
    const members = clustered.get(key) ?? [];
    members.push(node.id);
    clustered.set(key, members);
  }
  const clusters = [...clustered.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, nodeIds], index) => ({
      id: `cluster-${index + 1}-${key.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`,
      label: key.replace(/^[^:]+:/, '').replaceAll('-', ' '),
      nodeIds: [...nodeIds].sort(),
    }));
  return { nodes: [...nodes], edges: validEdges, clusters };
}

export function mergeGraphNodes(current: GraphNode[], incoming: GraphNode[]): GraphNode[] {
  const merged = new Map(current.map((node) => [node.id, node]));
  for (const next of incoming) {
    const prior = merged.get(next.id);
    if (!prior || next.version > prior.version) {
      merged.set(next.id, next);
    } else if (next.version === prior.version && next.status === 'contested') {
      merged.set(next.id, {
        ...prior,
        status: 'contested',
        contestedAlternatives: Array.from(
          new Set([...(prior.contestedAlternatives ?? []), ...(next.contestedAlternatives ?? [])]),
        ),
      });
    }
  }
  return [...merged.values()].sort((a, b) => a.id.localeCompare(b.id));
}
