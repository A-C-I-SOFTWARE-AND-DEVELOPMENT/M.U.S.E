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

export function AgentVessel({ vessel, settings }: { vessel: Vessel; settings: FidelitySettings }) {
  const vesselClass = vesselClassOf(vessel);
  const profile = CLASS_PROFILE[vesselClass];
  const paint = vessel.cosmetics?.paint ?? '#8e979b';
  const hasDegradation = (vessel.degraded_fields?.length ?? 0) > 0;
  return (
    <group name={`vessel:${vessel.id}`} userData={{ vesselId: vessel.id, vesselClass }} rotation={[0.04, -0.4, -0.03]}>
      <mesh rotation={[Math.PI / 2, 0, 0]} scale={[1, 1, profile.length / profile.beam]}>
        <capsuleGeometry args={[profile.beam * 0.58, profile.length * 0.38, 10, Math.max(16, settings.geometrySegments / 2)]} />
        <meshPhysicalMaterial color={paint} metalness={0.86} roughness={0.38} clearcoat={0.08} />
      </mesh>
      <mesh position={[0, 0.15, -profile.length * 0.42]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[profile.beam * 0.56, profile.length * 0.34, Math.max(12, settings.geometrySegments / 3)]} />
        <meshStandardMaterial color="#70797d" metalness={0.9} roughness={0.43} />
      </mesh>
      <mesh position={[0, 0.38, profile.length * 0.34]} rotation={[Math.PI / 2, 0, 0]}>
        <sphereGeometry args={[profile.beam * 0.42, 32, 14, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshPhysicalMaterial color="#cde9ee" transmission={settings.materialTransmission * 0.65} roughness={0.08} metalness={0.18} clearcoat={1} />
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side} position={[side * profile.wing * 0.62, -0.12, 0.05]}>
          <mesh rotation={[0.08, 0, side * -0.04]}>
            <boxGeometry args={[profile.wing, 0.1, profile.length * 0.55]} />
            <meshStandardMaterial color="#3a4247" metalness={0.84} roughness={0.52} />
          </mesh>
          <mesh position={[side * profile.wing * 0.36, 0, -0.2]}>
            <boxGeometry args={[profile.wing * 0.58, 0.035, profile.length * 0.46]} />
            <meshStandardMaterial color="#263c48" metalness={0.46} roughness={0.75} />
          </mesh>
          {Array.from({ length: profile.pods }, (_, index) => (
            <mesh key={index} position={[side * profile.wing * 0.28, -0.2, -profile.length * 0.25 + index * 0.62]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.18, 0.22, 0.82, 12]} />
              <meshStandardMaterial color="#596267" metalness={0.88} roughness={0.46} />
            </mesh>
          ))}
        </group>
      ))}
      <group position={[0, -0.1, profile.length * 0.56]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[profile.beam * 0.42, 0.08, 10, 32]} />
          <meshStandardMaterial color="#bcc3c4" metalness={0.9} roughness={0.34} />
        </mesh>
        <mesh position={[0, 0, 0.08]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[profile.beam * 0.35, profile.beam * 0.35, 0.18, 24]} />
          <meshStandardMaterial color="#1c2226" metalness={0.82} roughness={0.58} />
        </mesh>
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
