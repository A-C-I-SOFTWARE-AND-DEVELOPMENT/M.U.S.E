import React from 'react';
import { createRoot } from 'react-dom/client';
import { ShieldCheck, Cpu, GitBranch, ClipboardCheck, AlertTriangle, RadioTower } from 'lucide-react';
import { ownerBrief, jobs, gates, modelRoutes, integrations } from './lib/seed.js';
import './styles.css';

function Badge({ children, tone = 'neutral' }) { return <span className={`badge ${tone}`}>{children}</span>; }

function Card({ title, icon, children }) { return <section className="card"><div className="card-title">{icon}{title}</div>{children}</section>; }

function App() {
  return <main className="shell">
    <header className="hero">
      <div>
        <p className="eyebrow">ACI Hermes / JARVIS Prime</p>
        <h1>Command Cockpit</h1>
        <p className="sub">Base44 is the cockpit. Hermes remains the backend source of truth.</p>
      </div>
      <Badge tone="good">audit-ready</Badge>
    </header>

    <Card title="Owner Brief" icon={<ShieldCheck size={20}/>}> 
      <p><strong>Mission:</strong> {ownerBrief.mission}</p>
      <p><strong>Canonical repo:</strong> {ownerBrief.canonicalRepo}</p>
      <p><strong>Commit:</strong> <code>{ownerBrief.commit}</code></p>
      <p><strong>Next action:</strong> {ownerBrief.nextAction}</p>
    </Card>

    <div className="grid two">
      <Card title="Work Packets" icon={<ClipboardCheck size={20}/>}> 
        <div className="list">{jobs.map(j => <div className="row" key={j.id}><div><strong>{j.id}</strong><span>{j.title}</span></div><Badge tone={j.ownerGate ? 'warn':'good'}>{j.risk} · {j.status}</Badge></div>)}</div>
      </Card>
      <Card title="Integration Status" icon={<RadioTower size={20}/>}> 
        <div className="list">{integrations.map(i => <div className="row" key={i.name}><strong>{i.name}</strong><span>{i.state}</span></div>)}</div>
      </Card>
    </div>

    <Card title="Verification Gates" icon={<GitBranch size={20}/>}> 
      <div className="gate-grid">{gates.map(([name,status,reason]) => <div className="gate" key={name}><Badge tone={status==='pass'?'good':'warn'}>{status}</Badge><strong>{name}</strong><p>{reason}</p></div>)}</div>
    </Card>

    <Card title="Model Router" icon={<Cpu size={20}/>}> 
      <table><thead><tr><th>Lane</th><th>Model</th><th>Reason</th></tr></thead><tbody>{modelRoutes.map(r => <tr key={r.lane}><td>{r.lane}</td><td>{r.model}</td><td>{r.reason}</td></tr>)}</tbody></table>
    </Card>

    <Card title="Safety Boundary" icon={<AlertTriangle size={20}/>}> 
      <p>Base44 may request actions, but Hermes must decide, validate WorkPackets, enforce owner authorization, and record rollback/test evidence.</p>
    </Card>
  </main>;
}

createRoot(document.getElementById('root')).render(<App/>);
