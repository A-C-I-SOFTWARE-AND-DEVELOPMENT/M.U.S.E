import { useEffect, useMemo, useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { FidelitySettings } from '../fidelity.ts';
import { SPACE_PLATES } from '../spaceAssets.ts';
import { AtlasCrown } from './AtlasCrown.tsx';

/**
 * Persistent deep-space station field — galactic plane, host world, and a
 * distant Atlas Crown silhouette that sits behind every interior room so the
 * desktop never falls back to a flat void.
 *
 * Realism pass: temperature-graded starfield (vertex colours), a host world
 * relit from real NASA plates (Blue Marble day, Black Marble night lights,
 * MODIS cloud fraction — see public/space/ATTRIBUTION.md) with day/night
 * terminator, ocean sun-glint and limb darkening, wrapped in a fresnel
 * atmosphere shell, plus layered additive nebulae and emissive habitat
 * detail. Procedural elements remain generated in code and everything is
 * gated by the fidelity budget.
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
varying vec2 vUv;
void main() {
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vNormal = normalize(mat3(modelMatrix) * normal);
  vViewDir = normalize(cameraPosition - worldPos.xyz);
  vUv = uv;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

// Real-photography host world: NASA Blue Marble day plate, Black Marble
// night-side city lights, and the MODIS cloud-fraction plate, relit with the
// same terminator/limb model the procedural shader used. Textures are sRGB;
// lighting runs in linear and re-encodes at the end.
const PLANET_FRAGMENT = /* glsl */ `
uniform float uTime;
uniform vec3 uLightDir;
uniform sampler2D uDayMap;
uniform sampler2D uNightMap;
uniform sampler2D uCloudMap;
varying vec3 vNormal;
varying vec3 vViewDir;
varying vec2 vUv;

vec3 srgbToLinear(vec3 c) { return pow(c, vec3(2.2)); }

void main() {
  vec3 n = normalize(vNormal);
  vec3 light = normalize(uLightDir);
  vec3 view = normalize(vViewDir);
  float day = clamp(dot(n, light), -1.0, 1.0);

  vec3 surface = srgbToLinear(texture2D(uDayMap, vUv).rgb);
  vec3 nightGlow = srgbToLinear(texture2D(uNightMap, vUv).rgb);
  float cloud = texture2D(uCloudMap, vUv + vec2(uTime * 0.0018, 0.0)).r;

  float daylight = smoothstep(-0.08, 0.32, day);
  vec3 lit = surface * (0.05 + 1.85 * daylight);

  // Ocean sun glint: specular lobe masked to the blue-dominant water pixels.
  float waterMask = smoothstep(0.02, 0.14, surface.b - surface.r);
  float glint = pow(clamp(dot(reflect(-light, n), view), 0.0, 1.0), 42.0);
  lit += vec3(1.0, 0.96, 0.88) * glint * waterMask * daylight * 0.55;

  // Real cloud plate, lit by the same sun and drifting slowly with time.
  lit = mix(lit, vec3(1.04, 1.05, 1.08) * (0.06 + 1.9 * daylight), cloud * 0.82);

  // Black Marble city lights emerge past the terminator, dimmed under cloud.
  vec3 cities = nightGlow * vec3(1.35, 1.05, 0.72) * smoothstep(0.06, -0.26, day) * (1.0 - cloud * 0.85) * 2.4;

  // Limb darkening + warm scatter hugging the terminator.
  float rim = clamp(dot(n, view), 0.0, 1.0);
  float limb = pow(rim, 0.5);
  vec3 terminator = vec3(0.95, 0.55, 0.32) * smoothstep(0.16, 0.0, abs(day)) * 0.22;

  vec3 color = (lit + cities + terminator) * limb;
  gl_FragColor = vec4(pow(max(color, vec3(0.0)), vec3(1.0 / 2.2)), 1.0);
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
  float rim = pow(1.0 - abs(dot(n, normalize(vViewDir))), 2.4);
  float lit = clamp(dot(n, normalize(uLightDir)) * 0.5 + 0.5, 0.0, 1.0);
  vec3 sky = mix(vec3(0.2, 0.46, 0.7), vec3(0.56, 0.82, 0.98), lit);
  gl_FragColor = vec4(sky, rim * (0.3 + lit * 0.58));
}
`;

const PLANET_LIGHT_DIR = new THREE.Vector3(0.62, 0.28, 0.73).normalize();

/** Load the NASA host-world plates once; dispose on unmount. */
function usePlanetPlates(): {
  day: THREE.Texture;
  night: THREE.Texture;
  clouds: THREE.Texture;
} | null {
  const [plates, setPlates] = useState<{
    day: THREE.Texture;
    night: THREE.Texture;
    clouds: THREE.Texture;
  } | null>(null);
  useEffect(() => {
    let cancelled = false;
    const loader = new THREE.TextureLoader();
    const load = (path: string) =>
      new Promise<THREE.Texture>((resolve, reject) => {
        loader.load(path, resolve, undefined, reject);
      });
    void Promise.all([
      load(SPACE_PLATES.earthDay.path),
      load(SPACE_PLATES.earthNight.path),
      load(SPACE_PLATES.earthClouds.path),
    ])
      .then(([day, night, clouds]) => {
        if (cancelled) {
          day.dispose();
          night.dispose();
          clouds.dispose();
          return;
        }
        for (const texture of [day, night, clouds]) {
          texture.wrapS = THREE.RepeatWrapping;
          texture.colorSpace = THREE.NoColorSpace; // decoded manually in-shader
        }
        setPlates({ day, night, clouds });
      })
      .catch(() => {
        // Plates unavailable (offline dev server without public/) — the dim
        // standby sphere below keeps rendering; nothing else breaks.
      });
    return () => {
      cancelled = true;
      setPlates((current) => {
        current?.day.dispose();
        current?.night.dispose();
        current?.clouds.dispose();
        return null;
      });
    };
  }, []);
  return plates;
}

function HostWorld({ settings }: { settings: FidelitySettings }) {
  const ref = useRef<THREE.Mesh>(null);
  const plates = usePlanetPlates();
  const surfaceUniforms = useMemo(() => {
    if (!plates) return null;
    return {
      uTime: { value: 0 },
      uLightDir: { value: PLANET_LIGHT_DIR.clone() },
      uDayMap: { value: plates.day },
      uNightMap: { value: plates.night },
      uCloudMap: { value: plates.clouds },
    };
  }, [plates]);
  const atmosphereUniforms = useMemo(() => ({ uLightDir: { value: PLANET_LIGHT_DIR.clone() } }), []);
  const segments = Math.max(48, Math.min(settings.geometrySegments, 128));

  useFrame((state, delta) => {
    if (ref.current && settings.motion) ref.current.rotation.y += delta * 0.018;
    if (surfaceUniforms) surfaceUniforms.uTime.value = settings.motion ? state.clock.elapsedTime : 0;
  });

  return (
    <group position={[-26, -7, -66]}>
      <mesh ref={ref}>
        <sphereGeometry args={[10.6, segments, Math.round(segments * 0.7)]} />
        {surfaceUniforms ? (
          <shaderMaterial
            key="nasa-world"
            vertexShader={PLANET_VERTEX}
            fragmentShader={PLANET_FRAGMENT}
            uniforms={surfaceUniforms}
          />
        ) : (
          <meshStandardMaterial key="standby-world" color="#16303e" roughness={0.9} metalness={0.05} />
        )}
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
