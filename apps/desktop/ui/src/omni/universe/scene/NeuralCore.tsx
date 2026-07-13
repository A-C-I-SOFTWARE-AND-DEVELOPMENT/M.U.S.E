import { Line } from '@react-three/drei';
import type { GraphEdge, GraphNode } from '../semanticZoom.ts';
import type { FidelitySettings } from '../fidelity.ts';

const STATUS_COLOR: Record<GraphNode['status'], string> = {
  observed: '#dce8eb',
  inferred: '#7ea2ac',
  stale: '#7a7e82',
  simulated: '#9d8db7',
  contested: '#c5a96a',
};

export function NeuralCore({
  nodes,
  edges,
  settings,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  settings: FidelitySettings;
}) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  return (
    <group name="neural-core-graph">
      <pointLight color="#dff8ff" intensity={10} distance={14} decay={2} />
      <mesh>
        <sphereGeometry args={[1.25, settings.geometrySegments, Math.max(18, settings.geometrySegments / 2)]} />
        <meshPhysicalMaterial
          color="#eafaff"
          emissive="#bdeeff"
          emissiveIntensity={1.15}
          roughness={0.07}
          transmission={settings.materialTransmission}
          transparent
          opacity={0.92}
          clearcoat={1}
          clearcoatRoughness={0.08}
        />
      </mesh>
      {nodes.slice(0, 96).map((node) => (
        <mesh key={node.id} position={node.position} scale={node.status === 'contested' ? 0.17 : 0.12}>
          {node.status === 'contested' ? <octahedronGeometry args={[1, 0]} /> : <sphereGeometry args={[1, 10, 8]} />}
          <meshStandardMaterial
            color={STATUS_COLOR[node.status]}
            emissive={STATUS_COLOR[node.status]}
            emissiveIntensity={0.32}
            metalness={0.35}
            roughness={0.4}
          />
        </mesh>
      ))}
      {edges.slice(0, 160).map((edge) => {
        const source = byId.get(edge.source);
        const target = byId.get(edge.target);
        if (!source || !target) return null;
        return (
          <Line
            key={edge.id}
            points={[source.position, target.position]}
            color={edge.status === 'contested' ? '#b9a36d' : '#758d95'}
            transparent
            opacity={0.2 + Math.min(0.32, edge.weight ?? 0)}
            lineWidth={0.45}
          />
        );
      })}
    </group>
  );
}
