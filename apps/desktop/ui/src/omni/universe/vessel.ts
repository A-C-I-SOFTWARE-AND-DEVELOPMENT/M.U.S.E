import type { UniverseCommand, Vessel, VesselClassId } from './types.ts';

export const VESSEL_SYSTEM_MAP = {
  neuralCore: 'agent_binding.model_routing',
  sensorArray: 'agent_binding.capabilities',
  shields: 'agent_binding.permission_scopes',
  flightRecorder: 'agent_binding.audit_ref',
} as const;

export interface VesselCosmetics {
  paint?: string;
  name?: string;
  markings?: string;
}

export interface CosmeticPatch {
  command_type: 'vessel.cosmetics.update';
  payload: { vessel_id: string; cosmetics: VesselCosmetics };
}

export function cosmeticCommand(vesselId: string, cosmetics: VesselCosmetics): CosmeticPatch {
  return {
    command_type: 'vessel.cosmetics.update',
    payload: { vessel_id: vesselId, cosmetics: { ...cosmetics } },
  };
}

export function testFlightCommand(
  vesselId: string,
  expectedVersion: number,
  actorId: string,
): UniverseCommand {
  const commandId = `cmd_test_flight_${vesselId}_${expectedVersion}`;
  return {
    command_id: commandId,
    command_type: 'mission.create',
    realm_id: 'rlm_local',
    actor_id: actorId,
    stream_type: 'mission',
    stream_id: `sim_${vesselId}_${expectedVersion}`,
    expected_version: 0,
    payload: {
      id: `sim_${vesselId}_${expectedVersion}`,
      source_type: 'vessel_test_flight',
      source_id: vesselId,
      mode: 'simulation',
    },
    authorization: {
      allowed: false,
      reason: 'server must authorize simulation',
      scopes: [],
      owner_gate: 'not_required',
    },
    provenance: {
      source: 'atlas_shipyard_draft',
      evidence: [`vessel:${vesselId}`, `version:${expectedVersion}`],
      confidence: 1,
      signature: null,
    },
    causation_id: commandId,
    correlation_id: commandId,
    simulation: true,
  };
}

export function vesselClassOf(vessel: Vessel): VesselClassId {
  return vessel.vessel_class ?? vessel.class ?? 'scout';
}

export function vesselSystemValue(vessel: Vessel, system: keyof typeof VESSEL_SYSTEM_MAP): unknown {
  const field = VESSEL_SYSTEM_MAP[system].split('.')[1] as keyof NonNullable<Vessel['agent_binding']>;
  return vessel.agent_binding?.[field];
}

export function unavailableVesselSystems(vessel: Vessel): string[] {
  return (Object.keys(VESSEL_SYSTEM_MAP) as Array<keyof typeof VESSEL_SYSTEM_MAP>)
    .filter((system) => vesselSystemValue(vessel, system) == null)
    .map((system) => VESSEL_SYSTEM_MAP[system]);
}
