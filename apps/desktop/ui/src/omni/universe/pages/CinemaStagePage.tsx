import { Link } from 'react-router-dom';
import { routeForPath } from '../catalog.ts';
import { EvidencePanel } from '../components/EvidencePanel.tsx';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';

export default function CinemaStagePage() {
  const route = routeForPath('/cinema');
  const snapshot = useUniverseStore((state) => state.snapshot);
  const shots = Array.isArray(snapshot?.cinematic_shots) ? snapshot.cinematic_shots : [];
  const record = (shots[0] ?? null) as Record<string, unknown> | null;
  const qc = record?.qc && typeof record.qc === 'object' ? (record.qc as Record<string, unknown>) : null;
  const deliverables = record?.deliverables && typeof record.deliverables === 'object'
    ? (record.deliverables as Record<string, unknown>)
    : null;
  const masterReady = qc?.passed === true
    && Array.isArray(record?.camera_ids)
    && record.camera_ids.length === 2
    && typeof record?.settings_hash === 'string'
    && Boolean(deliverables?.checksums);
  return (
    <UniversePage route={route} eyebrow="Cinema Array" title="Native-Stereo Cinema Stage" description="Two physical metric cameras, deterministic eye/frame manifests, comfort and alignment QC, ACES deliverables, rights, archives, and explicit external certification gates." actions={<Link className="universe-button" to="/release">Release Dock</Link>}>
      <UniverseStatusBoundary>
        {!record && <section className="production-unavailable universe-panel"><p className="universe-eyebrow">Cinema production unavailable</p><h2>No stereo shot manifest was reported</h2><p>No flat-card conversion, render completion, certification, or passing QC is implied. Required production evidence is shown below as unavailable.</p></section>}
        <section className="cinema-shot universe-panel">
          <header><div><p className="universe-eyebrow">Screenplay · breakdown · storyboard · previs · techvis</p><h2>{typeof record?.name === 'string' ? record.name : typeof record?.id === 'string' ? record.id : 'No shot selected'}</h2></div><span className={`universe-chip universe-chip--${masterReady ? 'live' : 'unavailable'}`}>{masterReady ? 'Stereo master evidence ready' : 'Master not verified'}</span></header>
          <div className="cinema-safe-frames" aria-label="Composition overlays"><div className="cinema-frame cinema-frame--190"><span>1.90 safe composition</span><div className="cinema-frame cinema-frame--143"><span>1.43 safe composition</span></div></div></div>
        </section>
        <div className="production-grid">
          <EvidencePanel title="Physical camera rig" eyebrow="Two cameras · one metric scene" record={record} fields={[{ label: 'Camera ids', path: 'camera_ids' }, { label: 'Interaxial', path: 'interaxial_m' }, { label: 'Convergence', path: 'convergence_m' }, { label: 'Zero parallax', path: 'zero_parallax_m' }, { label: 'Focal length', path: 'focal_length_mm' }, { label: 'Sensor width', path: 'sensor_width_mm' }, { label: 'Near / far clips', path: 'clips' }, { label: 'Display geometry', path: 'display_geometry' }]} />
          <EvidencePanel title="Depth script & lenses" eyebrow="Comfort by shot" record={record} fields={[{ label: 'Depth budget', path: 'depth_budget' }, { label: 'Focal distance', path: 'focal_distance_m' }, { label: 'Aperture', path: 'aperture' }, { label: 'Transparency', path: 'handling.transparency' }, { label: 'Volumetrics', path: 'handling.volumetrics' }, { label: 'Motion blur', path: 'handling.motion_blur' }, { label: 'Editorial transition', path: 'editorial_transition' }]} />
          <EvidencePanel title="Performance & sound" eyebrow="Characters · dialogue · score · SFX" record={record} fields={[{ label: 'Performance', path: 'performance' }, { label: 'Dialogue', path: 'dialogue' }, { label: 'Score', path: 'score' }, { label: 'SFX', path: 'sfx' }, { label: 'Spatial mix', path: 'spatial_mix' }, { label: 'Locations / sets', path: 'locations' }]} />
          <EvidencePanel title="Render queue & retry" eyebrow="Deterministic eye/frame records" record={record} fields={[{ label: 'Renderer / version', path: 'renderer' }, { label: 'Scene revision', path: 'scene_revision' }, { label: 'Seed', path: 'seed' }, { label: 'Settings hash', path: 'settings_hash' }, { label: 'Left / right frames', path: 'frame_counts' }, { label: 'Attempt', path: 'attempt' }, { label: 'Error', path: 'error' }]} />
          <EvidencePanel title="Stereo QC" eyebrow="Alignment · disparity · comfort" record={qc} fields={[{ label: 'Horizontal disparity', path: 'horizontal_disparity' }, { label: 'Vertical alignment', path: 'vertical_alignment' }, { label: 'Occlusion conflicts', path: 'occlusion_conflicts' }, { label: 'Crosstalk risk', path: 'crosstalk_risk' }, { label: 'Floating windows', path: 'floating_windows' }, { label: 'Temporal sync', path: 'temporal_sync' }, { label: 'Comfort', path: 'comfort' }, { label: 'Passed', path: 'passed' }]} />
          <EvidencePanel title="Deliverables & archive" eyebrow="ACES 2 · checksums · rights" record={record} fields={[{ label: 'OpenEXR', path: 'deliverables.openexr' }, { label: 'ACES 2 config', path: 'deliverables.aces' }, { label: 'Editorial conform', path: 'deliverables.conform' }, { label: 'QC report', path: 'deliverables.qc_report' }, { label: 'Checksum inventory', path: 'deliverables.checksums' }, { label: 'Rights', path: 'rights_status' }, { label: 'Archive', path: 'archive_manifest' }, { label: 'IMAX external gate', path: 'imax_certified' }]}><p className="universe-inline-warning">IMAX certification is always an external gate; the UI never infers or self-awards it.</p></EvidencePanel>
        </div>
      </UniverseStatusBoundary>
    </UniversePage>
  );
}
