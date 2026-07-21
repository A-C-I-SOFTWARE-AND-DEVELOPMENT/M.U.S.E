import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  Brain,
  Clock,
  Code,
  Cpu,
  Download,
  KeyRound,
  MessageSquare,
  Package,
  Puzzle,
  RotateCw,
  Settings,
  Terminal,
  Users,
  Waypoints,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: LucideIcon;
  action: () => void;
  keywords?: string[];
}

interface CommandPaletteProps {
  onSystemAction?: (action: "restart" | "update") => void;
}

/**
 * CommandPalette — Cmd+K (Mac) / Ctrl+K (Windows) command palette.
 *
 * A centered modal overlay with fuzzy-search navigation to every
 * dashboard route plus system actions (restart gateway, update).
 * Arrow-key navigable, Esc to close, Enter to execute.
 */
export function CommandPalette({ onSystemAction }: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Build command list
  const commands = useMemo<Command[]>(() => {
    const navCommands: Command[] = [
      { id: "sessions", label: "Sessions", icon: MessageSquare, action: () => navigate("/sessions"), keywords: ["history", "chat"] },
      { id: "chat", label: "Chat", icon: Terminal, action: () => navigate("/chat"), keywords: ["terminal", "tui"] },
      { id: "studio", label: "Studio", icon: Zap, action: () => navigate("/studio"), keywords: ["mission control", "dashboard"] },
      { id: "fusion", label: "Fusion", icon: Waypoints, action: () => navigate("/fusion"), keywords: ["agents", "pipeline", "orchestrate"] },
      { id: "moa", label: "MoA", icon: Brain, action: () => navigate("/moa"), keywords: ["moa", "mixture of agents", "rounds", "synthesis"] },
      { id: "models", label: "Models", icon: Cpu, action: () => navigate("/models"), keywords: ["provider", "llm"] },
      { id: "analytics", label: "Analytics", icon: BarChart3, action: () => navigate("/analytics"), keywords: ["stats", "usage", "tokens"] },
      { id: "logs", label: "Logs", icon: BookOpen, action: () => navigate("/logs"), keywords: ["debug", "errors"] },
      { id: "cron", label: "Cron Jobs", icon: Clock, action: () => navigate("/cron"), keywords: ["schedule", "jobs", "timer"] },
      { id: "skills", label: "Skills", icon: Package, action: () => navigate("/skills"), keywords: ["tools", "abilities"] },
      { id: "plugins", label: "Plugins", icon: Puzzle, action: () => navigate("/plugins"), keywords: ["extensions", "addons"] },
      { id: "profiles", label: "Profiles", icon: Users, action: () => navigate("/profiles"), keywords: ["accounts", "users"] },
      { id: "config", label: "Config", icon: Settings, action: () => navigate("/config"), keywords: ["settings", "preferences"] },
      { id: "env", label: "Keys", icon: KeyRound, action: () => navigate("/env"), keywords: ["environment", "secrets", "api"] },
      { id: "docs", label: "Documentation", icon: Code, action: () => navigate("/docs"), keywords: ["help", "manual"] },
    ];

    const systemCommands: Command[] = [
      {
        id: "restart",
        label: "Restart Gateway",
        hint: "System",
        icon: RotateCw,
        action: () => onSystemAction?.("restart"),
        keywords: ["reload", "reboot"],
      },
      {
        id: "update",
        label: "Update muse",
        hint: "System",
        icon: Download,
        action: () => onSystemAction?.("update"),
        keywords: ["upgrade", "install"],
      },
    ];

    return [...navCommands, ...systemCommands];
  }, [navigate, onSystemAction]);

  // Global keyboard shortcut
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Filter commands
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((cmd) => {
      const haystack = [cmd.label, ...(cmd.keywords ?? []), cmd.hint ?? ""].join(" ").toLowerCase();
      return q.split(/\s+/).every((word) => haystack.includes(word));
    });
  }, [commands, query]);

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case "Escape":
          e.preventDefault();
          setOpen(false);
          break;
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (filtered[selectedIndex]) {
            filtered[selectedIndex].action();
            setOpen(false);
          }
          break;
      }
    },
    [filtered, selectedIndex],
  );

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selectedIndex}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (!open) return null;

  return (
    <div
      className="muse-cmd-palette fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className={cn(
          "relative w-full max-w-lg mx-4",
          "rounded-xl border border-current/15 bg-black/90 shadow-2xl backdrop-blur-xl",
          "overflow-hidden",
        )}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-current/10 px-4 py-3">
          <Zap className="h-4 w-4 shrink-0 text-midground/30" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search commands…"
            className={cn(
              "flex-1 bg-transparent text-[0.9rem] text-midground placeholder:text-midground/20",
              "focus:outline-none",
            )}
          />
          <kbd className="shrink-0 rounded border border-current/10 px-1.5 py-0.5 font-mono text-[0.65rem] opacity-30">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <span className="text-[0.8rem] opacity-30">No commands found</span>
            </div>
          ) : (
            filtered.map((cmd, idx) => {
              const Icon = cmd.icon;
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={cmd.id}
                  data-idx={idx}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => {
                    cmd.action();
                    setOpen(false);
                  }}
                  className={cn(
                    "group flex w-full items-center gap-3 rounded-lg px-3 py-2.5",
                    "transition-colors",
                    !isSelected && "hover:bg-white/[0.03]",
                  )}
                  style={isSelected ? { background: "var(--bg-mute)" } : undefined}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0 transition-colors",
                      !isSelected && "text-midground/40",
                    )}
                    style={isSelected ? { color: "var(--accent)" } : undefined}
                  />
                  <span
                    className={cn(
                      "flex-1 text-left text-[13px] transition-colors",
                      isSelected ? "text-midground" : "text-midground/60",
                    )}
                  >
                    {cmd.label}
                  </span>
                  {cmd.hint && (
                    <span className="text-[11px] opacity-30" style={{ color: "var(--fg-faint)" }}>
                      {cmd.hint}
                    </span>
                  )}
                  {isSelected && (
                    <span className="text-[0.65rem] opacity-30">↵</span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-current/10 px-4 py-2">
          <div className="flex items-center gap-3 text-[0.6rem] opacity-20">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-current/10 px-1">↑↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-current/10 px-1">↵</kbd>
              select
            </span>
          </div>
          <span className="text-[11px]" style={{ color: "var(--fg-faint)" }}>
            {filtered.length} commands
          </span>
        </div>
      </div>
    </div>
  );
}
