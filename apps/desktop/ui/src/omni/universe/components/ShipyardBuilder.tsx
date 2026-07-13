import { useMemo, useState } from 'react';
import type { UniverseCommand, UniverseModule, UniverseViewer, Vessel } from '../types.ts';
import { cosmeticCommand, testFlightCommand } from '../vessel.ts';

interface Props {
  vessel: Vessel | null;
  modules: Record<string, UniverseModule> | null;
  viewer: UniverseViewer | null;
  onValidate: (command: UniverseCommand) => Promise<Record<string, unknown>>;
  onApply: (command: UniverseCommand) => Promise<unknown>;
}

function commandForModule(vessel: Vessel, module: UniverseModule, viewer: UniverseViewer): UniverseCommand {
  const commandId = `cmd_module_${vessel.id}_${module.id}_${vessel.version}`;
  return {
    command_id: commandId,
    command_type: 'vessel.module.install',
    realm_id: vessel.realm_id,
    actor_id: viewer.actor_id,
    stream_type: 'vessel',
    stream_id: vessel.id,
    expected_version: vessel.version,
    payload: {
      vessel_id: vessel.id,
      module_id: module.id,
      attachment_type: module.attachment_types[0] ?? '',
    },
    authorization: {
      allowed: false,
      reason: 'server must authorize the current actor and realm membership',
      scopes: [],
      owner_gate: 'server-determined',
    },
    provenance: {
      source: 'atlas_shipyard_draft',
      evidence: [`vessel:${vessel.id}`, `module:${module.id}`, `version:${vessel.version}`],
      confidence: 1,
      signature: null,
    },
    causation_id: commandId,
    correlation_id: commandId,
    simulation: false,
  };
}

export function ShipyardBuilder({ vessel, modules, viewer, onValidate, onApply }: Props) {
  const moduleList = useMemo(() => Object.values(modules ?? {}), [modules]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [paint, setPaint] = useState(vessel?.cosmetics?.paint ?? '#8e979b');
  const [name, setName] = useState(vessel?.cosmetics?.name ?? '');
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [validatedVersion, setValidatedVersion] = useState<number | null>(null);
  const [pending, setPending] = useState<'validate' | 'apply' | 'cosmetic' | 'flight' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selected = moduleList.find((module) => module.id === selectedId) ?? null;
  const canMutate = Boolean(vessel && viewer);

  const validate = async () => {
    if (!vessel || !viewer || !selected) return;
    setPending('validate');
    setError(null);
    try {
      const result = await onValidate(commandForModule(vessel, selected, viewer));
      setValidation(result);
      setValidatedVersion(result.valid === true ? vessel.version : null);
    } catch (cause) {
      setValidation(null);
      setValidatedVersion(null);
      setError((cause as Error).message);
    } finally {
      setPending(null);
    }
  };

  const apply = async () => {
    if (!vessel || !viewer || !selected || validatedVersion !== vessel.version) return;
    setPending('apply');
    setError(null);
    try {
      await onApply(commandForModule(vessel, selected, viewer));
      setValidation(null);
      setValidatedVersion(null);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setPending(null);
    }
  };

  const updateCosmetics = async () => {
    if (!vessel || !viewer) return;
    const patch = cosmeticCommand(vessel.id, { paint, name: name.trim() || undefined });
    const commandId = `cmd_cosmetic_${vessel.id}_${vessel.version}`;
    const command: UniverseCommand = {
      command_id: commandId,
      command_type: patch.command_type,
      realm_id: vessel.realm_id,
      actor_id: viewer.actor_id,
      stream_type: 'vessel',
      stream_id: vessel.id,
      expected_version: vessel.version,
      payload: patch.payload,
      authorization: { allowed: false, reason: 'server authorization required', scopes: [], owner_gate: 'server-determined' },
      provenance: { source: 'atlas_shipyard_cosmetics', evidence: [`vessel:${vessel.id}`], confidence: 1, signature: null },
      causation_id: commandId,
      correlation_id: commandId,
      simulation: false,
    };
    setPending('cosmetic');
    setError(null);
    try {
      await onApply(command);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setPending(null);
    }
  };

  const testFlight = async () => {
    if (!vessel || !viewer) return;
    setPending('flight');
    setError(null);
    try {
      const command = { ...testFlightCommand(vessel.id, vessel.version, viewer.actor_id), realm_id: vessel.realm_id };
      await onApply(command);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setPending(null);
    }
  };

  return (
    <section className="shipyard-builder" aria-label="Neural Shipyard vessel builder">
      <div className="shipyard-builder__header">
        <div><p className="universe-eyebrow">Draft workspace</p><h2>{vessel ? vessel.cosmetics?.name ?? vessel.name ?? vessel.id : 'No vessel selected'}</h2></div>
        <span className="universe-chip">{vessel ? `v${vessel.version}` : 'Unavailable'}</span>
      </div>

      {!vessel && <p className="universe-empty-copy">The realm has not reported a vessel. A draft cannot be applied to an invented hull.</p>}
      {vessel && !viewer && <p className="universe-inline-warning">The snapshot did not report an authenticated viewer identity. Mutating controls are disabled.</p>}

      <div className="shipyard-grid">
        <div className="shipyard-modules">
          <p className="universe-eyebrow">Module catalog and snap points</p>
          {moduleList.length === 0 ? (
            <p className="universe-empty-copy">The authoritative module catalog is unavailable. No local substitute is displayed.</p>
          ) : (
            moduleList.map((module) => (
              <button key={module.id} type="button" aria-pressed={selectedId === module.id} onClick={() => { setSelectedId(module.id); setValidation(null); setValidatedVersion(null); }}>
                <span><strong>{module.id}</strong><small>{module.type} · {module.attachment_types.join(', ') || 'No snap point'}</small></span>
                <span className="mono">P{module.power} · H{module.heat}</span>
              </button>
            ))
          )}
        </div>

        <div className="shipyard-inspector">
          <p className="universe-eyebrow">Draft diagnostics</p>
          {selected ? (
            <>
              <h3>{selected.id}</h3>
              <dl className="universe-definition-grid">
                <div><dt>Power</dt><dd>{selected.power}</dd></div>
                <div><dt>Heat</dt><dd>{selected.heat}</dd></div>
                <div><dt>Compute</dt><dd>{selected.compute}</dd></div>
                <div><dt>Context</dt><dd>{selected.context}</dd></div>
                <div><dt>Requires</dt><dd>{selected.requires.join(', ') || 'None reported'}</dd></div>
                <div><dt>Conflicts</dt><dd>{selected.conflicts.join(', ') || 'None reported'}</dd></div>
                <div><dt>Trust exposure</dt><dd>{selected.trust_exposure}</dd></div>
                <div><dt>Cost class</dt><dd>{selected.cost_class}</dd></div>
              </dl>
              <div className="universe-action-row">
                <button type="button" disabled={!canMutate || pending != null} onClick={() => void validate()}>{pending === 'validate' ? 'Validating…' : 'Validate draft'}</button>
                <button type="button" className="universe-button--primary" disabled={!canMutate || validatedVersion !== vessel?.version || pending != null} onClick={() => void apply()}>{pending === 'apply' ? 'Applying…' : 'Apply validated draft'}</button>
              </div>
              {validation && <pre className="universe-evidence-block">{JSON.stringify(validation, null, 2)}</pre>}
            </>
          ) : (
            <p className="universe-empty-copy">Choose a reported module to inspect exact requirements, conflicts, budget, path, and trust exposure.</p>
          )}
        </div>
      </div>

      <div className="shipyard-cosmetics universe-panel">
        <div><p className="universe-eyebrow">Cosmetic-only continuity</p><p>Paint and naming never alter model routing, tools, scopes, or audit authority.</p></div>
        <label>Hull paint<input type="color" value={paint} onChange={(event) => setPaint(event.target.value)} /></label>
        <label>Vessel name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={64} /></label>
        <button type="button" disabled={!canMutate || pending != null} onClick={() => void updateCosmetics()}>{pending === 'cosmetic' ? 'Saving…' : 'Save cosmetics'}</button>
        <button type="button" disabled={!canMutate || pending != null} onClick={() => void testFlight()}>{pending === 'flight' ? 'Starting simulation…' : 'Test Flight · simulation'}</button>
      </div>

      {error && <p className="universe-error-copy" role="alert">{error} The draft remains unchanged.</p>}
    </section>
  );
}
