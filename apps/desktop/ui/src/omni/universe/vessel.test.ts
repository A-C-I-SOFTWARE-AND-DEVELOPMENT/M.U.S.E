import assert from 'node:assert/strict';
import test from 'node:test';
import { VESSEL_SYSTEM_MAP, cosmeticCommand, testFlightCommand } from './vessel.ts';

test('functional vessel systems map only to authoritative agent-binding fields', () => {
  assert.equal(VESSEL_SYSTEM_MAP.neuralCore, 'agent_binding.model_routing');
  assert.equal(VESSEL_SYSTEM_MAP.sensorArray, 'agent_binding.capabilities');
  assert.equal(VESSEL_SYSTEM_MAP.shields, 'agent_binding.permission_scopes');
  assert.equal(VESSEL_SYSTEM_MAP.flightRecorder, 'agent_binding.audit_ref');
});

test('cosmetic changes cannot alter capabilities', () => {
  const patch = cosmeticCommand('vsl_1', { paint: '#8ba6b8', name: 'Asterion' });
  assert.deepEqual(Object.keys(patch.payload).sort(), ['cosmetics', 'vessel_id']);
});

test('test flights are always explicitly simulated', () => {
  assert.equal(testFlightCommand('vsl_1', 3, 'ply_owner').simulation, true);
});
