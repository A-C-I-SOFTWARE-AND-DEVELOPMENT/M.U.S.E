import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { FidelitySettings } from '../fidelity.ts';
import { AtlasCrown } from './AtlasCrown.tsx';

/**
 * Persistent deep-space station field — galactic plane, host world, and a
 * distant Atlas Crown silhouette that sits behind every interior room so the
 * desktop never falls back to a flat void.
 */
function seeded(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 0xffffffff;
  };
}

function GalacticPlane({ density }: { density: number }) {
  const positions = useMemo(() => {
    const count = Math.round(1400 * density);
    const random = seeded(0xc0ffee);
    const data = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const radius = 40 + random() * 520;
      const theta = random() * Math.PI * 2;
      const thickness = (random() - 0.5) * (8 + radius * 0.018);
      data[i * 3] = Math.cos(theta) * radius;
      data[i * 3 + 1] = thickness;
      data[i * 3 + 2] = Math.sin(theta) * radius * 0.42;
    }
    return data;
  }, [density]);

  return (
    <points rotation={[0.42, 0.18, -0.12]} position={[0, -6, -80]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#c9d7ea"
        size={0.55}
        sizeAttenuation
        transparent
        opacity={0.42}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function HostWorld() {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.018;
  });
  return (
    <group position={[-28, -10, -72]}>
      <mesh ref={ref}>
        <sphereGeometry args={[9.4, 48, 32]} />
        <meshStandardMaterial
          color="#1a2a36"
          emissive="#0d3a4a"
          emissiveIntensity={0.35}
          metalness={0.2}
          roughness={0.78}
        />
      </mesh>
      <mesh scale={1.04}>
        <sphereGeometry args={[9.4, 32, 24]} />
        <meshBasicMaterial color="#6ea8c4" transparent opacity={0.08} depthWrite={false} />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, 0.2, 0.4]}>
        <torusGeometry args={[12.2, 0.08, 8, 96]} />
        <meshBasicMaterial color="#8eb8c8" transparent opacity={0.22} />
      </mesh>
      <mesh rotation={[Math.PI / 2.1, -0.1, 0.1]}>
        <torusGeometry args={[13.6, 0.035, 6, 96]} />
        <meshBasicMaterial color="#b388ff" transparent opacity={0.12} />
      </mesh>
    </group>
  );
}

function DistantHabitats({ count }: { count: number }) {
  const habitats = useMemo(() => {
    const random = seeded(0x51a710);
    return Array.from({ length: count }, (_, index) => {
      const angle = (index / Math.max(count, 1)) * Math.PI * 2 + random() * 0.4;
      const radius = 22 + random() * 34;
      return {
        key: `habitat-${index}`,
        position: [
          Math.cos(angle) * radius,
          -2 + random() * 8,
          -38 - Math.sin(angle) * radius * 0.55,
        ] as [number, number, number],
        scale: 0.35 + random() * 0.55,
        yaw: angle,
      };
    });
  }, [count]);

  return (
    <group>
      {habitats.map((habitat) => (
        <group key={habitat.key} position={habitat.position} rotation={[0, habitat.yaw, 0]} scale={habitat.scale}>
          <mesh>
            <cylinderGeometry args={[0.18, 0.22, 2.4, 10]} />
            <meshStandardMaterial color="#6a737a" metalness={0.86} roughness={0.42} />
          </mesh>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.85, 0.05, 8, 36]} />
            <meshStandardMaterial color="#8a9499" metalness={0.9} roughness={0.36} />
          </mesh>
          <pointLight color="#9ad8ee" intensity={1.4} distance={6} decay={2} />
        </group>
      ))}
    </group>
  );
}

export function GalacticStationField({
  settings,
  density = 1,
  showCrown = true,
  crownScale = 0.42,
  crownPosition = [8, -1.2, -18] as [number, number, number],
}: {
  settings: FidelitySettings;
  density?: number;
  showCrown?: boolean;
  crownScale?: number;
  crownPosition?: [number, number, number];
}) {
  return (
    <group name="galactic-station-field">
      <GalacticPlane density={density} />
      <HostWorld />
      <DistantHabitats count={Math.max(3, Math.round(settings.comets * 0.55))} />
      {showCrown && (
        <group position={crownPosition} scale={crownScale} rotation={[0.12, -0.55, 0.05]}>
          <AtlasCrown settings={settings} />
        </group>
      )}
    </group>
  );
}
