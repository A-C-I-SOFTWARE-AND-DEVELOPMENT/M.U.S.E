import { useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Float, Line, Sparkles } from '@react-three/drei';
import * as THREE from 'three';

export type WorldKind = 'neural' | 'grid' | 'fusion' | 'gate' | 'forge' | 'fleet' | 'council' | 'studio' | 'network' | 'signal' | 'system';

export const WORLD_META: Record<string, { kind: WorldKind; title: string; hint: string }> = {
  '/': { kind: 'neural', title: 'Neural Conversation', hint: 'Ideas become executable intent' },
  '/chat': { kind: 'neural', title: 'Neural Conversation', hint: 'Ideas become executable intent' },
  '/console': { kind: 'grid', title: 'Mission Control', hint: 'Live command and control surface' },
  '/fusion': { kind: 'fusion', title: 'Fusion Chamber', hint: 'Multiple minds · one answer' },
  '/axiom': { kind: 'gate', title: 'Axiom Gate', hint: 'Evidence before execution' },
  '/steer': { kind: 'neural', title: 'Steering Core', hint: 'Shape intelligence in real time' },
  '/forge': { kind: 'forge', title: 'Creation Forge', hint: 'Goals become working systems' },
  '/fleet': { kind: 'fleet', title: 'Agent Fleet', hint: 'Coordinated autonomous execution' },
  '/agents': { kind: 'fleet', title: 'Agent Workshop', hint: 'Build and deploy digital specialists' },
  '/council': { kind: 'council', title: 'Council Chamber', hint: 'Structured multi-agent deliberation' },
  '/studio': { kind: 'studio', title: 'AAA Studio', hint: 'A cinematic production workspace' },
  '/repo': { kind: 'network', title: 'Repository Matrix', hint: 'Living source topology' },
  '/models': { kind: 'fusion', title: 'Model Arsenal', hint: 'Choose the right intelligence' },
  '/second-brain': { kind: 'neural', title: 'Second Brain', hint: 'Your persistent knowledge field' },
  '/observatory': { kind: 'network', title: 'Neural Observatory', hint: 'Live cognitive topology' },
  '/championship': { kind: 'gate', title: 'Championship Arena', hint: 'Measured intelligence under pressure' },
  '/federation': { kind: 'network', title: 'Federation', hint: 'Connected sovereign intelligence' },
  '/activity': { kind: 'signal', title: 'Activity Pulse', hint: 'Every action in motion' },
  '/share': { kind: 'signal', title: 'Signal Broadcast', hint: 'Publish outcomes, not noise' },
  '/settings': { kind: 'system', title: 'System Core', hint: 'Configure the MUSE runtime' },
};

const cyan = '#7ae0ff';
const violet = '#b388ff';

function CameraDrift() {
  const { camera, pointer } = useThree();
  useFrame((_, delta) => {
    camera.position.x = THREE.MathUtils.damp(camera.position.x, pointer.x * 0.55, 2.5, delta);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, 1.7 + pointer.y * 0.3, 2.5, delta);
    camera.lookAt(0, 0, 0);
  });
  return null;
}

function Core({ scale = 1, color = '#ffffff' }: { scale?: number; color?: string }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }, delta) => {
    if (!ref.current) return;
    ref.current.rotation.x += delta * 0.06;
    ref.current.rotation.y += delta * 0.1;
    ref.current.scale.setScalar(scale * (1 + Math.sin(clock.elapsedTime * 1.1) * 0.035));
  });
  return (
    <group>
      <pointLight color={color} intensity={10} distance={16} decay={2} />
      <mesh ref={ref}>
        <icosahedronGeometry args={[0.7, 4]} />
        <meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={1.5} roughness={0.14} clearcoat={1} clearcoatRoughness={0.16} />
      </mesh>
      <mesh><icosahedronGeometry args={[0.95, 1]} /><meshBasicMaterial color={cyan} transparent opacity={0.12} wireframe /></mesh>
    </group>
  );
}

function OrbitalSystem({ count = 7, radius = 4.3 }: { count?: number; radius?: number }) {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += delta * 0.055; });
  return (
    <group ref={ref}>
      {Array.from({ length: count }).map((_, i) => {
        const a = (i / count) * Math.PI * 2;
        const r = radius * (0.52 + (i % 3) * 0.2);
        return (
          <Float key={i} speed={0.5 + i * 0.04} rotationIntensity={0.25} floatIntensity={0.25}>
            <mesh position={[Math.cos(a) * r, ((i % 3) - 1) * 0.72, Math.sin(a) * r]}>
              <icosahedronGeometry args={[0.2 + (i % 4) * 0.06, 2]} />
              <meshPhysicalMaterial color={i % 2 ? violet : cyan} emissive={i % 2 ? violet : cyan} emissiveIntensity={0.35} roughness={0.3} metalness={0.35} />
            </mesh>
          </Float>
        );
      })}
    </group>
  );
}

function GridWorld() {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += delta * 0.018; });
  return (
    <group ref={ref} rotation={[-0.3, 0, 0]}>
      <gridHelper args={[24, 28, '#35445a', '#111722']} position={[0, -2.2, 0]} />
      {Array.from({ length: 15 }).map((_, i) => (
        <mesh key={i} position={[(i % 5 - 2) * 1.35, -1.75 + (i % 4) * 0.35, (Math.floor(i / 5) - 1) * 1.7]}>
          <boxGeometry args={[0.7, 0.7 + (i % 4) * 0.36, 0.7]} />
          <meshPhysicalMaterial color="#18202d" emissive={i % 3 ? cyan : violet} emissiveIntensity={0.06 + (i % 5) * 0.025} roughness={0.52} metalness={0.25} transparent opacity={0.76} />
        </mesh>
      ))}
    </group>
  );
}

function FusionWorld() {
  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (group.current) { group.current.rotation.y += delta * 0.08; group.current.rotation.z -= delta * 0.012; } });
  return (
    <group ref={group}>
      {[-2.1, 0, 2.1].map((x, i) => <group key={x} position={[x, i === 1 ? 0.3 : -0.2, 0]} scale={i === 1 ? 1.1 : 0.72}><Core color={i === 1 ? '#ffffff' : i ? violet : cyan} /></group>)}
      <Line points={[[-2.1, -0.2, 0], [0, 0.3, 0], [2.1, -0.2, 0]]} color={cyan} transparent opacity={0.25} lineWidth={1} />
      {[1.5, 2.7, 4].map((r, i) => <mesh key={r} rotation={[Math.PI / 2 + i * 0.25, i * 0.4, 0]}><torusGeometry args={[r, 0.009, 6, 160]} /><meshBasicMaterial color={i % 2 ? violet : cyan} transparent opacity={0.12} /></mesh>)}
    </group>
  );
}

function GateWorld() {
  const gate = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (gate.current) gate.current.rotation.y += delta * 0.035; });
  return (
    <group ref={gate}>
      {[0, 1, 2].map((i) => <mesh key={i} rotation={[0, 0, i * Math.PI / 3]} scale={1 + i * 0.45}><torusGeometry args={[1.6, 0.028, 6, 6]} /><meshPhysicalMaterial color={i === 1 ? violet : cyan} emissive={i === 1 ? violet : cyan} emissiveIntensity={0.28} roughness={0.25} metalness={0.7} transparent opacity={0.42 - i * 0.08} /></mesh>)}
      <Core scale={0.72} />
    </group>
  );
}

function ForgeWorld() {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }, delta) => { if (ref.current) { ref.current.rotation.y += delta * 0.04; ref.current.position.y = Math.sin(clock.elapsedTime * 0.7) * 0.15; } });
  return (
    <group ref={ref}>
      <Core scale={0.8} />
      {Array.from({ length: 6 }).map((_, i) => <mesh key={i} position={[Math.cos(i * Math.PI / 3) * 2.2, Math.sin(i * 1.7) * 0.45, Math.sin(i * Math.PI / 3) * 2.2]} rotation={[i, i * 0.4, 0]}><octahedronGeometry args={[0.38, 0]} /><meshPhysicalMaterial color={i % 2 ? violet : cyan} emissive={i % 2 ? violet : cyan} emissiveIntensity={0.18} roughness={0.32} metalness={0.72} /></mesh>)}
      <Sparkles count={120} scale={[6, 4, 6]} size={1.6} speed={0.3} opacity={0.32} color="#ffffff" />
    </group>
  );
}

function CouncilWorld() {
  return <group><Core scale={0.65} /><OrbitalSystem count={8} radius={3.7} />{[2.2, 3.7].map(r => <mesh key={r} rotation-x={Math.PI / 2}><torusGeometry args={[r, 0.01, 6, 160]} /><meshBasicMaterial color={r > 3 ? violet : cyan} transparent opacity={0.11} /></mesh>)}</group>;
}

function StudioWorld() {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += delta * 0.025; });
  return (
    <group ref={ref} rotation={[0.35, -0.25, 0]}>
      {Array.from({ length: 5 }).map((_, i) => <mesh key={i} position={[0, 0, -i * 0.7]} scale={1 - i * 0.09}><boxGeometry args={[5.6, 3.2, 0.035]} /><meshBasicMaterial color={i % 2 ? violet : cyan} wireframe transparent opacity={0.12 - i * 0.012} /></mesh>)}
      <Core scale={0.55} />
    </group>
  );
}

function SignalWorld() {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (ref.current) ref.current.rotation.z = Math.sin(clock.elapsedTime * 0.18) * 0.08; });
  const points = useMemo(() => Array.from({ length: 36 }, (_, i) => new THREE.Vector3((i - 18) * 0.34, Math.sin(i * 0.8) * (0.25 + (i % 4) * 0.08), Math.cos(i * 0.43) * 0.55)), []);
  return <group ref={ref}><Line points={points} color={cyan} lineWidth={1.5} transparent opacity={0.34} /><Line points={points.map(p => p.clone().multiply(new THREE.Vector3(1, -0.55, 1)))} color={violet} lineWidth={0.8} transparent opacity={0.22} /><Core scale={0.52} /></group>;
}

function World({ kind }: { kind: WorldKind }) {
  if (kind === 'grid' || kind === 'system') return <GridWorld />;
  if (kind === 'fusion') return <FusionWorld />;
  if (kind === 'gate') return <GateWorld />;
  if (kind === 'forge') return <ForgeWorld />;
  if (kind === 'council') return <CouncilWorld />;
  if (kind === 'studio') return <StudioWorld />;
  if (kind === 'signal') return <SignalWorld />;
  if (kind === 'fleet' || kind === 'network') return <group><Core scale={0.68} /><OrbitalSystem count={kind === 'fleet' ? 9 : 12} radius={4.6} /></group>;
  return <group><Core /><OrbitalSystem count={6} radius={3.8} /></group>;
}

export default function CinematicWorld({ pathname }: { pathname: string }) {
  const meta = WORLD_META[pathname] ?? WORLD_META['/'];
  if (pathname === '/observatory') return null;
  return (
    <div className="omni-cinematic-world" aria-hidden="true" data-world={meta.kind}>
      <Canvas dpr={[1, 1.6]} camera={{ position: [0, 1.7, 11], fov: 48, near: 0.1, far: 80 }} gl={{ antialias: true, alpha: true, powerPreference: 'high-performance', toneMapping: THREE.ACESFilmicToneMapping }}>
        <fogExp2 attach="fog" args={['#050507', 0.04]} />
        <ambientLight intensity={0.12} color="#b8cbff" />
        <pointLight position={[4, 5, 6]} intensity={5} color="#ffffff" distance={24} />
        <Sparkles count={260} scale={[19, 12, 16]} size={0.7} speed={0.05} opacity={0.22} color="#dcecff" />
        <World kind={meta.kind} />
        <CameraDrift />
      </Canvas>
      <div className="omni-world-label"><span>{meta.title}</span><small>{meta.hint}</small></div>
    </div>
  );
}
