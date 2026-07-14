import { useEffect, useRef, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { SPACE_PLATES } from '../spaceAssets.ts';

/**
 * Real-photography deep-space layer.
 *
 * Loads the Tycho-2 all-sky star map (see `public/space/ATTRIBUTION.md`) and
 * uses it twice:
 *
 *   1. as a giant inverted backdrop sphere — the deepest parallax layer of
 *      the universe scenes, behind the procedural galactic plane and nebulae;
 *   2. as the PMREM `scene.environment`, so every metallic material in the
 *      scene picks up genuine starfield reflections instead of flat black —
 *      the single biggest step toward photoreal hulls.
 *
 * Fidelity-gated by the caller: when `enabled` is false nothing is fetched
 * and the scene keeps its procedural-only look (accessible/balanced tiers,
 * tests, and the 2D fallback are unaffected).
 */
export function SpaceEnvironment({ enabled }: { enabled: boolean }) {
  const { gl, scene } = useThree();
  const [starmap, setStarmap] = useState<THREE.Texture | null>(null);
  const backdropRef = useRef<THREE.Mesh>(null);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    let envTarget: THREE.WebGLRenderTarget | null = null;
    let texture: THREE.Texture | null = null;
    const loader = new THREE.TextureLoader();
    loader.load(SPACE_PLATES.starmap.path, (loaded) => {
      if (cancelled) {
        loaded.dispose();
        return;
      }
      texture = loaded;
      loaded.colorSpace = THREE.SRGBColorSpace;
      loaded.mapping = THREE.EquirectangularReflectionMapping;
      loaded.anisotropy = Math.min(4, gl.capabilities.getMaxAnisotropy());
      setStarmap(loaded);
      // Metals reflect their environment, and a raw starfield is ~99% black —
      // hulls would render as silhouettes. Composite the lighting environment
      // the way space really works: the star map for detail, an HDR-hot sun
      // disc for blinding key speculars, and a soft cool sphere standing in
      // for planetshine. PMREM captures values > 1, so the sun stays "sun".
      const envScene = new THREE.Scene();
      const skySphere = new THREE.Mesh(
        new THREE.SphereGeometry(50, 32, 16),
        new THREE.MeshBasicMaterial({ map: loaded, side: THREE.BackSide }),
      );
      const sun = new THREE.Mesh(
        new THREE.SphereGeometry(3.6, 16, 16),
        new THREE.MeshBasicMaterial({ color: new THREE.Color(14, 12.2, 9.8) }),
      );
      sun.position.set(26, 22, 30);
      const planetshine = new THREE.Mesh(
        new THREE.SphereGeometry(10, 16, 16),
        new THREE.MeshBasicMaterial({ color: new THREE.Color(0.35, 0.75, 1.15) }),
      );
      planetshine.position.set(-34, -14, -34);
      envScene.add(skySphere, sun, planetshine);
      const pmrem = new THREE.PMREMGenerator(gl);
      envTarget = pmrem.fromScene(envScene, 0.04);
      scene.environment = envTarget.texture;
      scene.environmentIntensity = 1.0;
      pmrem.dispose();
      skySphere.geometry.dispose();
      skySphere.material.dispose();
      sun.geometry.dispose();
      sun.material.dispose();
      planetshine.geometry.dispose();
      planetshine.material.dispose();
    });
    return () => {
      cancelled = true;
      if (scene.environment === envTarget?.texture) scene.environment = null;
      scene.environmentIntensity = 1;
      envTarget?.dispose();
      texture?.dispose();
      setStarmap(null);
    };
  }, [enabled, gl, scene]);

  // A barely-perceptible drift keeps the deep field alive without reading as
  // motion; combined with CameraDrift it produces true layered parallax.
  useFrame((_, delta) => {
    if (backdropRef.current) backdropRef.current.rotation.y += delta * 0.0016;
  });

  if (!enabled || !starmap) return null;
  return (
    <mesh ref={backdropRef} name="space-backdrop" rotation={[0.42, 2.1, -0.12]} renderOrder={-10}>
      <sphereGeometry args={[1600, 64, 32]} />
      <meshBasicMaterial map={starmap} side={THREE.BackSide} fog={false} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}
