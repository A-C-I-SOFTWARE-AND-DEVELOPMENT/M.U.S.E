'use client'

import * as THREE from 'three'
import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { OrbitControls, Grid, ContactShadows, Environment, Html } from '@react-three/drei'

/**
 * muse Sandbox 3D scene — a real-time preview stage.
 * Cinema screen plays the storyboard reel; character portraits arc around it;
 * spectral stage lighting; orbit camera.
 */

export interface SandboxSceneProps {
  reelImages: string[]
  portraits: { url: string; name: string }[]
  frame: number
  showGrid: boolean
  showPortraits: boolean
  autoRotate: boolean
  fog: number
}

// ---- Cinema screen --------------------------------------------------------

function CinemaScreen({ images, frame }: { images: string[]; frame: number }) {
  const materials = useMemo(() => {
    return images.map((url) => {
      const tex = new THREE.TextureLoader().load(url)
      tex.colorSpace = THREE.SRGBColorSpace
      return new THREE.MeshBasicMaterial({ map: tex, toneMapped: false })
    })
  }, [images])

  const geom = useMemo(() => new THREE.PlaneGeometry(16, 9), [])

  if (images.length === 0) {
    return (
      <group position={[0, 4, -8]}>
        <mesh geometry={geom}>
          <meshBasicMaterial color="#0b0d12" />
        </mesh>
        <mesh position={[0, 0, -0.1]}>
          <planeGeometry args={[16.6, 9.6]} />
          <meshStandardMaterial color="#050507" metalness={0.6} roughness={0.4} />
        </mesh>
        <Html position={[0, 0, 0.1]} center>
          <div style={{ color: '#6b7388', fontFamily: 'ui-monospace, monospace', fontSize: 12, whiteSpace: 'nowrap', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            No frames in the reel
          </div>
        </Html>
      </group>
    )
  }

  const idx = ((frame % images.length) + images.length) % images.length
  return (
    <group position={[0, 4, -8]}>
      <mesh geometry={geom} material={materials[idx]} />
      <mesh position={[0, 0, -0.1]}>
        <planeGeometry args={[16.6, 9.6]} />
        <meshStandardMaterial color="#050507" metalness={0.6} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, -0.25]}>
        <planeGeometry args={[22, 14]} />
        <meshBasicMaterial color="#7ae0ff" transparent opacity={0.06} />
      </mesh>
    </group>
  )
}

// ---- Portrait arc ---------------------------------------------------------

function PortraitArc({ portraits }: { portraits: { url: string; name: string }[] }) {
  const radius = 11
  const arcSpan = Math.min(Math.PI * 0.9, portraits.length * 0.35)
  return (
    <group position={[0, 1.2, -2]}>
      {portraits.map((p, i) => {
        const t = portraits.length === 1 ? 0.5 : i / (portraits.length - 1)
        const angle = -arcSpan / 2 + t * arcSpan
        const x = Math.sin(angle) * radius
        const z = -Math.cos(angle) * radius + radius
        const y = 3
        return (
          <PortraitCard
            key={i}
            url={p.url}
            name={p.name}
            position={[x, y, z]}
            rotation={[0, angle, 0]}
            index={i}
          />
        )
      })}
    </group>
  )
}

function PortraitCard({
  url,
  name,
  position,
  rotation,
  index,
}: {
  url: string
  name: string
  position: [number, number, number]
  rotation: [number, number, number]
  index: number
}) {
  const ref = useRef<THREE.Group>(null!)
  const tex = useMemo(() => {
    const t = new THREE.TextureLoader().load(url)
    t.colorSpace = THREE.SRGBColorSpace
    return t
  }, [url])

  useFrame((state) => {
    if (!ref.current) return
    ref.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * 0.6 + index) * 0.12
  })

  return (
    <group ref={ref} position={position} rotation={rotation}>
      <mesh>
        <planeGeometry args={[2.25, 3]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, -0.05]}>
        <planeGeometry args={[2.45, 3.2]} />
        <meshStandardMaterial color="#0b0d12" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0, -0.08]}>
        <planeGeometry args={[2.55, 3.3]} />
        <meshBasicMaterial color="#7ae0ff" transparent opacity={0.12} />
      </mesh>
      <Html position={[0, -2, 0.1]} center transform occlude distanceFactor={10}>
        <div
          style={{
            fontFamily: 'ui-monospace, monospace',
            fontSize: 9,
            color: '#aab2c4',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            whiteSpace: 'nowrap',
            padding: '2px 8px',
            background: 'rgba(5,5,7,0.7)',
            border: '1px solid rgba(122,224,255,0.3)',
            borderRadius: 3,
          }}
        >
          {name}
        </div>
      </Html>
    </group>
  )
}

// ---- Stage lighting -------------------------------------------------------

function StageLighting() {
  return (
    <>
      <ambientLight intensity={0.25} color="#aab2c4" />
      <spotLight
        position={[0, 12, 2]}
        angle={0.6}
        penumbra={0.8}
        intensity={120}
        color="#ffffff"
        target-position={[0, 4, -8]}
      />
      <pointLight position={[-12, 6, 2]} intensity={40} color="#7ae0ff" distance={30} />
      <pointLight position={[12, 6, 2]} intensity={40} color="#b388ff" distance={30} />
      <pointLight position={[0, 4, 8]} intensity={15} color="#5b8cff" distance={25} />
    </>
  )
}

// ---- Main scene -----------------------------------------------------------

export function SandboxScene({
  reelImages,
  portraits,
  frame,
  showGrid,
  showPortraits,
  autoRotate,
  fog,
}: SandboxSceneProps) {
  return (
    <>
      {fog > 0 && <fog attach="fog" args={['#050507', 8, 8 + fog * 40]} />}
      <StageLighting />
      <Environment preset="night" />

      <CinemaScreen images={reelImages} frame={frame} />

      {showPortraits && portraits.length > 0 && <PortraitArc portraits={portraits} />}

      {showGrid && (
        <Grid
          position={[0, -0.5, 0]}
          args={[60, 60]}
          cellSize={1}
          cellThickness={0.5}
          cellColor="#1c2030"
          sectionSize={5}
          sectionThickness={1}
          sectionColor="#7ae0ff"
          fadeDistance={45}
          fadeStrength={1.5}
          infiniteGrid
        />
      )}

      <ContactShadows
        position={[0, -0.49, -8]}
        opacity={0.4}
        scale={30}
        blur={2.5}
        far={12}
        color="#000000"
      />

      <OrbitControls
        enablePan
        enableZoom
        enableRotate
        autoRotate={autoRotate}
        autoRotateSpeed={0.5}
        minDistance={6}
        maxDistance={40}
        maxPolarAngle={Math.PI * 0.52}
        target={[0, 3, -4]}
        makeDefault
      />
    </>
  )
}
