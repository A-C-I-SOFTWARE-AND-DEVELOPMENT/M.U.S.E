/**
 * MuseChatOverlay — Identity + control layer that sits on top of the
 * xterm.js PTY terminal in ChatPage.
 *
 * Features:
 * - MUSE branding badge (top-left of terminal area)
 * - Live model indicator with context length
 * - Gateway status pulse
 * - "Chat controls everything" hint strip
 * - Quick action buttons that inject commands into the PTY
 * - PTY output interceptor that listens for dashboard navigation
 *   commands (e.g. when MUSE says "Opening sessions..." the overlay
 *   navigates automatically)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CircleDot,
  Cpu,
  Zap,
  Clock,
  Package,
  Terminal,
  RotateCw,
  Settings,
  ArrowRight,
} from "lucide-react";
import { ModelPickerDialog } from "@/components/ModelPickerDialog";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface MuseChatOverlayProps {
  /** The xterm.js terminal element container */
  hostRef: React.RefObject<HTMLDivElement | null>;
  /** The WebSocket ref so we can inject commands */
  wsRef: React.RefObject<WebSocket | null>;
}

interface StatusData {
  gateway_running: boolean;
  active_sessions: number;
  version?: string;
}

interface ModelData {
  model: string;
  provider: string;
  effective_context_length?: number;
}

/** Quick actions that inject slash commands into the PTY */
const QUICK_ACTIONS = [
  { label: "Status", cmd: "/status", icon: CircleDot },
  { label: "Models", cmd: "/model", icon: Cpu },
  { label: "Skills", cmd: "/skills", icon: Package },
  { label: "Cron", cmd: "/cron", icon: Clock },
  { label: "Restart", cmd: "/restart", icon: RotateCw },
  { label: "Config", cmd: "/config", icon: Settings },
];

/** Map of phrases the MUSE agent outputs that trigger dashboard navigation */
const NAVIGATION_TRIGGERS: Record<string, string> = {
  "navigate to sessions": "/sessions",
  "navigate to models": "/models",
  "navigate to logs": "/logs",
  "navigate to cron": "/cron",
  "navigate to skills": "/skills",
  "navigate to plugins": "/plugins",
  "navigate to config": "/config",
  "navigate to profiles": "/profiles",
  "navigate to studio": "/studio",
  "navigate to musehq": "/musehq",
  "navigate to nexus": "/nexus",
  "opening sessions": "/sessions",
  "opening models": "/models",
  "opening logs": "/logs",
  "opening cron": "/cron",
  "opening studio": "/studio",
};

export function MuseChatOverlay({ wsRef }: MuseChatOverlayProps) {
  const navigate = useNavigate();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [model, setModel] = useState<ModelData | null>(null);
  const [showHint, setShowHint] = useState(true);
  const [actionFlash, setActionFlash] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const navBufferRef = useRef<string>("");

  const refreshModel = useCallback(async () => {
    try {
      const m = await api.getModelInfo();
      setModel(m);
    } catch {
      /* best effort */
    }
  }, []);

  // ── Fetch status + model info ──
  useEffect(() => {
    const token =
      ((window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string) ?? "";
    const fetchAll = async () => {
      try {
        const [s, m] = await Promise.all([
          fetch("/api/status", {
            headers: { Authorization: `Bearer ${token}` },
          }).then((r) => r.json()),
          api.getModelInfo(),
        ]);
        setStatus(s);
        setModel(m);
      } catch {
        /* best effort */
      }
    };
    fetchAll();
    const interval = setInterval(fetchAll, 15_000);
    return () => clearInterval(interval);
  }, []);

  // ── Listen for MUSE navigation commands in terminal output ──
  // We hook into the xterm parser via a custom OSC handler
  // (registered by ChatPage). Here we also poll the terminal's
  // buffer for navigation triggers as a fallback.
  useEffect(() => {
    const checkBuffer = () => {
      const term = (window as unknown as Record<string, unknown>).__hermesTerminal as
        | { buffer?: { active?: { getLine?: (n: number) => { translateToString?: () => string } | null; length?: number } } }
        | undefined;
      if (!term?.buffer?.active?.getLine) return;

      const len = term.buffer.active.length ?? 0;
      // Check last 3 lines for navigation triggers
      for (let i = Math.max(0, len - 3); i < len; i++) {
        const line = term.buffer.active.getLine(i);
        if (!line?.translateToString) continue;
        const text = line.translateToString().toLowerCase();

        for (const [trigger, path] of Object.entries(NAVIGATION_TRIGGERS)) {
          if (navBufferRef.current.includes(`${i}-${trigger}`)) continue;
          if (text.includes(trigger)) {
            navBufferRef.current += `${i}-${trigger}|`;
            // Keep buffer from growing unbounded
            if (navBufferRef.current.length > 500) {
              navBufferRef.current = navBufferRef.current.slice(-200);
            }
            navigate(path);
            setActionFlash(`Navigating to ${path.replace("/", "")}...`);
            setTimeout(() => setActionFlash(null), 2000);
          }
        }
      }
    };

    const interval = setInterval(checkBuffer, 2000);
    return () => clearInterval(interval);
  }, [navigate]);

  // ── Inject a command into the PTY ──
  const sendCommand = useCallback(
    (cmd: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(cmd);
      setTimeout(() => {
        const s = wsRef.current;
        if (s && s.readyState === WebSocket.OPEN) s.send("\r");
      }, 80);
      setActionFlash(`${cmd}`);
      setTimeout(() => setActionFlash(null), 1500);
    },
    [wsRef],
  );

  return (
    <>
      {/* ── Top-left MUSE identity badge ── */}
      <div className="pointer-events-none absolute left-3 top-3 z-10">
        <div className="pointer-events-auto flex items-center gap-2 rounded-lg border border-cyan-400/10 bg-black/70 px-2.5 py-1 backdrop-blur-md">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-bold tracking-tight text-zinc-100">
              MUSE
            </span>
            <span className="hidden text-[0.55rem] uppercase tracking-widest text-zinc-600 sm:inline">
              Multi-Use Synaptic Entity
            </span>
          </div>
          <span className="h-3 w-px bg-white/10" />
          {model && (
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              title={`${model.provider} · ${model.model} — click to switch`}
              className="flex items-center gap-1 rounded px-1 py-0.5 text-[0.6rem] text-cyan-400/80 transition-colors hover:bg-white/10 hover:text-cyan-300"
            >
              <Cpu className="h-2.5 w-2.5" />
              {model.model?.split("/").pop()}
            </button>
          )}
          {model?.effective_context_length && (
            <span className="hidden text-[0.5rem] text-zinc-600 sm:inline">
              {(model.effective_context_length / 1000).toFixed(0)}k
            </span>
          )}
        </div>
      </div>

      {pickerOpen && (
        <ModelPickerDialog
          loader={api.getModelOptions}
          alwaysGlobal
          title="Switch Model"
          onApply={async ({ provider, model: nextModel }) => {
            await api.setModelAssignment({
              scope: "main",
              provider,
              model: nextModel,
              task: "",
            });
            await refreshModel();
            // Also nudge the live TUI session if the PTY is up.
            sendCommand(`/model ${nextModel} --provider ${provider} --global`);
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      {/* ── Top-right status indicators ── */}
      <div className="pointer-events-none absolute right-3 top-3 z-10">
        <div className="pointer-events-auto flex items-center gap-2">
          {status && (
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2 py-0.5 backdrop-blur-md",
                status.gateway_running
                  ? "border-emerald-400/20 bg-emerald-500/5"
                  : "border-zinc-500/20 bg-zinc-500/5",
              )}
            >
              <CircleDot
                className={cn(
                  "h-2 w-2",
                  status.gateway_running
                    ? "text-emerald-400"
                    : "text-zinc-500",
                )}
              />
              <span
                className={cn(
                  "text-[0.5rem] font-semibold uppercase tracking-wider",
                  status.gateway_running
                    ? "text-emerald-400/80"
                    : "text-zinc-500",
                )}
              >
                {status.gateway_running ? "Live" : "Stopped"}
              </span>
            </div>
          )}
          {status?.active_sessions !== undefined && (
            <div className="flex items-center gap-1 rounded-full border border-white/[0.06] bg-black/70 px-2 py-0.5 backdrop-blur-md">
              <Zap className="h-2.5 w-2.5 text-cyan-400/60" />
              <span className="text-[0.5rem] text-zinc-500">
                {status.active_sessions}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── Quick action bar (bottom of terminal) ── */}
      <div className="pointer-events-none absolute bottom-2 left-1/2 z-10 -translate-x-1/2">
        <div className="pointer-events-auto flex items-center gap-1 rounded-xl border border-white/[0.06] bg-black/80 p-1 backdrop-blur-xl shadow-2xl">
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.cmd}
                onClick={() => sendCommand(action.cmd)}
                className="group flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition-all duration-150 hover:bg-white/[0.06]"
                title={action.cmd}
              >
                <Icon className="h-3 w-3 text-zinc-500 transition-colors group-hover:text-cyan-400" />
                <span className="text-[0.55rem] font-medium uppercase tracking-wider text-zinc-600 transition-colors group-hover:text-zinc-300">
                  {action.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── "Chat controls everything" hint (auto-dismiss) ── */}
      {showHint && (
        <div className="pointer-events-none absolute bottom-14 left-1/2 z-10 -translate-x-1/2">
          <div
            className="pointer-events-auto flex items-center gap-2 rounded-lg border border-cyan-400/10 bg-black/90 px-3 py-1.5 backdrop-blur-md"
            style={{ animation: "museHintIn 0.3s ease-out" }}
          >
            <Terminal className="h-3 w-3 text-cyan-400/60" />
            <span className="text-[0.6rem] text-zinc-400">
              MUSE can control the entire dashboard from here
            </span>
            <ArrowRight className="h-2.5 w-2.5 text-cyan-400/40" />
            <button
              onClick={() => setShowHint(false)}
              className="text-[0.5rem] uppercase tracking-widest text-zinc-600 hover:text-zinc-400"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── Action flash toast ── */}
      {actionFlash && (
        <div className="pointer-events-none absolute right-3 top-12 z-10">
          <div
            className="rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-[0.6rem] font-medium text-cyan-300 backdrop-blur-md"
            style={{ animation: "museFlashIn 0.2s ease-out" }}
          >
            {actionFlash}
          </div>
        </div>
      )}

      <style>{`
        @keyframes museHintIn {
          from { opacity: 0; transform: translate(-50%, 8px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
        @keyframes museFlashIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </>
  );
}
