import { useState } from 'react';
import { routeForPath } from '../catalog.ts';
import { EvidencePanel } from '../components/EvidencePanel.tsx';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';
import type { ReleaseRecord, UniverseCommand } from '../types.ts';

export default function ReleaseDockPage() {
  const route = routeForPath('/release');
  const snapshot = useUniverseStore((state) => state.snapshot);
  const connection = useUniverseStore((state) => state.connection);
  const execute = useUniverseStore((state) => state.executeCommand);
  const releases = (Array.isArray(snapshot?.releases) ? snapshot.releases : []) as ReleaseRecord[];
  const record = releases[0] ?? null;
  const [approvalId, setApprovalId] = useState(record?.approval_id ?? '');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [failed, setFailed] = useState(false);
  const isLive = record?.state === 'live';
  const canPromote = connection === 'online' && record?.state === 'awaiting_owner' && Boolean(snapshot?.viewer && approvalId.trim());

  const promote = async () => {
    if (!record || !snapshot?.viewer || !canPromote) return;
    const commandId = `cmd_release_promote_${record.id}_${record.version}`;
    const command: UniverseCommand = {
      command_id: commandId,
      command_type: 'release.promote',
      realm_id: record.realm_id,
      actor_id: snapshot.viewer.actor_id,
      stream_type: 'release',
      stream_id: record.id,
      expected_version: record.version,
      payload: { release_id: record.id, target: 'production' },
      authorization: { allowed: false, reason: 'server must validate the bound approval and all release gates', scopes: [], owner_gate: 'required' },
      provenance: { source: 'atlas_release_dock', evidence: [`release:${record.id}`, `version:${record.version}`], confidence: 1, signature: null },
      causation_id: commandId,
      correlation_id: commandId,
      simulation: false,
      approval_id: approvalId.trim(),
    };
    setPending(true);
    setFailed(false);
    setMessage('');
    try {
      await execute(command);
      setMessage('Promotion command acknowledged. Refreshing durable provider state.');
    } catch (cause) {
      setFailed(true);
      setMessage(`${(cause as Error).message} The prior public version remains authoritative.`);
    } finally {
      setPending(false);
    }
  };

  const gates = record?.gates && typeof record.gates === 'object' ? record.gates as Record<string, unknown> : null;
  const preview = record?.visibility === 'private' ? record as unknown as Record<string, unknown> : null;
  return (
    <UniversePage route={route} eyebrow="Release Dock" title="Verified Promotion & Rollback" description="Private preview, verification, staging, owner approval, provider publish, prior durable version, and rollback are separate states. Failed publish never appears live.">
      <UniverseStatusBoundary>
        {!record && <section className="production-unavailable universe-panel"><p className="universe-eyebrow">Release record unavailable</p><h2>No release candidate was reported</h2><p>No preview, staged bundle, approval, provider deployment, public URL, or rollback result is invented.</p></section>}
        <div className="release-state-machine" role="list" aria-label="Release lifecycle">
          {['draft', 'verified', 'staged', 'awaiting_owner', 'publishing', 'live', 'failed', 'rolled_back'].map((state) => <div role="listitem" key={state} className={record?.state === state ? `is-current is-${state}` : ''}><span />{state.replaceAll('_', ' ')}</div>)}
        </div>
        <div className="production-grid production-grid--release">
          <EvidencePanel title="Private preview" eyebrow="Never auto-promoted" record={preview} fields={[{ label: 'Visibility', path: 'visibility' }, { label: 'Preview URL', path: 'preview_url' }, { label: 'Artifact', path: 'artifact_id' }, { label: 'Revision', path: 'version_name' }, { label: 'Observed', path: 'updated_at' }]} />
          <EvidencePanel title="Verification gates" eyebrow="Required evidence bundle" record={gates} fields={[{ label: 'Provenance', path: 'provenance' }, { label: 'Rights', path: 'rights' }, { label: 'Security', path: 'security' }, { label: 'Performance', path: 'performance' }, { label: 'Accessibility', path: 'accessibility' }, { label: 'Product', path: 'product' }]} />
          <EvidencePanel title="Owner approval" eyebrow="Bound actor · action · realm · command" record={record as unknown as Record<string, unknown> | null} fields={[{ label: 'State', path: 'state' }, { label: 'Approval', path: 'approval_id' }, { label: 'Actor', path: 'actor_id' }, { label: 'Cost estimate', path: 'estimated_cost' }]}>
            <label className="production-instruction">Existing approval id<input value={approvalId} onChange={(event) => setApprovalId(event.target.value)} placeholder="Bound approval id" /></label>
            <button type="button" className="universe-button--primary" disabled={!canPromote || pending} onClick={() => void promote()}>{pending ? 'Publishing…' : 'Promote to durable release'}</button>
            {message && <p className={failed ? 'universe-error-copy' : 'universe-success-copy'} role="status">{message}</p>}
          </EvidencePanel>
          <EvidencePanel title="Durable release" eyebrow="Provider result" record={isLive ? record as unknown as Record<string, unknown> : null} fields={[{ label: 'State', path: 'state' }, { label: 'Provider', path: 'provider' }, { label: 'Deployment id', path: 'deployment_id' }, { label: 'Current public URL', path: 'public_url' }, { label: 'Actual cost', path: 'actual_cost' }, { label: 'Deployment logs', path: 'deployment_logs' }]} />
          <EvidencePanel title="Previous version" eyebrow="Rollback source" record={record as unknown as Record<string, unknown> | null} fields={[{ label: 'Version', path: 'previous_version' }, { label: 'Deployment', path: 'previous_deployment_id' }, { label: 'Public URL', path: 'previous_public_url' }, { label: 'Hash', path: 'previous_hash' }]} />
          <EvidencePanel title="Rollback" eyebrow="Durable recovery evidence" record={record?.rollback && typeof record.rollback === 'object' ? record.rollback as Record<string, unknown> : null} fields={[{ label: 'State', path: 'status' }, { label: 'Reason', path: 'reason' }, { label: 'Restored version', path: 'restored_version' }, { label: 'Provider result', path: 'provider_result' }, { label: 'Recovery instruction', path: 'recovery_instruction' }]}><button type="button" disabled title="Rollback API is not reported by this universe service">Rollback to previous version</button></EvidencePanel>
        </div>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
