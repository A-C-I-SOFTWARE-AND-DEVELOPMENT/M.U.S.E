import { useMemo, useRef } from 'react';
import { Line } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { FidelitySettings } from '../fidelity.ts';

interface Props {
  settings: FidelitySettings;
  density?: number;
}

function seeded(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 0xffffffff;
  };
}

function pointCloud(count: number, inner: number, outer: number, seed: number): Float32Array {
  const random = seeded(seed);
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    const radius = inner + random() * (outer - inner);
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    positions[index * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[index * 3 + 1] = radius * Math.cos(phi);
    positions[index * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
  }
  return positions;
}

const NEBULA_VERTEX = `
  varying vec3 vPosition;
  void main() {
    vPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const NEBULA_FRAGMENT = `
  varying vec3 vPosition;
  uniform vec3 colorA;
  uniform vec3 colorB;
  uniform float density;
  float hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(.1, .2, .3));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }
  void main() {
    float radial = 1.0 - smoothstep(0.08, 1.0, length(vPosition));
    float grain = hash(floor(vPosition * 12.0)) * 0.28;
    float filament = sin(vPosition.x * 8.0 + vPosition.y * 5.0) * 0.5 + 0.5;
    float alpha = radial * (0.055 + grain * 0.09 + filament * 0.035) * density;
    vec3 color = mix(colorA, colorB, clamp(vPosition.y * 0.45 + 0.5, 0.0, 1.0));
    gl_FragColor = vec4(color, alpha);
  }
`;

function NebulaVolume({ index, density }: { index: number; density: number }) {
  const uniforms = useMemo(
    () => ({
      colorA: { value: new THREE.Color(index % 2 ? '#786a9b' : '#476979') },
      colorB: { value: new THREE.Color(index % 2 ? '#253846' : '#42395c') },
      density: { value: density },
    }),
    [density, index],
  );
  return (
    <mesh
      position={[index * 18 - 12, index % 2 ? 5 : -7, -42 - index * 14]}
      rotation={[index * 0.31, index * 0.67, index * 0.17]}
      scale={[34 + index * 8, 17 + index * 3, 12 + index * 4]}
    >
      <sphereGeometry args={[1, 32, 18]} />
      <shaderMaterial
        vertexShader={NEBULA_VERTEX}
        fragmentShader={NEBULA_FRAGMENT}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        side={THREE.BackSide}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}

function CometField({ count, motion }: { count: number; motion: boolean }) {
  const ref = useRef<THREE.Group>(null);
  const comets = useMemo(() => {
    const random = seeded(0x51a7c0de);
    return Array.from({ length: count }, (_, index) => {
      const origin = new THREE.Vector3(
        -18 + random() * 38,
        -8 + random() * 18,
        -16 - random() * 46,
      );
      const length = 2.5 + random() * 6;
      return {
        key: `comet-${index}`,
        points: [origin, origin.clone().add(new THREE.Vector3(-length, length * 0.16, -length * 0.28))],
        opacity: 0.2 + random() * 0.38,
      };
    });
  }, [count]);
  useFrame((_, delta) => {
    if (motion && ref.current) ref.current.rotation.y += delta * 0.008;
  });
  return (
    <group ref={ref}>
      {comets.map((comet) => (
        <Line
          key={comet.key}
          points={comet.points}
          color="#d8eff8"
          transparent
          opacity={comet.opacity}
          lineWidth={0.45}
        />
      ))}
    </group>
  );
}

export function CelestialEnvironment({ settings, density = 1 }: Props) {
  const stars = useMemo(
    () => pointCloud(Math.round(settings.starCount * density), 180, 1400, 0xa71a5),
    [density, settings.starCount],
  );
  const dust = useMemo(
    () => pointCloud(Math.round(settings.dustCount * density), 8, 64, 0xd057),
    [density, settings.dustCount],
  );

  return (
    <group name="celestial-environment">
      {stars.length > 0 && (
        <points frustumCulled={false}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[stars, 3]} />
          </bufferGeometry>
          <pointsMaterial
            color="#dbe8ed"
            size={0.72}
            sizeAttenuation
            transparent
            opacity={0.72}
            depthWrite={false}
          />
        </points>
      )}
      {Array.from({ length: settings.volumetricLayers }, (_, index) => (
        <NebulaVolume key={index} index={index} density={Math.max(0.2, density)} />
      ))}
      {dust.length > 0 && (
        <points>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[dust, 3]} />
          </bufferGeometry>
          <pointsMaterial
            color="#9eb0b8"
            size={0.045}
            sizeAttenuation
            transparent
            opacity={0.34}
            depthWrite={false}
          />
        </points>
      )}
      <CometField count={settings.comets} motion={settings.motion} />
    </group>
  );
}
