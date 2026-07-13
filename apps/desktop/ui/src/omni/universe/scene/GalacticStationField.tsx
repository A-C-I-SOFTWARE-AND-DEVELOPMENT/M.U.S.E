import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { FidelitySettings } from '../fidelity.ts';
import { AtlasCrown } from './AtlasCrown.tsx';

/**
 * Persistent deep-space station field — galactic plane, host world, and a
 * distant Atlas Crown silhouette that sits behind every interior room so the
 * desktop never falls back to a flat void.
 *
 * Realism pass: temperature-graded starfield (vertex colours), a fully
 * procedural planet shader (banded surface, day/night terminator, night-side
 * city lights, limb darkening) wrapped in a fresnel atmosphere shell, layered
 * additive nebulae, and emissive habitat detail. Everything is generated in
 * code — no shipped textures — and gated by the fidelity budget.
 */
function seeded(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 0xffffffff;
  };
}

/** Blackbody-ish star palette, weighted toward white/blue-white like a real field. */
const STAR_TEMPS: ReadonlyArray<readonly [number, number, number, number]> = [
  [0.64, 0.76, 1.0, 0.22], // O/B blue-white
  [0.82, 0.88, 1.0, 0.2], // A
  [1.0, 1.0, 1.0, 0.28], // F/G white
  [1.0, 0.9, 0.72, 0.18], // K amber
  [1.0, 0.68, 0.5, 0.12], // M orange-red
];

function pickTemp(t: number): readonly [number, number, number] {
  let acc = 0;
  for (const [r, g, b, w] of STAR_TEMPS) {
    acc += w;
    if (t <= acc) return [r, g, b];
  }
  return [1, 1, 1];
}

function GalacticPlane({ density }: { density: number }) {
  const { positions, colors } = useMemo(() => {
    const count = Math.round(1400 * density);
    const random = seeded(0xc0ffee);
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const radius = 40 + random() * 520;
      const theta = random() * Math.PI * 2;
      const thickness = (random() - 0.5) * (8 + radius * 0.018);
      pos[i * 3] = Math.cos(theta) * radius;
      pos[i * 3 + 1] = thickness;
      pos[i * 3 + 2] = Math.sin(theta) * radius * 0.42;
      const [r, g, b] = pickTemp(random());
      const lum = 0.55 + random() * 0.45;
      col[i * 3] = r * lum;
      col[i * 3 + 1] = g * lum;
      col[i * 3 + 2] = b * lum;
    }
    return { positions: pos, colors: col };
  }, [density]);

  return (
    <points rotation={[0.42, 0.18, -0.12]} position={[0, -6, -80]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        vertexColors
        size={0.55}
        sizeAttenuation
        transparent
        opacity={0.55}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/** Soft radial nebula texture, generated once on a canvas — no shipped assets. */
function useNebulaTexture(r: number, g: number, b: number): THREE.CanvasTexture | null {
  return useMemo(() => {
    if (typeof document === 'undefined') return null;
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    grad.addColorStop(0, `rgba(${r},${g},${b},0.85)`);
    grad.addColorStop(0.35, `rgba(${r},${g},${b},0.32)`);
    grad.addColorStop(0.7, `rgba(${r},${g},${b},0.08)`);
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }, [r, g, b]);
}

function NebulaField({ layers }: { layers: number }) {
  const teal = useNebulaTexture(96, 196, 224);
  const violet = useNebulaTexture(150, 118, 244);
  const ember = useNebulaTexture(226, 150, 110);
  const sprites = useMemo(() => {
    return [
      { key: 'neb-teal', map: teal, position: [-120, 18, -240] as const, scale: 260, opacity: 0.14 },
      { key: 'neb-violet', map: violet, position: [150, -30, -300] as const, scale: 320, opacity: 0.12 },
      { key: 'neb-ember', map: ember, position: [30, 60, -360] as const, scale: 220, opacity: 0.08 },
    ].slice(0, Math.max(1, layers));
  }, [teal, violet, ember, layers]);

  return (
    <group name="nebula-field">
      {sprites.map((entry) =>
        entry.map ? (
          <sprite key={entry.key} position={[...entry.position]} scale={[entry.scale, entry.scale, 1]}>
            <spriteMaterial
              map={entry.map}
              transparent
              opacity={entry.opacity}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </sprite>
        ) : null,
      )}
    </group>
  );
}

const PLANET_VERTEX = /* glsl */ `
varying vec3 vNormal;
varying vec3 vViewDir;
varying vec3 vLocal;
void main() {
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vNormal = normalize(mat3(modelMatrix) * normal);
  vViewDir = normalize(cameraPosition - worldPos.xyz);
  vLocal = position;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

const PLANET_FRAGMENT = /* glsl */ `
uniform float uTime;
uniform vec3 uLightDir;
varying vec3 vNormal;
varying vec3 vViewDir;
varying vec3 vLocal;

float hash(vec3 p) {
  p = fract(p * 0.3183099 + 0.1);
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash(i), hash(i + vec3(1, 0, 0)), f.x), mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
    mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x), mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y),
    f.z);
}

float fbm(vec3 p) {
  float value = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 4; i++) {
    value += amp * noise(p);
    p *= 2.15;
    amp *= 0.5;
  }
  return value;
}

void main() {
  vec3 n = normalize(vNormal);
  float day = clamp(dot(n, normalize(uLightDir)), -1.0, 1.0);

  // Banded, slowly drifting surface — ice-teal ocean world with mineral bands.
  float bands = fbm(vLocal * 0.42 + vec3(0.0, uTime * 0.008, 0.0)) * 0.6
              + fbm(vLocal * vec3(0.22, 1.35, 0.22)) * 0.4;
  vec3 ocean = vec3(0.035, 0.10, 0.15);
  vec3 shelf = vec3(0.10, 0.24, 0.28);
  vec3 mineral = vec3(0.36, 0.33, 0.26);
  vec3 surface = mix(ocean, shelf, smoothstep(0.35, 0.62, bands));
  surface = mix(surface, mineral, smoothstep(0.68, 0.86, bands) * 0.55);

  // Sparse cloud sheets catch the light.
  float clouds = smoothstep(0.58, 0.8, fbm(vLocal * 0.9 + vec3(uTime * 0.012, 0.0, 0.0)));
  surface = mix(surface, vec3(0.82, 0.88, 0.9), clouds * 0.5);

  float daylight = smoothstep(-0.12, 0.35, day);
  vec3 lit = surface * (0.12 + 1.25 * daylight);

  // Night-side settlements: sparse warm speckle, masked to land bands.
  float cityMask = step(0.66, hash(floor(vLocal * 14.0))) * smoothstep(0.5, 0.72, bands) * (1.0 - clouds);
  vec3 cities = vec3(1.0, 0.72, 0.42) * cityMask * smoothstep(0.05, -0.3, day) * 0.9;

  // Limb darkening + a whisper of atmospheric scatter at the terminator.
  float view = clamp(dot(n, normalize(vViewDir)), 0.0, 1.0);
  float limb = pow(view, 0.55);
  vec3 terminator = vec3(0.9, 0.5, 0.3) * smoothstep(0.18, 0.0, abs(day)) * 0.18;

  gl_FragColor = vec4((lit + cities + terminator) * limb, 1.0);
}
`;

const ATMOSPHERE_VERTEX = /* glsl */ `
varying vec3 vNormal;
varying vec3 vViewDir;
void main() {
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vNormal = normalize(mat3(modelMatrix) * normal);
  vViewDir = normalize(cameraPosition - worldPos.xyz);
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

const ATMOSPHERE_FRAGMENT = /* glsl */ `
uniform vec3 uLightDir;
varying vec3 vNormal;
varying vec3 vViewDir;
void main() {
  vec3 n = normalize(vNormal);
  float rim = pow(1.0 - abs(dot(n, normalize(vViewDir))), 2.6);
  float lit = clamp(dot(n, normalize(uLightDir)) * 0.5 + 0.5, 0.0, 1.0);
  vec3 sky = mix(vec3(0.16, 0.4, 0.62), vec3(0.5, 0.78, 0.95), lit);
  gl_FragColor = vec4(sky, rim * (0.22 + lit * 0.5));
}
`;

const PLANET_LIGHT_DIR = new THREE.Vector3(0.62, 0.28, 0.73).normalize();

function HostWorld({ settings }: { settings: FidelitySettings }) {
  const ref = useRef<THREE.Mesh>(null);
  const surfaceUniforms = useMemo(
    () => ({ uTime: { value: 0 }, uLightDir: { value: PLANET_LIGHT_DIR.clone() } }),
    [],
  );
  const atmosphereUniforms = useMemo(() => ({ uLightDir: { value: PLANET_LIGHT_DIR.clone() } }), []);
  const segments = Math.max(48, Math.min(settings.geometrySegments, 128));

  useFrame((state, delta) => {
    if (ref.current && settings.motion) ref.current.rotation.y += delta * 0.018;
    surfaceUniforms.uTime.value = settings.motion ? state.clock.elapsedTime : 0;
  });

  return (
    <group position={[-28, -10, -72]}>
      <mesh ref={ref}>
        <sphereGeometry args={[9.4, segments, Math.round(segments * 0.7)]} />
        <shaderMaterial vertexShader={PLANET_VERTEX} fragmentShader={PLANET_FRAGMENT} uniforms={surfaceUniforms} />
      </mesh>
      <mesh scale={1.045}>
        <sphereGeometry args={[9.4, Math.max(32, Math.round(segments * 0.5)), 24]} />
        <shaderMaterial
          vertexShader={ATMOSPHERE_VERTEX}
          fragmentShader={ATMOSPHERE_FRAGMENT}
          uniforms={atmosphereUniforms}
          transparent
          depthWrite={false}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, 0.2, 0.4]}>
        <torusGeometry args={[12.2, 0.08, 8, 96]} />
        <meshStandardMaterial
          color="#8eb8c8"
          emissive="#5d90a6"
          emissiveIntensity={0.25}
          metalness={0.6}
          roughness={0.4}
          transparent
          opacity={0.5}
        />
      </mesh>
      <mesh rotation={[Math.PI / 2.1, -0.1, 0.1]}>
        <torusGeometry args={[13.6, 0.035, 6, 96]} />
        <meshBasicMaterial color="#b388ff" transparent opacity={0.12} />
      </mesh>
    </group>
  );
}

function DistantHabitats({ count, motion }: { count: number; motion: boolean }) {
  const spinRef = useRef<THREE.Group>(null);
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
        spin: 0.05 + random() * 0.12,
      };
    });
  }, [count]);

  useFrame((_, delta) => {
    if (!spinRef.current || !motion) return;
    spinRef.current.children.forEach((child, index) => {
      child.rotation.y += delta * (habitats[index]?.spin ?? 0.08);
    });
  });

  return (
    <group ref={spinRef}>
      {habitats.map((habitat) => (
        <group key={habitat.key} position={habitat.position} rotation={[0, habitat.yaw, 0]} scale={habitat.scale}>
          <mesh>
            <cylinderGeometry args={[0.18, 0.22, 2.4, 10]} />
            <meshStandardMaterial color="#6a737a" metalness={0.86} roughness={0.42} />
          </mesh>
          {/* Habitation ring with a physical clearcoat so rim light reads as metal. */}
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.85, 0.05, 8, 36]} />
            <meshPhysicalMaterial
              color="#8a9499"
              metalness={0.9}
              roughness={0.32}
              clearcoat={0.6}
              clearcoatRoughness={0.25}
            />
          </mesh>
          {/* Lit window band — emissive, so the glow survives tone mapping. */}
          <mesh position={[0, 0.35, 0]}>
            <cylinderGeometry args={[0.185, 0.185, 0.14, 12, 1, true]} />
            <meshStandardMaterial
              color="#0b0f12"
              emissive="#ffc98a"
              emissiveIntensity={1.6}
              metalness={0.1}
              roughness={0.8}
              side={THREE.DoubleSide}
            />
          </mesh>
          <mesh position={[0, -1.28, 0]}>
            <sphereGeometry args={[0.06, 8, 8]} />
            <meshStandardMaterial color="#10161a" emissive="#ff5470" emissiveIntensity={2.2} />
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
      <NebulaField layers={settings.volumetricLayers} />
      <GalacticPlane density={density} />
      <HostWorld settings={settings} />
      <DistantHabitats count={Math.max(3, Math.round(settings.comets * 0.55))} motion={settings.motion} />
      {showCrown && (
        <group position={crownPosition} scale={crownScale} rotation={[0.12, -0.55, 0.05]}>
          <AtlasCrown settings={settings} />
        </group>
      )}
    </group>
  );
}
