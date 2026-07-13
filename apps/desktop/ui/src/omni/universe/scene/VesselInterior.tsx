import type { Vessel } from '../types.ts';
import type { FidelitySettings } from '../fidelity.ts';

const ROOMS = [
  ['airlock_security', 'Airlock / security'],
  ['command_bridge', 'Command bridge'],
  ['neural_chamber', 'Neural chamber'],
  ['sensor_laboratory', 'Sensor laboratory'],
  ['fabrication_bay', 'Fabrication bay'],
  ['memory_vault', 'Memory vault'],
  ['drone_hangar', 'Drone hangar'],
  ['engineering', 'Engineering'],
] as const;

export function VesselInterior({ vessel, settings }: { vessel: Vessel; settings: FidelitySettings }) {
  const available = new Set(vessel.rooms ?? []);
  const reportsRooms = Array.isArray(vessel.rooms);
  return (
    <group name={`vessel-interior:${vessel.id}`} userData={{ vesselId: vessel.id }}>
      <mesh position={[0, -2.25, 0]}>
        <boxGeometry args={[11.6, 0.22, 8]} />
        <meshStandardMaterial color="#282f33" metalness={0.75} roughness={0.62} />
      </mesh>
      <mesh position={[0, 1.2, -3.85]}>
        <boxGeometry args={[11.6, 7.2, 0.18]} />
        <meshStandardMaterial color="#161c20" metalness={0.58} roughness={0.76} />
      </mesh>
      {ROOMS.map(([id, label], index) => {
        const column = index % 4;
        const row = Math.floor(index / 4);
        const x = -4.2 + column * 2.8;
        const z = -1.5 + row * 3.2;
        const reportedAvailable = reportsRooms && available.has(id);
        return (
          <group key={id} position={[x, -0.85, z]} name={`interior-room:${id}`} userData={{ room: id, label, available: reportedAvailable }}>
            <mesh>
              <boxGeometry args={[2.35, 2.6, 2.55]} />
              <meshStandardMaterial
                color={reportedAvailable ? '#485257' : '#272c2f'}
                metalness={0.78}
                roughness={0.56}
                transparent
                opacity={reportedAvailable ? 0.84 : 0.48}
              />
            </mesh>
            <mesh position={[0, 0.45, 1.29]}>
              <planeGeometry args={[1.55, 0.52, Math.max(1, settings.geometrySegments / 12)]} />
              <meshBasicMaterial color={reportedAvailable ? '#7fabb6' : '#555b5e'} transparent opacity={0.45} />
            </mesh>
          </group>
        );
      })}
      <mesh position={[0, -1.78, 0]}>
        <boxGeometry args={[10.2, 0.08, 0.58]} />
        <meshBasicMaterial color="#85979d" transparent opacity={0.28} />
      </mesh>
    </group>
  );
}

export const VESSEL_INTERIOR_ROOMS = ROOMS;
