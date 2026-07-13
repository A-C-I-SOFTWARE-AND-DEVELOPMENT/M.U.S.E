import { Link } from 'react-router-dom';
import { routeForPath } from '../catalog.ts';
import { EvidencePanel } from '../components/EvidencePanel.tsx';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';

export default function FabricationPage() {
  const route = routeForPath('/fabrication');
  const snapshot = useUniverseStore((state) => state.snapshot);
  const sessions = Array.isArray(snapshot?.fabrication_sessions) ? snapshot.fabrication_sessions : [];
  const leases = Array.isArray(snapshot?.workspace_leases) ? snapshot.workspace_leases : [];
  const record = (sessions[0] ?? leases[0] ?? null) as Record<string, unknown> | null;
  const verification = record?.verification && typeof record.verification === 'object'
    ? (record.verification as Record<string, unknown>)
    : null;
  const canEdit = Boolean(record && record.status === 'active');
  return (
    <UniversePage route={route} eyebrow="Fabrication Foundry" title="Live Source Fabrication" description="Every visual selection resolves to bounded source, revision, property path, diff, gate evidence, checkpoint, and rollback. Preview is never public release." actions={<Link className="universe-button" to="/release">Release Dock</Link>}>
      <UniverseStatusBoundary>
        {!record && <section className="production-unavailable universe-panel"><p className="universe-eyebrow">Production record unavailable</p><h2>No Fabrication session or workspace lease was reported</h2><p>The complete cockpit remains visible below as an evidence contract. No sample project, source path, preview URL, or passing gate is fabricated.</p></section>}
        <div className="production-grid production-grid--fabrication">
          <EvidencePanel title="Source map" eyebrow="Selected element → repository source" record={record} fields={[{ label: 'Component id', path: 'source_ref.component_id' }, { label: 'File', path: 'source_ref.file' }, { label: 'Line', path: 'source_ref.line' }, { label: 'Property path', path: 'source_ref.property_path' }, { label: 'Revision', path: 'source_ref.revision' }, { label: 'Lease', path: 'id' }]}>
            <label className="production-instruction">Edit instruction<textarea rows={3} disabled={!canEdit} placeholder={canEdit ? 'Describe a bounded source change' : 'Requires an active authoritative Fabrication session'} /></label>
          </EvidencePanel>
          <EvidencePanel title="Live preview" eyebrow="Signed private workspace" record={record} fields={[{ label: 'Visibility', path: 'visibility' }, { label: 'Preview URL', path: 'preview_url' }, { label: 'Health', path: 'preview_health' }, { label: 'HMR', path: 'hmr_status' }, { label: 'Expires', path: 'expires_at' }, { label: 'Workspace', path: 'workspace_path' }]} />
          <EvidencePanel title="Unified diff" eyebrow="Isolated source change" record={record} fields={[{ label: 'Files changed', path: 'diff.files' }, { label: 'Insertions', path: 'diff.insertions' }, { label: 'Deletions', path: 'diff.deletions' }, { label: 'Revision', path: 'diff.revision' }]}><pre className="universe-evidence-block">{typeof record?.unified_diff === 'string' ? record.unified_diff : 'No diff reported.'}</pre></EvidencePanel>
          <EvidencePanel title="Verification" eyebrow="Captured gate exit codes" record={verification} fields={[{ label: 'Affected tests', path: 'tests' }, { label: 'Lint', path: 'lint' }, { label: 'Type', path: 'typecheck' }, { label: 'Accessibility', path: 'accessibility' }, { label: 'Performance', path: 'performance' }, { label: 'Required gates', path: 'required_passed' }]} />
          <EvidencePanel title="Checkpoint" eyebrow="Pre-apply recovery boundary" record={record} fields={[{ label: 'Checkpoint id', path: 'checkpoint.id' }, { label: 'Revision', path: 'checkpoint.revision' }, { label: 'Created', path: 'checkpoint.created_at' }, { label: 'Status', path: 'checkpoint.status' }]} />
          <EvidencePanel title="Apply · Rollback · Stage release" eyebrow="Explicit lifecycle" record={record} fields={[{ label: 'Apply state', path: 'apply_status' }, { label: 'Rollback state', path: 'rollback.status' }, { label: 'Rollback evidence', path: 'rollback.evidence' }, { label: 'Release stage', path: 'release_stage' }]}>
            <div className="universe-action-row"><button type="button" disabled={!canEdit || verification?.required_passed !== true}>Apply verified change</button><button type="button" disabled={!record?.checkpoint}>Rollback checkpoint</button><Link className="universe-button" to="/release">Stage release</Link></div>
          </EvidencePanel>
        </div>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
