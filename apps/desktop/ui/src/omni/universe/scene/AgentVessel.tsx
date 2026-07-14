import { useMemo } from 'react';
import * as THREE from 'three';
import type { Vessel } from '../types.ts';
import { vesselClassOf } from '../vessel.ts';
import type { FidelitySettings } from '../fidelity.ts';

const CLASS_PROFILE = {
  scout: { length: 4.8, beam: 1.5, pods: 1, wing: 2.8 },
  surveyor: { length: 5.6, beam: 1.8, pods: 2, wing: 3.4 },
  forge: { length: 6.2, beam: 2.2, pods: 3, wing: 2.6 },
  director: { length: 5.9, beam: 2, pods: 2, wing: 4.1 },
  carrier: { length: 7.4, beam: 2.8, pods: 4, wing: 4.6 },
  diplomat: { length: 5.8, beam: 2.2, pods: 2, wing: 3.8 },
  sentinel: { length: 6.3, beam: 2.4, pods: 2, wing: 3.1 },
  courier: { length: 5.1, beam: 1.65, pods: 1, wing: 2.5 },
  flagship: { length: 8.2, beam: 3, pods: 5, wing: 5.2 },
} as const;

function seeded(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 0xffffffff;
  };
}

interface HullMaps {
  map: THREE.CanvasTexture;
  roughnessMap: THREE.CanvasTexture;
  bumpMap: THREE.CanvasTexture;
}

/**
 * Procedural aerospace plating, generated once on canvases — panel rows with
 * per-panel tonal jitter, dark seams, sparse service ports, and matching
 * roughness variation with brushed-metal streaks. With the starfield PMREM
 * environment reflecting off it, this is what sells the hull as real metal;
 * no image assets are shipped for the ship itself.
 */
function makeHullMaps(seedValue: number): HullMaps | null {
  if (typeof document === 'undefined') return null;
  const size = 512;
  const random = seeded(seedValue);

  const albedo = document.createElement('canvas');
  albedo.width = size;
  albedo.height = size;
  const rough = document.createElement('canvas');
  rough.width = size;
  rough.height = size;
  const bump = document.createElement('canvas');
  bump.width = size;
  bump.height = size;
  const a = albedo.getContext('2d');
  const r = rough.getContext('2d');
  const b = bump.getContext('2d');
  if (!a || !r || !b) return null;

  a.fillStyle = '#c9d1d6';
  a.fillRect(0, 0, size, size);
  r.fillStyle = '#5a5a5a'; // base roughness ≈ 0.35
  r.fillRect(0, 0, size, size);
  b.fillStyle = '#808080';
  b.fillRect(0, 0, size, size);

  // Panel grid with irregular column splits per row.
  const rows = 9;
  for (let row = 0; row < rows; row += 1) {
    const y0 = Math.round((row / rows) * size);
    const y1 = Math.round(((row + 1) / rows) * size);
    let x = 0;
    while (x < size) {
      const w = Math.round(size * (0.08 + random() * 0.16));
      const tone = 196 + Math.round((random() - 0.5) * 26);
      a.fillStyle = `rgb(${tone},${tone + 3},${tone + 6})`;
      a.fillRect(x, y0, w, y1 - y0);
      const roughTone = 82 + Math.round((random() - 0.5) * 52);
      r.fillStyle = `rgb(${roughTone},${roughTone},${roughTone})`;
      r.fillRect(x, y0, w, y1 - y0);
      // Seams: darker albedo line + bump groove on panel borders.
      a.fillStyle = 'rgba(38,44,48,0.85)';
      a.fillRect(x, y0, 2, y1 - y0);
      b.fillStyle = '#565656';
      b.fillRect(x, y0, 2, y1 - y0);
      // Sparse service ports / vents.
      if (random() > 0.82) {
        const px = x + 6 + random() * Math.max(w - 18, 6);
        const py = y0 + 5 + random() * Math.max(y1 - y0 - 12, 4);
        a.fillStyle = 'rgba(30,36,40,0.9)';
        a.fillRect(px, py, 5 + random() * 9, 3 + random() * 4);
      }
      x += w;
    }
    a.fillStyle = 'rgba(38,44,48,0.85)';
    a.fillRect(0, y0, size, 2);
    b.fillStyle = '#565656';
    b.fillRect(0, y0, size, 2);
  }

  // Brushed streaks: long, faint horizontal roughness scratches.
  for (let i = 0; i < 320; i += 1) {
    const y = random() * size;
    const len = 24 + random() * 150;
    const shade = random() > 0.5 ? 255 : 40;
    r.fillStyle = `rgba(${shade},${shade},${shade},0.05)`;
    r.fillRect(random() * size, y, len, 1);
  }

  const map = new THREE.CanvasTexture(albedo);
  map.colorSpace = THREE.SRGBColorSpace;
  const roughnessMap = new THREE.CanvasTexture(rough);
  const bumpMap = new THREE.CanvasTexture(bump);
  for (const texture of [map, roughnessMap, bumpMap]) {
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.anisotropy = 4;
  }
  return { map, roughnessMap, bumpMap };
}

export function AgentVessel({ vessel, settings }: { vessel: Vessel; settings: FidelitySettings }) {
  const vesselClass = vesselClassOf(vessel);
  const profile = CLASS_PROFILE[vesselClass];
  const paint = vessel.cosmetics?.paint ?? '#cfd6da';
  const hasDegradation = (vessel.degraded_fields?.length ?? 0) > 0;
  const hull = useMemo(() => makeHullMaps(0x715e55), []);
  return (
    <group name={`vessel:${vessel.id}`} userData={{ vesselId: vessel.id, vesselClass }} rotation={[0.04, -0.4, -0.03]}>
      {/* Primary hull — plated aerospace metal with starfield reflections. */}
      <mesh rotation={[Math.PI / 2, 0, 0]} scale={[1, 1, profile.length / profile.beam]}>
        <capsuleGeometry args={[profile.beam * 0.58, profile.length * 0.38, 10, Math.max(16, settings.geometrySegments / 2)]} />
        <meshPhysicalMaterial
          color={paint}
          map={hull?.map ?? null}
          roughnessMap={hull?.roughnessMap ?? null}
          bumpMap={hull?.bumpMap ?? null}
          bumpScale={0.9}
          metalness={0.94}
          roughness={hull ? 1 : 0.34}
          clearcoat={0.32}
          clearcoatRoughness={0.22}
          envMapIntensity={1.5}
        />
      </mesh>
      {/* Nose cone — bare polished alloy. */}
      <mesh position={[0, 0.15, -profile.length * 0.42]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[profile.beam * 0.56, profile.length * 0.34, Math.max(12, settings.geometrySegments / 3)]} />
        <meshPhysicalMaterial
          color="#aeb7bc"
          metalness={1}
          roughness={0.2}
          clearcoat={0.5}
          clearcoatRoughness={0.14}
          envMapIntensity={1.7}
        />
      </mesh>
      {/* Canopy — real glass: transmission + IOR + clearcoat. */}
      <mesh position={[0, 0.38, profile.length * 0.34]} rotation={[Math.PI / 2, 0, 0]}>
        <sphereGeometry args={[profile.beam * 0.42, 32, 14, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshPhysicalMaterial
          color="#dff2f6"
          transmission={Math.max(settings.materialTransmission * 0.75, 0.2)}
          ior={1.45}
          thickness={0.12}
          roughness={0.05}
          metalness={0}
          clearcoat={1}
          clearcoatRoughness={0.06}
          envMapIntensity={1.2}
        />
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side} position={[side * profile.wing * 0.62, -0.12, 0.05]}>
          {/* Wing spar — dark structural alloy. */}
          <mesh rotation={[0.08, 0, side * -0.04]}>
            <boxGeometry args={[profile.wing, 0.1, profile.length * 0.55]} />
            <meshPhysicalMaterial color="#4c565c" metalness={0.96} roughness={0.34} envMapIntensity={1.35} />
          </mesh>
          {/* Radiator panel — matte charcoal, barely reflective. */}
          <mesh position={[side * profile.wing * 0.36, 0, -0.2]}>
            <boxGeometry args={[profile.wing * 0.58, 0.035, profile.length * 0.46]} />
            <meshStandardMaterial color="#1f272c" metalness={0.4} roughness={0.72} envMapIntensity={0.5} />
          </mesh>
          {/* Equipment pods — gold Kapton MLI foil, like real spacecraft. */}
          {Array.from({ length: profile.pods }, (_, index) => (
            <mesh key={index} position={[side * profile.wing * 0.28, -0.2, -profile.length * 0.25 + index * 0.62]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.18, 0.22, 0.82, 12]} />
              <meshPhysicalMaterial
                color="#d9a441"
                metalness={1}
                roughness={0.3}
                clearcoat={0.25}
                clearcoatRoughness={0.3}
                envMapIntensity={1.8}
              />
            </mesh>
          ))}
        </group>
      ))}
      <group position={[0, -0.1, profile.length * 0.56]}>
        {/* Engine shroud ring — polished. */}
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[profile.beam * 0.42, 0.08, 10, 32]} />
          <meshPhysicalMaterial color="#c4cccd" metalness={1} roughness={0.22} envMapIntensity={1.6} />
        </mesh>
        {/* Nozzle throat — heat-darkened. */}
        <mesh position={[0, 0, 0.08]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[profile.beam * 0.35, profile.beam * 0.35, 0.18, 24]} />
          <meshStandardMaterial color="#14181b" metalness={0.85} roughness={0.5} envMapIntensity={0.7} />
        </mesh>
        {/* Ion drive glow — emissive disc + real light spilling onto the hull. */}
        <mesh position={[0, 0, 0.19]} rotation={[Math.PI / 2, 0, 0]}>
          <circleGeometry args={[profile.beam * 0.3, 24]} />
          <meshBasicMaterial color="#8fd8ff" toneMapped={false} transparent opacity={0.85} />
        </mesh>
        <pointLight color="#7fc6ee" intensity={3.2} distance={9} decay={2} position={[0, 0, 0.7]} />
      </group>
      {Array.from({ length: 8 }, (_, index) => {
        const side = index % 2 ? 1 : -1;
        const z = -profile.length * 0.34 + Math.floor(index / 2) * (profile.length * 0.19);
        return (
          <mesh key={index} position={[side * profile.beam * 0.61, 0.23, z]}>
            <sphereGeometry args={[0.035, 8, 6]} />
            <meshBasicMaterial color={index < 2 ? '#ffffff' : '#89aab3'} toneMapped={false} />
          </mesh>
        );
      })}
      {hasDegradation && (
        <mesh position={[0, -0.45, -profile.length * 0.08]}>
          <boxGeometry args={[profile.beam * 0.9, 0.04, 0.32]} />
          <meshBasicMaterial color="#b09b67" transparent opacity={0.72} />
        </mesh>
      )}
    </group>
  );
}
