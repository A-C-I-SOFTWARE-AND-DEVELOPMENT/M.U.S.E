/**
 * Observatory scene graph — animation-spec.md §1–§3 (binding contract).
 *
 * Raw three.js (no @react-three/fiber). One WebGL context hosting:
 *   §1  spectral wireframe sigil  — TorusKnotGeometry(60, 18, 220, 36),
 *       custom ShaderMaterial, per-vertex band-limited spectral colors
 *       (hue 0.68→0.92, sat 0.5, light 0.5), additive, depthTest off,
 *       breathing displacement + per-frame jitter + hue drift.
 *   §2  dust field — 800 additive THREE.Points with per-point drift
 *       velocity and gentle pointer repulsion.
 *   §3  pointer parallax — normalized pointer lerped (0.05) into camera
 *       x/y (±12 units); wheel nudges camera z (±10 around base).
 *
 * All per-frame state lives here; the React component only owns the rAF
 * loop, DOM listeners, and disposal.
 */
import * as THREE from "three";

import { SIGIL_FRAGMENT_SHADER, SIGIL_VERTEX_SHADER } from "./shaders";

/* ---- Contract constants (animation-spec.md §1–§3) -------------------- */

const SIGIL = {
  radius: 60,
  tube: 18,
  tubularSegments: 220,
  radialSegments: 36,
  x: 40, // right-of-center so the content column stays readable
  opacity: 0.25, // contract band 0.22–0.3
  hueMin: 0.68,
  hueMax: 0.92,
  saturation: 0.5,
  lightness: 0.5,
  rotationPerFrame: 0.0025, // spec-blessed: ~0.15 rad/s at 60 fps
  breathBase: 5,
  breathAmplitude: 4,
  breathFrequency: 0.5, // amplitude = 5 + 4*sin(0.5*t)
  jitter: 0.3, // 0.3 * (0.5 - Math.random()) per frame
  hueDrift: 0.0005, // offsetHSL(0.0005, 0, 0) per frame
} as const;

const DUST = {
  count: 800,
  opacity: 0.35,
  size: 2.2,
  hue: 0.75, // inside the Singularity violet→magenta band
  saturation: 0.5,
  lightness: 0.72,
  boundX: 260,
  boundY: 150,
  zMin: -150,
  zMax: 60,
  maxDrift: 1.5, // units/second per axis, slow ambient drift
  repelRadius: 36,
  repelStrength: 1.2, // units per 60 fps frame at the radius core
} as const;

const CAMERA = {
  fov: 60,
  near: 0.1,
  far: 1000,
  baseZ: 220,
  parallaxXY: 12, // ±12 units
  zoomRange: 10, // wheel nudges z within ±10 of baseZ
  lerp: 0.05,
} as const;

const HALF_FOV_TAN = Math.tan(((CAMERA.fov / 2) * Math.PI) / 180);

export interface ObservatorySceneHandle {
  /** Update camera aspect + renderer size (contract §4). */
  resize(width: number, height: number): void;
  /**
   * Advance and render one frame.
   * @param timeSeconds  elapsed scene time (drives breathing/rotation)
   * @param deltaSeconds frame delta, pre-clamped by the caller
   */
  renderFrame(timeSeconds: number, deltaSeconds: number): void;
  /** Normalized pointer, both axes in [-1, 1] (y up). */
  setPointer(nx: number, ny: number): void;
  /** Accumulate a wheel nudge, clamped to ±CAMERA.zoomRange around baseZ. */
  nudgeZoom(delta: number): void;
  /** Dispose geometry/material/renderer (contract §4 cleanup). */
  dispose(): void;
}

const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), max);

export function createObservatoryScene(
  canvas: HTMLCanvasElement,
): ObservatorySceneHandle {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
  });
  renderer.setClearColor(0x000000, 0); // transparent — page bg shows through
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(
    CAMERA.fov,
    1,
    CAMERA.near,
    CAMERA.far,
  );
  camera.position.set(0, 0, CAMERA.baseZ);

  /* ---- §1 Spectral wireframe sigil ---------------------------------- */

  const sigilGeometry = new THREE.TorusKnotGeometry(
    SIGIL.radius,
    SIGIL.tube,
    SIGIL.tubularSegments,
    SIGIL.radialSegments,
  );
  const positionAttr = sigilGeometry.getAttribute("position");
  if (!positionAttr) {
    throw new Error("Observatory: TorusKnotGeometry has no position attribute");
  }
  const vertexCount = positionAttr.count;

  // Per-vertex spectral gradient, band-limited to the Singularity family.
  const colors = new Float32Array(vertexCount * 3);
  // Precomputed random displacement vectors (breathing directions).
  const displacements = new Float32Array(vertexCount * 3);
  const vertexColor = new THREE.Color();
  for (let i = 0; i < vertexCount; i += 1) {
    const t = vertexCount > 1 ? i / (vertexCount - 1) : 0;
    vertexColor.setHSL(
      SIGIL.hueMin + (SIGIL.hueMax - SIGIL.hueMin) * t,
      SIGIL.saturation,
      SIGIL.lightness,
    );
    colors[i * 3] = vertexColor.r;
    colors[i * 3 + 1] = vertexColor.g;
    colors[i * 3 + 2] = vertexColor.b;
    displacements[i * 3] = Math.random() * 2 - 1;
    displacements[i * 3 + 1] = Math.random() * 2 - 1;
    displacements[i * 3 + 2] = Math.random() * 2 - 1;
  }
  sigilGeometry.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
  sigilGeometry.setAttribute(
    "aDisplacement",
    new THREE.BufferAttribute(displacements, 3),
  );

  // Uniform multiplier whose hue drifts every frame (offsetHSL per contract).
  const sigilHue = new THREE.Color(0xffffff);
  const sigilMaterial = new THREE.ShaderMaterial({
    uniforms: {
      amplitude: { value: SIGIL.breathBase },
      color: { value: sigilHue },
      opacity: { value: SIGIL.opacity },
    },
    vertexShader: SIGIL_VERTEX_SHADER,
    fragmentShader: SIGIL_FRAGMENT_SHADER,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: false,
    depthWrite: false,
    wireframe: true,
  });
  const sigil = new THREE.Mesh(sigilGeometry, sigilMaterial);
  sigil.position.set(SIGIL.x, 0, 0);
  scene.add(sigil);

  /* ---- §2 Dust field ------------------------------------------------- */

  const dustPositions = new Float32Array(DUST.count * 3);
  const dustVelocities = new Float32Array(DUST.count * 3);
  const zSpan = DUST.zMax - DUST.zMin;
  for (let i = 0; i < DUST.count; i += 1) {
    dustPositions[i * 3] = (Math.random() * 2 - 1) * DUST.boundX;
    dustPositions[i * 3 + 1] = (Math.random() * 2 - 1) * DUST.boundY;
    dustPositions[i * 3 + 2] = DUST.zMin + Math.random() * zSpan;
    dustVelocities[i * 3] = (Math.random() * 2 - 1) * DUST.maxDrift;
    dustVelocities[i * 3 + 1] = (Math.random() * 2 - 1) * DUST.maxDrift;
    dustVelocities[i * 3 + 2] = (Math.random() * 2 - 1) * DUST.maxDrift * 0.4;
  }
  const dustGeometry = new THREE.BufferGeometry();
  const dustPositionAttr = new THREE.BufferAttribute(dustPositions, 3);
  dustGeometry.setAttribute("position", dustPositionAttr);
  const dustMaterial = new THREE.PointsMaterial({
    color: new THREE.Color().setHSL(DUST.hue, DUST.saturation, DUST.lightness),
    size: DUST.size,
    sizeAttenuation: true,
    transparent: true,
    opacity: DUST.opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const dust = new THREE.Points(dustGeometry, dustMaterial);
  scene.add(dust);

  /* ---- §3 Pointer parallax state ------------------------------------- */

  let aspect = 1;
  let pointerNX = 0;
  let pointerNY = 0;
  let camX = 0;
  let camY = 0;
  // Explicit `number` — `as const` config would otherwise pin literal types.
  let camZ: number = CAMERA.baseZ;
  let targetZ: number = CAMERA.baseZ;

  const updateDust = (deltaSeconds: number, frameScale: number): void => {
    // Pointer position in world units on the z=0 plane (screen-space
    // repulsion; camera parallax offset is a negligible second-order term).
    const halfH = CAMERA.baseZ * HALF_FOV_TAN;
    const pointerWorldX = pointerNX * halfH * aspect;
    const pointerWorldY = pointerNY * halfH;
    const radiusSq = DUST.repelRadius * DUST.repelRadius;

    for (let i = 0; i < DUST.count; i += 1) {
      const ix = i * 3;
      dustPositions[ix] += dustVelocities[ix] * deltaSeconds;
      dustPositions[ix + 1] += dustVelocities[ix + 1] * deltaSeconds;
      dustPositions[ix + 2] += dustVelocities[ix + 2] * deltaSeconds;

      // Gentle pointer repulsion within a radius.
      const dx = dustPositions[ix] - pointerWorldX;
      const dy = dustPositions[ix + 1] - pointerWorldY;
      const distSq = dx * dx + dy * dy;
      if (distSq < radiusSq && distSq > 1e-6) {
        const dist = Math.sqrt(distSq);
        const push =
          (1 - dist / DUST.repelRadius) * DUST.repelStrength * frameScale;
        dustPositions[ix] += (dx / dist) * push;
        dustPositions[ix + 1] += (dy / dist) * push;
      }

      // Wrap around the field bounds so the field never thins out.
      if (dustPositions[ix] > DUST.boundX) dustPositions[ix] = -DUST.boundX;
      else if (dustPositions[ix] < -DUST.boundX) dustPositions[ix] = DUST.boundX;
      if (dustPositions[ix + 1] > DUST.boundY)
        dustPositions[ix + 1] = -DUST.boundY;
      else if (dustPositions[ix + 1] < -DUST.boundY)
        dustPositions[ix + 1] = DUST.boundY;
      if (dustPositions[ix + 2] > DUST.zMax) dustPositions[ix + 2] = DUST.zMin;
      else if (dustPositions[ix + 2] < DUST.zMin)
        dustPositions[ix + 2] = DUST.zMax;
    }
    dustPositionAttr.needsUpdate = true;
  };

  return {
    resize(width, height) {
      aspect = height > 0 ? width / height : 1;
      camera.aspect = aspect;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    },

    renderFrame(timeSeconds, deltaSeconds) {
      const frameScale = deltaSeconds * 60; // 1.0 at 60 fps

      // §1 breathing + per-frame jitter.
      sigilMaterial.uniforms.amplitude.value =
        SIGIL.breathBase +
        SIGIL.breathAmplitude *
          Math.sin(SIGIL.breathFrequency * timeSeconds) +
        SIGIL.jitter * (0.5 - Math.random());
      // §1 rotation (0.0025 per 60 fps frame — spec-blessed rate).
      sigil.rotation.y += SIGIL.rotationPerFrame * frameScale;
      // §1 uniform hue drift.
      sigilHue.offsetHSL(SIGIL.hueDrift * frameScale, 0, 0);

      // §2 dust drift + pointer repulsion.
      updateDust(deltaSeconds, frameScale);

      // §3 camera parallax — smooth exponential approach, never snappy.
      camX += (pointerNX * CAMERA.parallaxXY - camX) * CAMERA.lerp;
      camY += (pointerNY * CAMERA.parallaxXY - camY) * CAMERA.lerp;
      camZ += (targetZ - camZ) * CAMERA.lerp;
      camera.position.set(camX, camY, camZ);

      renderer.render(scene, camera);
    },

    setPointer(nx, ny) {
      pointerNX = clamp(nx, -1, 1);
      pointerNY = clamp(ny, -1, 1);
    },

    nudgeZoom(delta) {
      targetZ = clamp(
        targetZ + delta,
        CAMERA.baseZ - CAMERA.zoomRange,
        CAMERA.baseZ + CAMERA.zoomRange,
      );
    },

    dispose() {
      sigilGeometry.dispose();
      sigilMaterial.dispose();
      dustGeometry.dispose();
      dustMaterial.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}
