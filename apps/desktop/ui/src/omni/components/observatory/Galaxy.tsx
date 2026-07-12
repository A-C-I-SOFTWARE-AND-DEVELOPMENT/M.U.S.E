import { Suspense, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Billboard, Line, OrbitControls, Sparkles, Text } from '@react-three/drei';
import * as THREE from 'three';
import type { ObsCluster, ObsSnapshot } from '@/lib/types';

interface Props {
  snapshot: ObsSnapshot | null;
  pulses: Record<string, number>;
  queuePulse: number;
  height?: number;
}

const TYPE_TINT: Record<string, string> = {
  code: '#7ae0ff', docs: '#8fb4ff', test: '#f5c451', memory: '#b388ff',
  skills: '#8ad9e8', agent: '#c79bff', model: '#6ad2ff', system: '#aab2c4',
};

function dominantType(mix: Record<string, number>): string {
  return Object.entries(mix).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'system';
}

function normalizePositions(clusters: ObsCluster[]): Map<string, THREE.Vector3> {
  const max = Math.max(1, ...clusters.flatMap((cluster) => cluster.pos.map(Math.abs)));
  const result = new Map<string, THREE.Vector3>();
  clusters.forEach((cluster) => {
    const [x, y, z] = cluster.pos;
    result.set(cluster.id, new THREE.Vector3((x / max) * 8.5, (y / max) * 5.2, (z / max) * 8.5));
  });
  return result;
}

function CameraRig() {
  const { camera, pointer } = useThree();
  useFrame((_, delta) => {
    camera.position.x = THREE.MathUtils.damp(camera.position.x, pointer.x * 0.75, 2.2, delta);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, 3.8 + pointer.y * 0.42, 2.2, delta);
    camera.lookAt(0, 0, 0);
  });
  return null;
}

function NeuralCore({ queuePulse }: { queuePulse: number }) {
  const core = useRef<THREE.Mesh>(null);
  const shell = useRef<THREE.Mesh>(null);
  useFrame(({ clock }, delta) => {
    const pulse = 1 + Math.sin(clock.elapsedTime * 1.35) * 0.035 + queuePulse * 0.12;
    if (core.current) {
      core.current.scale.setScalar(THREE.MathUtils.damp(core.current.scale.x, pulse, 5, delta));
      core.current.rotation.y += delta * 0.09;
    }
    if (shell.current) {
      shell.current.rotation.x += delta * 0.025;
      shell.current.rotation.y -= delta * 0.04;
    }
  });
  return (
    <group>
      <pointLight color="#ffffff" intensity={22 + queuePulse * 18} distance={28} decay={2} />
      <pointLight color="#7ae0ff" intensity={10} distance={18} decay={2} />
      <mesh ref={core}>
        <icosahedronGeometry args={[1.05, 7]} />
        <meshPhysicalMaterial color="#ffffff" emissive="#dff8ff" emissiveIntensity={2.6} roughness={0.12} metalness={0.04} transmission={0.12} thickness={1.2} />
      </mesh>
      <mesh ref={shell}>
        <icosahedronGeometry args={[1.43, 2]} />
        <meshBasicMaterial color="#7ae0ff" wireframe transparent opacity={0.15} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh rotation-x={Math.PI / 2}>
        <torusGeometry args={[1.75, 0.012, 8, 180]} />
        <meshBasicMaterial color="#b388ff" transparent opacity={0.42} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  );
}

function ClusterWorld({ cluster, position, pulse, selected, onSelect }: {
  cluster: ObsCluster; position: THREE.Vector3; pulse: number; selected: boolean; onSelect: () => void;
}) {
  const group = useRef<THREE.Group>(null);
  const atmosphere = useRef<THREE.Mesh>(null);
  const type = dominantType(cluster.type_mix);
  const color = TYPE_TINT[type] ?? '#aab2c4';
  const measuredHeat = cluster.heat ?? 0;
  const radius = THREE.MathUtils.clamp(0.24 + Math.log10(Math.max(10, cluster.members)) * 0.17 + cluster.radius * 0.025, 0.42, 1.08);

  useFrame(({ clock }, delta) => {
    if (!group.current) return;
    group.current.rotation.y += delta * (0.04 + measuredHeat * 0.1);
    const target = 1 + pulse * 0.34 + (selected ? 0.08 : 0);
    group.current.scale.setScalar(THREE.MathUtils.damp(group.current.scale.x, target, 7, delta));
    if (atmosphere.current) {
      const material = atmosphere.current.material as THREE.MeshBasicMaterial;
      material.opacity = 0.05 + measuredHeat * 0.1 + pulse * 0.24 + Math.sin(clock.elapsedTime * 1.8 + position.x) * 0.012;
    }
  });

  return (
    <group position={position}>
      <group ref={group} onClick={(event) => { event.stopPropagation(); onSelect(); }}>
        <mesh castShadow receiveShadow>
          <sphereGeometry args={[radius, 64, 64]} />
          <meshPhysicalMaterial
            color={cluster.heat == null ? '#526071' : color}
            emissive={color}
            emissiveIntensity={cluster.heat == null ? 0.04 : 0.16 + measuredHeat * 0.72 + pulse * 1.4}
            roughness={0.48 - measuredHeat * 0.18}
            metalness={0.14}
            clearcoat={0.72}
            clearcoatRoughness={0.28}
          />
        </mesh>
        <mesh ref={atmosphere} scale={1.16}>
          <sphereGeometry args={[radius, 48, 48]} />
          <meshBasicMaterial color={color} transparent opacity={0.08} side={THREE.BackSide} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
        {pulse > 0.02 && (
          <mesh scale={1.3 + pulse * 0.7}>
            <sphereGeometry args={[radius, 32, 32]} />
            <meshBasicMaterial color={color} transparent opacity={pulse * 0.14} wireframe blending={THREE.AdditiveBlending} depthWrite={false} />
          </mesh>
        )}
      </group>
      <Billboard position={[0, -radius - 0.34, 0]} follow>
        <Text fontSize={0.2} color={selected ? '#ffffff' : '#aab2c4'} anchorX="center" anchorY="middle" outlineWidth={0.008} outlineColor="#050507" maxWidth={3.2}>
          {cluster.label}
        </Text>
      </Billboard>
    </group>
  );
}

function GalaxyScene({ snapshot, pulses, queuePulse, selectedId, setSelectedId }: {
  snapshot: ObsSnapshot; pulses: Record<string, number>; queuePulse: number;
  selectedId: string | null; setSelectedId: (id: string | null) => void;
}) {
  const clusters = snapshot.graph.available ? snapshot.graph.clusters : [];
  const positions = useMemo(() => normalizePositions(clusters), [clusters]);
  const edgeMax = Math.max(1, ...snapshot.graph.cluster_edges.map((edge) => edge.weight));

  return (
    <>
      <color attach="background" args={['#020205']} />
      <fogExp2 attach="fog" args={['#05070d', 0.025]} />
      <ambientLight intensity={0.11} color="#b8cbff" />
      <directionalLight position={[8, 10, 5]} intensity={0.55} color="#ffffff" />
      <NeuralCore queuePulse={queuePulse} />

      <Sparkles count={900} scale={[28, 18, 28]} size={0.8} speed={0.08} opacity={0.36} color="#dcecff" noise={1.2} />
      <Sparkles count={180} scale={[18, 11, 18]} size={2.2} speed={0.14} opacity={0.16} color="#7ae0ff" noise={1} />

      {[2.3, 4.4, 6.5, 8.6].map((radius, index) => (
        <mesh key={radius} rotation={[Math.PI / 2.25 + index * 0.025, 0, index * 0.4]}>
          <torusGeometry args={[radius, 0.006, 6, 220]} />
          <meshBasicMaterial color={index % 2 ? '#b388ff' : '#7ae0ff'} transparent opacity={0.075} depthWrite={false} />
        </mesh>
      ))}

      {snapshot.graph.cluster_edges.map((edge) => {
        const start = positions.get(edge.a);
        const end = positions.get(edge.b);
        if (!start || !end) return null;
        const active = Math.max(pulses[edge.a] ?? 0, pulses[edge.b] ?? 0);
        const strength = edge.weight / edgeMax;
        const midpoint = start.clone().add(end).multiplyScalar(0.5);
        midpoint.y += start.distanceTo(end) * 0.12;
        const curve = new THREE.QuadraticBezierCurve3(start, midpoint, end);
        return (
          <Line
            key={`${edge.a}:${edge.b}`}
            points={curve.getPoints(28)}
            color={edge.heat != null || active > 0.02 ? '#7ae0ff' : '#374052'}
            lineWidth={0.35 + strength * 1.25 + active * 1.8}
            transparent
            opacity={0.14 + strength * 0.28 + active * 0.38}
          />
        );
      })}

      {clusters.map((cluster) => (
        <ClusterWorld
          key={cluster.id}
          cluster={cluster}
          position={positions.get(cluster.id) ?? new THREE.Vector3()}
          pulse={pulses[cluster.id] ?? 0}
          selected={selectedId === cluster.id}
          onSelect={() => setSelectedId(selectedId === cluster.id ? null : cluster.id)}
        />
      ))}

      <CameraRig />
      <OrbitControls makeDefault enablePan={false} minDistance={7} maxDistance={24} autoRotate autoRotateSpeed={0.16} dampingFactor={0.045} minPolarAngle={0.45} maxPolarAngle={Math.PI - 0.45} />
    </>
  );
}

export function Galaxy({ snapshot, pulses, queuePulse, height = 420 }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = snapshot?.graph.clusters.find((cluster) => cluster.id === selectedId) ?? null;
  const live = Boolean(snapshot?.graph.available);

  return (
    <div className="observatory-galaxy" style={{ height }} data-live={live}>
      {snapshot && live ? (
        <Canvas
          dpr={[1, 2.25]}
          camera={{ position: [0, 3.8, 15], fov: 46, near: 0.1, far: 120 }}
          gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', toneMapping: THREE.ACESFilmicToneMapping }}
          onPointerMissed={() => setSelectedId(null)}
        >
          <Suspense fallback={null}>
            <GalaxyScene snapshot={snapshot} pulses={pulses} queuePulse={queuePulse} selectedId={selectedId} setSelectedId={setSelectedId} />
          </Suspense>
        </Canvas>
      ) : (
        <Canvas dpr={[1, 2]} camera={{ position: [0, 2.4, 14], fov: 48 }} gl={{ antialias: true, powerPreference: 'high-performance' }}>
          <color attach="background" args={['#020205']} />
          <fogExp2 attach="fog" args={['#05070d', 0.035]} />
          <Sparkles count={650} scale={[26, 16, 24]} size={0.8} speed={0.04} opacity={0.22} color="#dcecff" />
          <group scale={0.72}><NeuralCore queuePulse={0} /></group>
          <CameraRig />
          <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.08} />
        </Canvas>
      )}

      <div className="observatory-galaxy__hud" aria-hidden="true">
        <span>NEURAL SPACE</span><span>{live ? 'SYNCHRONIZED' : 'AWAITING TELEMETRY'}</span>
      </div>
      <div className="observatory-galaxy__reticle" aria-hidden="true" />
      {selected && (
        <aside className="observatory-inspector" aria-live="polite">
          <button onClick={() => setSelectedId(null)} aria-label="Close node inspector">×</button>
          <div className="hud-label">LIVE CLUSTER</div>
          <h3>{selected.label}</h3>
          <div className="observatory-inspector__grid">
            <span>Nodes<strong>{selected.members.toLocaleString()}</strong></span>
            <span>Heat<strong>{selected.heat == null ? 'gated' : `${Math.round(selected.heat * 100)}%`}</strong></span>
            <span>Type<strong>{dominantType(selected.type_mix)}</strong></span>
            <span>Pulse<strong>{Math.round((pulses[selected.id] ?? 0) * 100)}%</strong></span>
          </div>
          <div className="observatory-inspector__mix">
            {Object.entries(selected.type_mix).sort((a, b) => b[1] - a[1]).map(([type, share]) => (
              <div key={type}><span>{type}</span><i style={{ width: `${Math.max(2, share * 100)}%` }} /></div>
            ))}
          </div>
        </aside>
      )}
    </div>
  );
}
