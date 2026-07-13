import { BrainCircuit, GitCommitHorizontal, MessageSquare, Server } from "lucide-react";
import { type FC, useEffect, useMemo, useState } from 'react';

// --- Type Definitions ---

type Session = {
  id: string;
  title?: string;
  model?: string;
  message_count?: number;
  created_at?: string;
};

type ApiConfig = {
  model: string;
  provider: string;
  fusion_mode?: string;
};

type ModelInfo = {
  model: string;
  provider: string;
  effective_context_length: number;
};

// --- Helper Functions ---

const timeAgo = (dateString?: string): string => {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  let interval = seconds / 31536000;
  if (interval > 1) return Math.floor(interval) + 'y ago';
  interval = seconds / 2592000;
  if (interval > 1) return Math.floor(interval) + 'mo ago';
  interval = seconds / 86400;
  if (interval > 1) return Math.floor(interval) + 'd ago';
  interval = seconds / 3600;
  if (interval > 1) return Math.floor(interval) + 'h ago';
  interval = seconds / 60;
  if (interval > 1) return Math.floor(interval) + 'm ago';
  return Math.floor(seconds) + 's ago';
};

const getToken = (): string => {
    return (window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string;
}

// --- Sub-components ---

const ConfigDisplay: FC<{ config: ApiConfig | null; modelInfo: ModelInfo | null }> = ({ config, modelInfo }) => (
  <div className="bg-zinc-900/50 rounded-lg p-3 text-xs text-zinc-400">
    <h3 className="font-semibold text-cyan-400 mb-2 text-sm">MUSE Configuration</h3>
    {config ? (
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        <div className="flex items-center gap-1.5"><Server size={14} className="text-zinc-500" /> Provider</div>
        <div className="text-zinc-200 truncate">{config.provider}</div>
        <div className="flex items-center gap-1.5"><BrainCircuit size={14} className="text-zinc-500" /> Model</div>
        <div className="text-zinc-200 truncate">{config.model}</div>
        {modelInfo && (
            <>
                <div className="flex items-center gap-1.5"><GitCommitHorizontal size={14} className="text-zinc-500" /> Context</div>
                <div className="text-zinc-200">{modelInfo.effective_context_length.toLocaleString()}</div>
            </>
        )}
      </div>
    ) : (
      <div>Loading config...</div>
    )}
  </div>
);

const SessionCard: FC<{ session: Session }> = ({ session }) => (
  <div className="bg-zinc-900/50 rounded-lg p-2.5 text-xs hover:bg-zinc-800/50 transition-colors duration-200">
    <div className="flex justify-between items-start">
        <p className="text-zinc-200 font-medium mb-1.5 break-all">{session.title || 'Untitled Session'}</p>
        <span className="text-zinc-500 flex-shrink-0 ml-2">{timeAgo(session.created_at)}</span>
    </div>
    <div className="flex items-center text-zinc-400 gap-4">
      <div className="flex items-center gap-1.5" title="Model">
        <BrainCircuit size={12} />
        <span>{session.model || 'unknown'}</span>
      </div>
      <div className="flex items-center gap-1.5" title="Messages">
        <MessageSquare size={12} />
        <span>{session.message_count || 0}</span>
      </div>
    </div>
  </div>
);


const KnowledgeGraph: FC<{ sessions: Session[] }> = ({ sessions }) => {
    const nodes = useMemo(() => {
        const center = { x: 150, y: 100 };
        const radius = 80;
        return sessions.slice(0, 7).map((session, i) => {
            const angle = (i / Math.min(sessions.length, 7)) * 2 * Math.PI;
            return {
                id: session.id,
                x: center.x + radius * Math.cos(angle),
                y: center.y + radius * Math.sin(angle),
                color: i % 2 === 0 ? 'cyan' : 'emerald',
            };
        });
    }, [sessions]);

    return (
        <div className="aspect-[3/2] w-full">
            <svg viewBox="0 0 300 200" className="w-full h-full">
                <defs>
                    <radialGradient id="grad-center">
                        <stop offset="0%" stopColor="rgba(0,255,255,0.3)" />
                        <stop offset="100%" stopColor="rgba(0,255,255,0)" />
                    </radialGradient>
                    <radialGradient id="grad-cyan-node">
                        <stop offset="0%" stopColor="rgba(34,211,238,0.5)" />
                        <stop offset="100%" stopColor="rgba(34,211,238,0)" />
                    </radialGradient>
                     <radialGradient id="grad-emerald-node">
                        <stop offset="0%" stopColor="rgba(52,211,153,0.5)" />
                        <stop offset="100%" stopColor="rgba(52,211,153,0)" />
                    </radialGradient>
                </defs>

                {/* Center Node */}
                <circle cx="150" cy="100" r="20" fill="url(#grad-center)" />
                <circle cx="150" cy="100" r="8" className="fill-cyan-400" />
                <text x="150" y="104" textAnchor="middle" fontSize="9" className="fill-white font-bold tracking-widest">MUSE</text>


                {/* Session Nodes and Lines */}
                {nodes.map(node => (
                    <g key={node.id}>
                        <line x1="150" y1="100" x2={node.x} y2={node.y} className="stroke-zinc-700/50" strokeWidth="1" />
                        <circle cx={node.x} cy={node.y} r="12" fill={node.color === 'cyan' ? 'url(#grad-cyan-node)' : 'url(#grad-emerald-node)'} />
                        <circle cx={node.x} cy={node.y} r="4" className={node.color === 'cyan' ? 'fill-cyan-400' : 'fill-emerald-400'} />
                    </g>
                ))}
            </svg>
        </div>
    );
};


// --- Main Component ---

const AgentMemoryPanel: FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = getToken();
        if (!token) {
            // This might be expected if the user is not logged in.
            // Silently fail or set a specific state.
            console.warn("No session token found for AgentMemoryPanel.");
            return;
        }

        const headers = { Authorization: `Bearer ${token}` };

        const [sessionsRes, configRes, modelInfoRes] = await Promise.all([
          fetch('/api/sessions', { headers }),
          fetch('/api/config', { headers }),
          fetch('/api/model/info', { headers }),
        ]);

        if (!sessionsRes.ok) throw new Error(`Failed to fetch sessions: ${sessionsRes.statusText}`);
        if (!configRes.ok) throw new Error(`Failed to fetch config: ${configRes.statusText}`);
        if (!modelInfoRes.ok) throw new Error(`Failed to fetch model info: ${modelInfoRes.statusText}`);

        const sessionsData = await sessionsRes.json();
        const configData = await configRes.json();
        const modelInfoData = await modelInfoRes.json();

        setSessions(sessionsData);
        setConfig(configData);
        setModelInfo(modelInfoData);

      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unknown error occurred.');
        console.error("Error fetching agent memory data:", err);
      }
    };

    fetchData();
    const intervalId = setInterval(fetchData, 30000); // Refresh every 30 seconds

    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="bg-zinc-950 text-white w-full h-full p-4 flex flex-col gap-4 overflow-y-auto">
      <h2 className="text-lg font-bold text-zinc-200">Agent Memory</h2>

      {error && <div className="bg-red-900/50 border border-red-700 text-red-300 text-xs rounded-md p-2">{error}</div>}

      <ConfigDisplay config={config} modelInfo={modelInfo} />

      <KnowledgeGraph sessions={sessions} />

      <div>
        <h3 className="font-semibold text-emerald-400 mb-2 text-sm">Recent Activity</h3>
        <div className="flex flex-col gap-2">
            {sessions.length > 0 ? (
                sessions.slice(0, 5).map(s => <SessionCard key={s.id} session={s} />)
            ) : (
                <div className="text-zinc-500 text-xs text-center py-4">No recent sessions found.</div>
            )}
        </div>
      </div>
    </div>
  );
};

export default AgentMemoryPanel;
