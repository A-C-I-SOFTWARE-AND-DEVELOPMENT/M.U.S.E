import type { ReactNode } from 'react';
import type { UniverseRoute } from '../catalog.ts';
import type { FidelitySettings } from '../fidelity.ts';

const FLOOR = '#252a2f';
const WALL = '#555f65';
const DARK = '#12171b';
const SCREEN = '#92c3d1';

function RoomShell({ children, room }: { children: ReactNode; room: string }) {
  return (
    <group name={`room:${room}`} userData={{ room }}>
      <mesh position={[0, -2.45, 0]}>
        <boxGeometry args={[13, 0.25, 10]} />
        <meshStandardMaterial color={FLOOR} metalness={0.72} roughness={0.62} />
      </mesh>
      <mesh position={[0, 2.4, -4.8]}>
        <boxGeometry args={[13, 9.5, 0.22]} />
        <meshStandardMaterial color={DARK} metalness={0.55} roughness={0.72} />
      </mesh>
      {[-6.1, 6.1].map((x) => (
        <mesh key={x} position={[x, 1.2, 0]}>
          <boxGeometry args={[0.24, 7.2, 10]} />
          <meshStandardMaterial color={WALL} metalness={0.76} roughness={0.52} />
        </mesh>
      ))}
      {/* Observation windows — transparent panes look out onto the galactic field. */}
      {[-3.2, 0, 3.2].map((x) => (
        <mesh key={`win-${x}`} position={[x, 1.35, -4.68]}>
          <planeGeometry args={[2.4, 1.6]} />
          <meshPhysicalMaterial
            color="#9ec8d6"
            transparent
            opacity={0.18}
            roughness={0.05}
            metalness={0.1}
            transmission={0.55}
            thickness={0.2}
          />
        </mesh>
      ))}
      <rectAreaLight position={[0, 4.2, 0]} rotation={[-Math.PI / 2, 0, 0]} width={8} height={2} intensity={2.2} color="#dce9e9" />
      <pointLight position={[0, 2.2, -3.8]} color="#8ad8ee" intensity={1.6} distance={10} decay={2} />
      {children}
    </group>
  );
}

function Console({ position, rotation = 0 }: { position: [number, number, number]; rotation?: number }) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <mesh rotation={[-0.3, 0, 0]}>
        <boxGeometry args={[1.8, 0.18, 0.92]} />
        <meshStandardMaterial color="#333b40" metalness={0.78} roughness={0.48} />
      </mesh>
      <mesh position={[0, 0.15, -0.43]} rotation={[-0.3, 0, 0]}>
        <planeGeometry args={[1.35, 0.42]} />
        <meshBasicMaterial color={SCREEN} transparent opacity={0.42} />
      </mesh>
      <mesh position={[0, -0.7, 0.1]}>
        <boxGeometry args={[0.22, 1.35, 0.45]} />
        <meshStandardMaterial color={DARK} metalness={0.75} roughness={0.6} />
      </mesh>
    </group>
  );
}

function RoomFeature({ room }: { room: UniverseRoute['room'] }) {
  switch (room) {
    case 'command-bridge':
      return <>{[-3, 0, 3].map((x) => <Console key={x} position={[x, -0.7, 0]} />)}<mesh position={[0, 1.2, -4.55]}><planeGeometry args={[8, 3]} /><meshPhysicalMaterial color="#7f9fa8" transparent opacity={0.22} roughness={0.1} /></mesh></>;
    case 'neural-chamber':
      return <><mesh position={[0, 0.2, 0]}><sphereGeometry args={[1.35, 48, 24]} /><meshPhysicalMaterial color="#dff8ff" emissive="#8ad8ee" emissiveIntensity={0.7} transmission={0.6} transparent opacity={0.86} roughness={0.08} /></mesh>{[2, 2.8, 3.6].map((r, index) => <mesh key={r} rotation={[Math.PI / 2 + index * 0.3, index * 0.45, 0]}><torusGeometry args={[r, 0.035, 8, 64]} /><meshStandardMaterial color="#8a9499" metalness={0.9} roughness={0.36} /></mesh>)}</>;
    case 'sensor-laboratory':
      return <><mesh position={[0, 0, -1]} rotation={[0.2, 0, 0]}><cylinderGeometry args={[2.3, 0.35, 0.32, 48]} /><meshStandardMaterial color="#9ba6aa" metalness={0.88} roughness={0.34} /></mesh><mesh position={[0, -0.2, 1]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.15, 0.32, 3.8, 16]} /><meshStandardMaterial color={WALL} metalness={0.82} roughness={0.48} /></mesh></>;
    case 'fabrication-bay':
      return <>{[-3, 3].map((x) => <group key={x} position={[x, 0, 0]}><mesh><boxGeometry args={[0.45, 5, 0.45]} /><meshStandardMaterial color={WALL} metalness={0.9} roughness={0.44} /></mesh><mesh position={[-x / 2, 1.8, 0]} rotation={[0, 0, x > 0 ? -0.8 : 0.8]}><boxGeometry args={[3.2, 0.3, 0.38]} /><meshStandardMaterial color="#747d80" metalness={0.92} roughness={0.4} /></mesh></group>)}<mesh position={[0, -1.95, 0]}><cylinderGeometry args={[2.3, 2.3, 0.3, 48]} /><meshStandardMaterial color="#30383d" metalness={0.84} roughness={0.5} /></mesh></>;
    case 'memory-vault':
      return <>{Array.from({ length: 7 }, (_, row) => Array.from({ length: 9 }, (_, column) => <mesh key={`${row}-${column}`} position={[-4.4 + column * 1.1, -1.65 + row * 0.64, -4.55]}><boxGeometry args={[0.82, 0.42, 0.18]} /><meshStandardMaterial color={(row + column) % 5 === 0 ? '#566f77' : '#293138'} emissive={(row + column) % 5 === 0 ? '#6da9b8' : '#000000'} emissiveIntensity={0.18} metalness={0.72} roughness={0.52} /></mesh>))}</>;
    case 'drone-hangar':
      return <>{[-3.4, 0, 3.4].map((x) => <group key={x} position={[x, -0.9, 0]}><mesh><sphereGeometry args={[0.48, 18, 10]} /><meshStandardMaterial color="#697176" metalness={0.92} roughness={0.34} /></mesh>{[-1, 1].map((side) => <mesh key={side} position={[side * 0.72, 0, 0]}><boxGeometry args={[0.88, 0.09, 0.38]} /><meshStandardMaterial color="#343b40" metalness={0.86} roughness={0.44} /></mesh>)}</group>)}<mesh position={[0, 1.7, -4.5]}><planeGeometry args={[7.5, 1.2]} /><meshBasicMaterial color="#68828b" transparent opacity={0.25} /></mesh></>;
    case 'engineering':
      return <><mesh position={[0, -0.5, 0]}><cylinderGeometry args={[1.25, 1.6, 4.1, 32]} /><meshPhysicalMaterial color="#7c8588" metalness={0.9} roughness={0.34} clearcoat={0.1} /></mesh>{[-2.7, 2.7].map((x) => <mesh key={x} position={[x, 0, -1]}><torusGeometry args={[1.1, 0.16, 12, 42, Math.PI * 1.5]} /><meshStandardMaterial color="#4c555b" metalness={0.84} roughness={0.52} /></mesh>)}</>;
    case 'security-airlock':
      return <><mesh position={[0, 0.2, -4.55]}><boxGeometry args={[4.4, 5.3, 0.32]} /><meshStandardMaterial color="#596166" metalness={0.9} roughness={0.46} /></mesh><mesh position={[0, 0.2, -4.35]}><torusGeometry args={[1.65, 0.16, 10, 8]} /><meshStandardMaterial color="#20262b" metalness={0.82} roughness={0.55} /></mesh><Console position={[3.5, -0.7, -2.8]} rotation={-0.6} /></>;
    case 'governance-chamber':
      return <><mesh position={[0, -1.4, 0]}><cylinderGeometry args={[2.7, 2.9, 0.42, 10]} /><meshStandardMaterial color="#4c555a" metalness={0.78} roughness={0.55} /></mesh>{Array.from({ length: 10 }, (_, index) => { const a = index / 10 * Math.PI * 2; return <mesh key={index} position={[Math.cos(a) * 4, -1.3, Math.sin(a) * 4]} rotation={[0, -a, 0]}><boxGeometry args={[0.9, 1.45, 0.9]} /><meshStandardMaterial color={DARK} metalness={0.66} roughness={0.7} /></mesh>; })}</>;
    case 'cinema-array':
      return <><mesh position={[0, 0.8, -4.5]}><planeGeometry args={[9.2, 4.8]} /><meshBasicMaterial color="#718b94" transparent opacity={0.3} /></mesh>{[-0.22, 0.22].map((x) => <group key={x} position={[x, -0.3, 1.8]}><mesh><boxGeometry args={[0.32, 0.46, 0.9]} /><meshStandardMaterial color="#3e464b" metalness={0.88} roughness={0.38} /></mesh><mesh position={[0, 0, -0.5]} rotation={[0, Math.PI / 2, 0]}><cylinderGeometry args={[0.19, 0.24, 0.48, 24]} /><meshPhysicalMaterial color="#c6eef8" transmission={0.5} roughness={0.08} /></mesh></group>)}</>;
    case 'game-foundry':
      return <><gridHelper args={[10, 20, '#48606b', '#252d32']} position={[0, -2.28, 0]} />{Array.from({ length: 8 }, (_, index) => <mesh key={index} position={[(index % 4 - 1.5) * 2.2, -1.2 + Math.floor(index / 4) * 1.6, -1.4]}><boxGeometry args={[1.2, 1.2, 1.2]} /><meshStandardMaterial color={index % 3 === 0 ? '#5a7079' : '#363f44'} wireframe={index % 2 === 0} metalness={0.7} roughness={0.58} /></mesh>)}</>;
    case 'release-dock':
      return <><mesh position={[0, -1.9, 0]}><boxGeometry args={[7.8, 0.45, 4.8]} /><meshStandardMaterial color="#3c454a" metalness={0.86} roughness={0.52} /></mesh>{[-3.8, 3.8].map((x) => <mesh key={x} position={[x, 0, 0]}><boxGeometry args={[0.34, 5.2, 0.48]} /><meshStandardMaterial color={WALL} metalness={0.92} roughness={0.42} /></mesh>)}<mesh position={[0, 0.9, -4.5]}><planeGeometry args={[8, 2.6]} /><meshBasicMaterial color="#68838c" transparent opacity={0.24} /></mesh></>;
    case 'shipyard':
      return <>{[-3.8, 3.8].map((x) => <group key={x} position={[x, 0, 0]}><mesh><boxGeometry args={[0.38, 6.4, 0.38]} /><meshStandardMaterial color="#697276" metalness={0.92} roughness={0.4} /></mesh>{[-1.8, 0, 1.8].map((y) => <mesh key={y} position={[-x, y, 0]}><boxGeometry args={[7.6, 0.22, 0.3]} /><meshStandardMaterial color="#40484d" metalness={0.88} roughness={0.48} /></mesh>)}</group>)}<mesh position={[0, -2, 0]}><boxGeometry args={[8.8, 0.25, 3]} /><meshStandardMaterial color="#2e373b" metalness={0.82} roughness={0.56} /></mesh></>;
    case 'relay-embassy':
      return <><mesh position={[0, -0.4, 0]}><cylinderGeometry args={[1.1, 1.6, 4.2, 24]} /><meshStandardMaterial color="#606a6e" metalness={0.84} roughness={0.46} /></mesh>{[1.8, 2.7, 3.6].map((r, index) => <mesh key={r} rotation={[Math.PI / 2 + index * 0.25, 0, index * 0.5]}><torusGeometry args={[r, 0.035, 8, 56]} /><meshBasicMaterial color={index % 2 ? '#8e84a9' : '#6e9cac'} transparent opacity={0.4} /></mesh>)}</>;
    case 'production-command':
      return <><mesh position={[0, 1.1, -4.52]}><planeGeometry args={[9.4, 3.2]} /><meshBasicMaterial color="#7895a0" transparent opacity={0.22} /></mesh>{Array.from({ length: 5 }, (_, index) => <group key={index} position={[-4 + index * 2, -1.5, 0]}><mesh><boxGeometry args={[1.5, 0.18, 2.4]} /><meshStandardMaterial color="#394146" metalness={0.78} roughness={0.54} /></mesh><mesh position={[0, 0.15, -0.4]} rotation={[-0.28, 0, 0]}><planeGeometry args={[1.1, 0.62]} /><meshBasicMaterial color="#7999a4" transparent opacity={0.35} /></mesh></group>)}</>;
    case 'crew-observation':
      return <>{Array.from({ length: 4 }, (_, row) => <mesh key={row} position={[0, -1.8 + row * 0.72, 1.8 + row * 0.7]}><boxGeometry args={[9 - row * 0.7, 0.32, 1.2]} /><meshStandardMaterial color={row % 2 ? '#293137' : '#333c41'} metalness={0.64} roughness={0.68} /></mesh>)}<mesh position={[0, 1, -4.52]}><planeGeometry args={[8, 3.6]} /><meshBasicMaterial color="#718d96" transparent opacity={0.26} /></mesh></>;
  }
}

export function StationRoom({ route, settings: _settings }: { route: UniverseRoute; settings: FidelitySettings }) {
  return (
    <RoomShell room={route.room}>
      <RoomFeature room={route.room} />
    </RoomShell>
  );
}
