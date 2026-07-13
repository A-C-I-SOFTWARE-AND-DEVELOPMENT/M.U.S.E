import { useState } from 'react';
import { Link } from 'react-router-dom';
import { routeForPath } from '../catalog.ts';
import { CivilizationPanel } from '../components/CivilizationPanel.tsx';
import { EvidencePanel } from '../components/EvidencePanel.tsx';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';
import type { Civilization, UniverseCommand, UniverseEntity } from '../types.ts';

const WORKFLOWS = {
  'civilization.create': { stream: 'civilization', hint: 'id, name, charter, governance' },
  'membership.invite': { stream: 'membership', hint: 'id, civilization_id, player_id, roles' },
  'membership.accept': { stream: 'membership', hint: 'id' },
  'governance.propose': { stream: 'proposal', hint: 'id, civilization_id, title, action, deadline_utc' },
  'governance.vote': { stream: 'proposal', hint: 'proposal_id, choice' },
  'civilization.diplomacy': { stream: 'treaty', hint: 'id, civilization_id, counterpart_id, state' },
  'moderation.report': { stream: 'moderation_case', hint: 'id, target_id, reason, evidence' },
  'moderation.block': { stream: 'block', hint: 'id, target_id, reason' },
  'operational_ledger.record': { stream: 'operational_ledger', hint: 'id, civilization_id, kind, amount, evidence' },
  'creator_ledger.record': { stream: 'creator_ledger', hint: 'id, civilization_id, kind, amount, evidence' },
} as const;

type Workflow = keyof typeof WORKFLOWS;

export default function CivilizationsPage() {
  const route = routeForPath('/civilizations');
  const snapshot = useUniverseStore((state) => state.snapshot);
  const connection = useUniverseStore((state) => state.connection);
  const cursor = useUniverseStore((state) => state.cursor);
  const refresh = useUniverseStore((state) => state.refresh);
  const execute = useUniverseStore((state) => state.executeCommand);
  const civilizations = (Array.isArray(snapshot?.civilizations) ? snapshot.civilizations : []) as Civilization[];
  const memberships = (Array.isArray(snapshot?.memberships) ? snapshot.memberships : []) as UniverseEntity[];
  const proposals = (Array.isArray(snapshot?.proposals) ? snapshot.proposals : []) as UniverseEntity[];
  const viewer = snapshot?.viewer ?? null;
  const player = (Array.isArray(snapshot?.players) ? snapshot.players : []).find((entry) => entry.id === viewer?.actor_id) ?? null;
  const [workflow, setWorkflow] = useState<Workflow>('civilization.create');
  const [streamId, setStreamId] = useState('');
  const [expectedVersion, setExpectedVersion] = useState(0);
  const [payload, setPayload] = useState('{}');
  const [approvalId, setApprovalId] = useState('');
  const [operationState, setOperationState] = useState<'idle' | 'pending' | 'complete' | 'failed'>('idle');
  const [operationMessage, setOperationMessage] = useState('');

  const submit = async () => {
    if (!viewer || !streamId.trim()) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(payload) as Record<string, unknown>;
    } catch {
      setOperationState('failed');
      setOperationMessage('Payload must be a JSON object.');
      return;
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setOperationState('failed');
      setOperationMessage('Payload must be a JSON object.');
      return;
    }
    const commandId = `cmd_ui_${workflow.replaceAll('.', '_')}_${streamId}_${expectedVersion}`;
    const command: UniverseCommand = {
      command_id: commandId,
      command_type: workflow,
      realm_id: snapshot?.realm_id ?? 'rlm_local',
      actor_id: viewer.actor_id,
      stream_type: WORKFLOWS[workflow].stream,
      stream_id: streamId.trim(),
      expected_version: expectedVersion,
      payload: parsed,
      authorization: { allowed: false, reason: 'server must derive active membership and scopes', scopes: [], owner_gate: 'server-determined' },
      provenance: { source: 'atlas_civilization_console', evidence: [`cursor:${cursor}`], confidence: 1, signature: null },
      causation_id: commandId,
      correlation_id: commandId,
      simulation: false,
      ...(approvalId.trim() ? { approval_id: approvalId.trim() } : {}),
    };
    setOperationState('pending');
    setOperationMessage('');
    try {
      await execute(command);
      setOperationState('complete');
      setOperationMessage('Command acknowledged by the authoritative service.');
    } catch (cause) {
      setOperationState('failed');
      setOperationMessage((cause as Error).message);
    }
  };

  const treaties = (Array.isArray(snapshot?.treaties) ? snapshot.treaties : []) as UniverseEntity[];
  const operationalLedger = (Array.isArray(snapshot?.operational_ledgers) ? snapshot.operational_ledgers : []) as UniverseEntity[];
  const creatorLedger = (Array.isArray(snapshot?.creator_ledgers) ? snapshot.creator_ledgers : []) as UniverseEntity[];
  const moderation = [
    ...((Array.isArray(snapshot?.moderation_cases) ? snapshot.moderation_cases : []) as UniverseEntity[]),
    ...((Array.isArray(snapshot?.blocks) ? snapshot.blocks : []) as UniverseEntity[]),
  ];
  const assets = (Array.isArray(snapshot?.assets) ? snapshot.assets : []) as UniverseEntity[];

  return (
    <UniversePage route={route} eyebrow="Relay Embassy" title="Players & Civilizations" description="Realm identity, membership, co-op roles, governance, shared assets, diplomacy, ledgers, and moderation remain separate from sovereign Federation peer identity." actions={<Link className="universe-button" to="/federation">Federation identity</Link>}>
      <UniverseStatusBoundary>
        <section className="civilization-profile universe-panel">
          <div><p className="universe-eyebrow">Local profile · server-derived authority only</p><h2>{player?.name ?? viewer?.display_name ?? viewer?.actor_id ?? 'Viewer not reported'}</h2><p>A profile field cannot claim captain, owner, moderator, release, or tool authority. Active membership scopes are resolved server-side.</p></div>
          <dl className="universe-definition-grid"><div><dt>Actor</dt><dd>{viewer?.actor_id ?? 'Not reported'}</dd></div><div><dt>Realm role</dt><dd>{viewer?.realm_role ?? 'Not reported'}</dd></div><div><dt>Scopes</dt><dd>{viewer?.scopes.join(', ') || 'Not reported'}</dd></div><div><dt>Reconnect cursor</dt><dd>{cursor}</dd></div></dl>
          <button type="button" onClick={() => void refresh()}>Reconnect from cursor {cursor}</button>
        </section>

        <div className="civilization-grid">
          {civilizations.length > 0 ? civilizations.map((civilization) => <CivilizationPanel key={civilization.id} civilization={civilization} memberships={memberships} proposals={proposals} />) : <div className="universe-panel universe-empty-copy"><p className="universe-eyebrow">Civilizations</p><h2>No civilization projections reported</h2><p>Create or join through the bounded command console. No demo civilization is inserted.</p></div>}
        </div>

        <section className="civilization-console universe-panel">
          <header><div><p className="universe-eyebrow">Bounded co-op command console</p><h2>Create · join · invite · govern · moderate</h2></div><span className={`universe-chip universe-chip--${operationState}`}>{operationState}</span></header>
          <div className="civilization-console__form">
            <label>Workflow<select value={workflow} onChange={(event) => { setWorkflow(event.target.value as Workflow); setOperationState('idle'); }}>{Object.keys(WORKFLOWS).map((entry) => <option key={entry} value={entry}>{entry}</option>)}</select><small>Required payload: {WORKFLOWS[workflow].hint}</small></label>
            <label>Stream id<input value={streamId} onChange={(event) => setStreamId(event.target.value)} placeholder="Stable entity id" /></label>
            <label>Expected version<input type="number" min={0} value={expectedVersion} onChange={(event) => setExpectedVersion(Math.max(0, Number(event.target.value)))} /></label>
            <label>Owner approval id<input value={approvalId} onChange={(event) => setApprovalId(event.target.value)} placeholder="Only when already granted" /></label>
            <label className="civilization-console__payload">Payload JSON<textarea value={payload} onChange={(event) => setPayload(event.target.value)} rows={7} spellCheck={false} /></label>
          </div>
          <button type="button" className="universe-button--primary" disabled={connection !== 'online' || !viewer || !streamId.trim() || operationState === 'pending'} onClick={() => void submit()}>{operationState === 'pending' ? 'Awaiting authoritative response…' : 'Submit bounded command'}</button>
          {operationMessage && <p className={operationState === 'failed' ? 'universe-error-copy' : 'universe-success-copy'} role="status">{operationMessage}</p>}
        </section>

        <div className="civilization-evidence-grid">
          <EvidencePanel title="Shared assets" eyebrow="Provenance and rights" record={assets[0] ?? null} fields={[{ label: 'Records', path: 'id' }, { label: 'License', path: 'license' }, { label: 'Verification', path: 'verification' }, { label: 'Moderation', path: 'moderation_state' }]} />
          <EvidencePanel title="Diplomacy" eyebrow="Treaties" record={treaties[0] ?? null} fields={[{ label: 'Treaty', path: 'id' }, { label: 'State', path: 'state' }, { label: 'Counterpart', path: 'counterpart_id' }, { label: 'Observed', path: 'updated_at' }]} />
          <EvidencePanel title="Operational ledger" eyebrow="Execution economy" record={operationalLedger[0] ?? null} fields={[{ label: 'Entry', path: 'id' }, { label: 'Kind', path: 'kind' }, { label: 'Amount', path: 'amount' }, { label: 'Evidence', path: 'evidence' }]} />
          <EvidencePanel title="Creator ledger" eyebrow="Creator economy" record={creatorLedger[0] ?? null} fields={[{ label: 'Entry', path: 'id' }, { label: 'Kind', path: 'kind' }, { label: 'Amount', path: 'amount' }, { label: 'Refund', path: 'refund' }]} />
          <EvidencePanel title="Moderation & blocks" eyebrow="Safety" record={moderation[0] ?? null} fields={[{ label: 'Case', path: 'id' }, { label: 'Target', path: 'target_id' }, { label: 'State', path: 'status' }, { label: 'Evidence', path: 'evidence' }]} />
        </div>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
