import { Component, useEffect, useMemo, useRef, type ErrorInfo, type ReactNode } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { UniverseRoute } from '../catalog.ts';
import type { FidelitySettings } from '../fidelity.ts';
import { projectUniverseGraph } from '../semanticZoom.ts';
import type { UniverseSnapshot, Vessel } from '../types.ts';
import { AtlasCrown } from './AtlasCrown.tsx';
import { CelestialEnvironment } from './CelestialEnvironment.tsx';
import { GalacticStationField } from './GalacticStationField.tsx';
import { NeuralCore } from './NeuralCore.tsx';
import { StationRoom } from './StationRoom.tsx';
import { AgentVessel } from './AgentVessel.tsx';
import { VesselInterior } from './VesselInterior.tsx';
import { useUniverseStore, type RenderDiagnostics } from '../store.ts';

function ContextGuard() {
  const { gl } = useThree();
  useEffect(() => {
    const failed = (event: Event) => {
      event.preventDefault();
      window.dispatchEvent(new CustomEvent('universe:webgl-failed', { detail: 'context-lost' }));
    };
    gl.domElement.addEventListener('webglcontextlost', failed);
    return () => gl.domElement.removeEventListener('webglcontextlost', failed);
  }, [gl]);
  return null;
}

function CameraDrift({ strength }: { strength: number }) {
  const { camera, pointer } = useThree();
  useFrame((_, delta) => {
    camera.position.x = THREE.MathUtils.damp(camera.position.x, pointer.x * strength, 2.4, delta);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, 1.2 + pointer.y * strength * 0.42, 2.4, delta);
    camera.lookAt(0, 0, 0);
  });
  return null;
}

function Diagnostics({
  tier,
  graphNodeCount,
  report,
}: {
  tier: FidelitySettings['tier'];
  graphNodeCount: number;
  report: (patch: Partial<RenderDiagnostics>) => void;
}) {
  const { gl } = useThree();
  const elapsed = useRef<number[]>([]);
  const frames = useRef(0);
  useFrame((_, delta) => {
    elapsed.current.push(delta * 1000);
    if (elapsed.current.length > 90) elapsed.current.shift();
    frames.current += 1;
    if (frames.current % 90 !== 0) return;
    const average = elapsed.current.reduce((sum, value) => sum + value, 0) / Math.max(elapsed.current.length, 1);
    report({
      tier,
      dpr: gl.getPixelRatio(),
      frameTimeMs: Number(average.toFixed(2)),
      drawCalls: gl.info.render.calls,
      triangles: gl.info.render.triangles,
      textureMemoryMb: Number((gl.info.memory.textures * 4).toFixed(1)),
      graphNodeCount,
    });
  });
  return null;
}

function SceneContent({
  route,
  snapshot,
  settings,
}: {
  route: UniverseRoute;
  snapshot: UniverseSnapshot | null;
  settings: FidelitySettings;
}) {
  const graph = useMemo(() => projectUniverseGraph(snapshot), [snapshot]);
  const selected = useUniverseStore((state) => state.selected);
  const vessels = Array.isArray(snapshot?.vessels) ? snapshot.vessels : [];
  const vessel = (vessels.find((entry) => entry.id === selected) ?? vessels[0]) as Vessel | undefined;

  if (route.scene === 'neural-core') {
    return (
      <>
        <GalacticStationField settings={settings} showCrown={false} density={0.7} />
        <NeuralCore nodes={graph.nodes} edges={graph.edges} settings={settings} />
      </>
    );
  }
  if (route.scene === 'vessel-exterior' && vessel) {
    return (
      <>
        <GalacticStationField settings={settings} crownScale={0.28} crownPosition={[14, 2, -26]} />
        <AgentVessel vessel={vessel} settings={settings} />
      </>
    );
  }
  if (route.scene === 'vessel-interior' && vessel) {
    return (
      <>
        <GalacticStationField settings={settings} crownScale={0.22} crownPosition={[16, 1, -30]} />
        <VesselInterior vessel={vessel} settings={settings} />
      </>
    );
  }
  if (route.scene === 'station-room' || route.scene.startsWith('vessel-') || route.scene === 'celestial-map') {
    return (
      <>
        <GalacticStationField
          settings={settings}
          crownScale={route.scene === 'celestial-map' ? 0.55 : 0.34}
          crownPosition={route.scene === 'celestial-map' ? [4, 0.4, -14] : [11, -0.6, -22]}
        />
        {route.scene === 'celestial-map' ? null : <StationRoom route={route} settings={settings} />}
      </>
    );
  }
  return (
    <>
      <GalacticStationField settings={settings} showCrown={false} density={0.85} />
      <AtlasCrown settings={settings} />
    </>
  );
}

class SceneErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, _info: ErrorInfo): void {
    window.dispatchEvent(new CustomEvent('universe:webgl-failed', { detail: error.message }));
  }

  render(): ReactNode {
    return this.state.failed ? null : this.props.children;
  }
}

export function UniverseScene({
  route,
  snapshot,
  settings,
  particleDensity = 1,
}: {
  route: UniverseRoute;
  snapshot: UniverseSnapshot | null;
  settings: FidelitySettings;
  particleDensity?: number;
}) {
  const reportDiagnostics = useUniverseStore((state) => state.reportDiagnostics);
  const graphNodeCount = useMemo(() => projectUniverseGraph(snapshot).nodes.length, [snapshot]);

  if (!settings.mount3d) {
    return (
      <div className="universe-2d-fallback" data-room={route.room} aria-hidden="true">
        <span className="universe-2d-fallback__crown" />
      </div>
    );
  }

  return (
    <SceneErrorBoundary>
      <div className="universe-scene" data-room={route.room} aria-hidden="true">
        <Canvas
          dpr={[1, settings.dprCap]}
          camera={{ position: [0, 1.2, route.scene === 'station-room' ? 12 : 16], fov: 46, near: 0.08, far: 2200 }}
          shadows={settings.shadowMap > 0}
          gl={{
            antialias: settings.antialiasing,
            alpha: true,
            powerPreference: 'high-performance',
            toneMapping: THREE.ACESFilmicToneMapping,
          }}
          onCreated={({ gl }) => {
            gl.toneMappingExposure = 0.82;
            gl.outputColorSpace = THREE.SRGBColorSpace;
            gl.shadowMap.enabled = settings.shadowMap > 0;
            gl.shadowMap.type = THREE.PCFSoftShadowMap;
          }}
        >
          <color attach="background" args={['#020306']} />
          <fogExp2 attach="fog" args={['#05070a', 0.025]} />
          <ambientLight color="#90a5b1" intensity={0.18} />
          <directionalLight
            color="#f3f1e8"
            intensity={3.2}
            position={[8, 11, 9]}
            castShadow={settings.shadowMap > 0}
            shadow-mapSize-width={settings.shadowMap}
            shadow-mapSize-height={settings.shadowMap}
          />
          <directionalLight color="#668da4" intensity={0.82} position={[-8, -3, -7]} />
          <CelestialEnvironment settings={settings} density={particleDensity} />
          <SceneContent route={route} snapshot={snapshot} settings={settings} />
          {settings.motion && <CameraDrift strength={settings.cameraDrift} />}
          <ContextGuard />
          <Diagnostics tier={settings.tier} graphNodeCount={graphNodeCount} report={reportDiagnostics} />
        </Canvas>
      </div>
    </SceneErrorBoundary>
  );
}
