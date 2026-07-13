import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { FidelitySettings } from '../fidelity.ts';

const HULL = '#7f8991';
const HULL_DARK = '#252b31';
const CERAMIC = '#c2c9ca';
const GLASS = '#d9f6ff';

function HullMaterial({ roughness = 0.42 }: { roughness?: number }) {
  return <meshPhysicalMaterial color={HULL} metalness={0.88} roughness={roughness} clearcoat={0.04} />;
}

function DarkMaterial() {
  return <meshStandardMaterial color={HULL_DARK} metalness={0.76} roughness={0.58} />;
}

function CrownRing({
  radius,
  direction,
  settings,
  tilt,
}: {
  radius: number;
  direction: 1 | -1;
  settings: FidelitySettings;
  tilt: number;
}) {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (settings.motion && ref.current) ref.current.rotation.z += delta * 0.045 * direction;
  });
  return (
    <group ref={ref} rotation={[tilt, 0, direction * 0.12]}>
      <mesh>
        <torusGeometry args={[radius, 0.16, 12, settings.geometrySegments]} />
        <HullMaterial roughness={0.34} />
      </mesh>
      {Array.from({ length: 16 }, (_, index) => {
        const angle = (index / 16) * Math.PI * 2;
        return (
          <group key={index} rotation={[0, 0, angle]}>
            <mesh position={[radius, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <boxGeometry args={[0.34, 0.08, 0.14]} />
              <meshStandardMaterial color={index % 4 === 0 ? CERAMIC : HULL_DARK} metalness={0.72} roughness={0.5} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function SectorArcs({ settings }: { settings: FidelitySettings }) {
  return (
    <group rotation={[Math.PI / 2, 0, 0]}>
      {Array.from({ length: 5 }, (_, index) => {
        const angle = (index / 5) * Math.PI * 2;
        return (
          <group key={index} rotation={[0, 0, angle]}>
            <mesh>
              <torusGeometry args={[5.1, 0.27, 14, settings.geometrySegments, 0.82]} />
              <meshPhysicalMaterial
                color={index === 0 ? '#aeb5b8' : HULL}
                metalness={0.9}
                roughness={0.36 + index * 0.025}
              />
            </mesh>
            <mesh position={[4.6, 0.25, 0]}>
              <boxGeometry args={[1.3, 0.36, 0.48]} />
              <DarkMaterial />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function DockAssembly({ index }: { index: number }) {
  const angle = (index / 4) * Math.PI * 2 + Math.PI / 4;
  const x = Math.cos(angle) * 6.35;
  const z = Math.sin(angle) * 6.35;
  return (
    <group position={[x, 0, z]} rotation={[0, -angle, 0]}>
      <mesh rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.44, 0.58, 1.55, 16]} />
        <HullMaterial roughness={0.48} />
      </mesh>
      <mesh position={[0.9, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <torusGeometry args={[0.43, 0.08, 10, 30]} />
        <meshStandardMaterial color="#b8c0c3" metalness={0.82} roughness={0.42} />
      </mesh>
      <mesh position={[1.2, 0, 0]}>
        <boxGeometry args={[0.4, 0.92, 0.92]} />
        <DarkMaterial />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh key={side} position={[0.2, side * 0.72, 0]}>
          <boxGeometry args={[1.65, 0.04, 0.42]} />
          <meshStandardMaterial color="#273848" metalness={0.52} roughness={0.7} />
        </mesh>
      ))}
    </group>
  );
}

function RadiatorCrown() {
  return (
    <group>
      {Array.from({ length: 6 }, (_, index) => {
        const angle = (index / 6) * Math.PI * 2;
        return (
          <group key={index} rotation={[0, angle, 0]}>
            <mesh position={[3.4, index % 2 ? 1.4 : -1.4, 0]} rotation={[0, 0, 0.08]}>
              <boxGeometry args={[2.7, 0.035, 1.15]} />
              <meshStandardMaterial color="#1f3440" metalness={0.4} roughness={0.76} />
            </mesh>
            <mesh position={[2.05, index % 2 ? 1.4 : -1.4, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.055, 0.055, 1.1, 8]} />
              <DarkMaterial />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

export function AtlasCrown({ settings }: { settings: FidelitySettings }) {
  return (
    <group name="atlas-crown" rotation={[0.08, -0.3, -0.04]}>
      <group name="non-rotating-spine">
        <mesh>
          <cylinderGeometry args={[0.42, 0.58, 10.8, 20]} />
          <HullMaterial roughness={0.4} />
        </mesh>
        {[-4.2, -2.1, 2.1, 4.2].map((y) => (
          <mesh key={y} position={[0, y, 0]}>
            <cylinderGeometry args={[0.86, 0.86, 0.48, 20]} />
            <DarkMaterial />
          </mesh>
        ))}
        <mesh position={[0, 5.8, 0]}>
          <cylinderGeometry args={[0.06, 0.12, 3.2, 8]} />
          <meshStandardMaterial color="#929a9d" metalness={0.9} roughness={0.36} />
        </mesh>
        <mesh position={[0, 7.25, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.52, 0.035, 8, 32]} />
          <meshStandardMaterial color={CERAMIC} metalness={0.6} roughness={0.32} />
        </mesh>
      </group>

      <group name="neural-core">
        <pointLight color="#eefcff" intensity={14} distance={18} decay={2} />
        <mesh>
          <sphereGeometry args={[1.12, settings.geometrySegments, Math.max(18, settings.geometrySegments / 2)]} />
          <meshPhysicalMaterial
            color="#e7f7fb"
            emissive="#bfefff"
            emissiveIntensity={1.4}
            roughness={0.08}
            metalness={0.05}
            transmission={settings.materialTransmission}
            thickness={0.8}
            clearcoat={1}
            clearcoatRoughness={0.08}
          />
        </mesh>
        <mesh scale={1.16}>
          <icosahedronGeometry args={[1.12, 2]} />
          <meshBasicMaterial color="#7ae0ff" wireframe transparent opacity={0.08} />
        </mesh>
      </group>

      <CrownRing radius={2.25} direction={1} settings={settings} tilt={Math.PI / 2.8} />
      <CrownRing radius={3.18} direction={-1} settings={settings} tilt={-Math.PI / 3.4} />
      <SectorArcs settings={settings} />
      <RadiatorCrown />
      {Array.from({ length: 4 }, (_, index) => <DockAssembly key={index} index={index} />)}

      {Array.from({ length: 18 }, (_, index) => {
        const angle = (index / 18) * Math.PI * 2;
        return (
          <mesh key={index} position={[Math.cos(angle) * 4.98, 0.16, Math.sin(angle) * 4.98]}>
            <boxGeometry args={[0.12, 0.08, 0.04]} />
            <meshBasicMaterial color={index % 6 === 0 ? '#ffffff' : GLASS} toneMapped={false} />
          </mesh>
        );
      })}

      <mesh position={[0, -5.95, 0]}>
        <coneGeometry args={[0.18, 1.6, 8]} />
        <meshStandardMaterial color="#596066" metalness={0.86} roughness={0.5} />
      </mesh>
    </group>
  );
}
