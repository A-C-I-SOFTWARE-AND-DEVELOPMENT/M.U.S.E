import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Cpu, Globe, MessageSquare, Sparkles, X, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface QuickAction {
  label: string;
  path: string;
  icon: typeof Globe;
}

const QUICK_ACTIONS: QuickAction[] = [
  { label: "Studio", path: "/studio", icon: Globe },
  { label: "Sessions", path: "/sessions", icon: MessageSquare },
  { label: "Models", path: "/models", icon: Cpu },
];

/**
 * MuseChatOverlay — a lightweight M.U.S.E identity badge + quick-action
 * dock that floats over the Chat page (xterm.js terminal) when the
 * dashboard runs in TUI mode.
 *
 * The overlay is intentionally minimal: a small pill at bottom-right
 * that expands on hover/click to reveal navigation shortcuts. It never
 * blocks the terminal — pointer-events are restricted to the pill itself.
 */
export function MuseChatOverlay() {
  const location = useLocation();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [visible, setVisible] = useState(false);

  // Only show on /chat route
  useEffect(() => {
    const isChat = location.pathname === "/chat";
    setVisible(isChat);
    if (!isChat) setExpanded(false);
  }, [location.pathname]);

  // Keyboard toggle: press 'm' to expand/collapse when on chat
  useEffect(() => {
    if (!visible) return;
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === "m" &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        e.target === document.body
      ) {
        setExpanded((prev) => !prev);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible]);

  if (!visible) return null;

  return (
    <div
      className="muse-chat-overlay fixed bottom-4 right-4 z-30 flex flex-col items-end gap-2"
      style={{ pointerEvents: "none" }}
    >
      {/* Expanded panel */}
      {expanded && (
        <div
          className="muse-overlay-panel flex flex-col gap-1 rounded-lg border border-current/15 bg-black/80 p-1.5 backdrop-blur-md"
          style={{ pointerEvents: "auto" }}
        >
          {/* Identity header */}
          <div className="flex items-center gap-2 px-2 py-1.5">
            <Sparkles className="h-3 w-3 text-cyan-400/60" />
            <span className="font-mondwest text-[0.7rem] tracking-[0.12em] uppercase text-midground/70">
              M.U.S.E
            </span>
          </div>

          <div className="h-px w-full bg-current/10" />

          {/* Quick actions */}
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.path}
                onClick={() => {
                  navigate(action.path);
                  setExpanded(false);
                }}
                className="group flex items-center gap-2.5 rounded px-2 py-1.5 transition-colors hover:bg-white/[0.06]"
              >
                <Icon className="h-3.5 w-3.5 text-midground/40 transition-colors group-hover:text-midground/70" />
                <span className="font-mondwest text-[0.75rem] tracking-[0.08em] text-midground/60 transition-colors group-hover:text-midground">
                  {action.label}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Toggle pill */}
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className={cn(
          "muse-overlay-pill group flex items-center gap-1.5 rounded-full border px-3 py-1.5",
          "border-current/15 bg-black/70 backdrop-blur-md",
          "transition-all hover:border-current/30 hover:bg-black/85",
        )}
        style={{ pointerEvents: "auto" }}
        aria-label="Toggle M.U.S.E overlay"
      >
        {expanded ? (
          <X className="h-3 w-3 text-midground/50" />
        ) : (
          <Zap className="h-3 w-3 text-cyan-400/60" />
        )}
        <span className="font-mondwest text-[0.65rem] tracking-[0.15em] uppercase text-midground/50 transition-colors group-hover:text-midground/70">
          muse
        </span>
      </button>
    </div>
  );
}
