/**
 * CommandPalette — Cmd/Ctrl+K global command palette.
 *
 * Provides fuzzy search across all dashboard pages + quick actions.
 * Renders as a modal overlay with keyboard navigation.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Terminal,
  MessageSquare,
  Cpu,
  FileText,
  Clock,
  Package,
  Puzzle,
  Settings,
  KeyRound,
  BookOpen,
  Users,
  Globe,
  Sparkles,
  Code,
  RotateCw,
  Search,
  CornerDownLeft,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
  action: () => void;
  category: string;
}

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // ── Build command list ──
  const commands = useMemo<Command[]>(() => {
    const nav = (path: string) => () => {
      navigate(path);
      onClose();
    };
    return [
      { id: "chat", label: "Chat", hint: "AI conversation terminal", icon: Terminal, action: nav("/chat"), category: "Navigate" },
      { id: "studio", label: "Studio", hint: "Generative studio cockpit", icon: Code, action: nav("/studio"), category: "Navigate" },
      { id: "sessions", label: "Sessions", hint: "Browse conversation history", icon: MessageSquare, action: nav("/sessions"), category: "Navigate" },
      { id: "models", label: "Models", hint: "Switch AI model", icon: Cpu, action: nav("/models"), category: "Navigate" },
      { id: "logs", label: "Logs", hint: "System activity logs", icon: FileText, action: nav("/logs"), category: "Navigate" },
      { id: "cron", label: "Cron Jobs", hint: "Scheduled tasks", icon: Clock, action: nav("/cron"), category: "Navigate" },
      { id: "skills", label: "Skills", hint: "Agent skill library", icon: Package, action: nav("/skills"), category: "Navigate" },
      { id: "plugins", label: "Plugins", hint: "Dashboard extensions", icon: Puzzle, action: nav("/plugins"), category: "Navigate" },
      { id: "musehq", label: "MuseHQ", hint: "Cockpit shell", icon: Sparkles, action: nav("/musehq"), category: "Navigate" },
      { id: "nexus", label: "Nexus", hint: "Command console", icon: Globe, action: nav("/nexus"), category: "Navigate" },
      { id: "profiles", label: "Profiles", hint: "Agent profiles", icon: Users, action: nav("/profiles"), category: "Navigate" },
      { id: "config", label: "Config", hint: "System configuration", icon: Settings, action: nav("/config"), category: "Navigate" },
      { id: "keys", label: "API Keys", hint: "Environment variables", icon: KeyRound, action: nav("/env"), category: "Navigate" },
      { id: "docs", label: "Documentation", hint: "Help & docs", icon: BookOpen, action: nav("/docs"), category: "Navigate" },
      {
        id: "restart-gateway",
        label: "Restart Gateway",
        hint: "Restart the messaging gateway",
        icon: RotateCw,
        action: async () => {
          try {
            const token = (window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string;
            await fetch("/api/gateway/restart", {
              method: "POST",
              headers: { Authorization: `Bearer ${token}` },
            });
          } catch { /* best effort */ }
          onClose();
        },
        category: "Actions",
      },
    ];
  }, [navigate, onClose]);

  // ── Filter commands ──
  const filtered = useMemo(() => {
    if (!query) return commands;
    const q = query.toLowerCase();
    return commands.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.hint?.toLowerCase().includes(q) ||
        c.category.toLowerCase().includes(q),
    );
  }, [commands, query]);

  // ── Keyboard navigation ──
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        filtered[selectedIndex]?.action();
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, filtered, selectedIndex, onClose]);

  // ── Scroll selected into view ──
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selectedIndex}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (!open) return null;

  // Group by category
  const categories = Array.from(new Set(filtered.map((c) => c.category)));

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Palette */}
      <div
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        style={{ animation: "paletteEnter 0.12s ease-out" }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3.5">
          <Search className="h-4 w-4 shrink-0 text-zinc-500" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command or search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
          />
          <kbd className="shrink-0 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[0.55rem] font-mono text-zinc-500">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-zinc-600">
              No results found
            </div>
          )}
          {categories.map((cat) => (
            <div key={cat} className="mb-2">
              <div className="px-3 py-1 text-[0.55rem] font-semibold uppercase tracking-widest text-zinc-700">
                {cat}
              </div>
              {filtered
                .filter((c) => c.category === cat)
                .map((cmd) => {
                  const idx = filtered.indexOf(cmd);
                  const Icon = cmd.icon;
                  const isSelected = idx === selectedIndex;
                  return (
                    <button
                      key={cmd.id}
                      data-idx={idx}
                      onClick={() => cmd.action()}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                        isSelected ? "bg-cyan-500/10" : "hover:bg-white/[0.03]",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 shrink-0",
                          isSelected ? "text-cyan-400" : "text-zinc-500",
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div
                          className={cn(
                            "text-sm font-medium",
                            isSelected ? "text-zinc-100" : "text-zinc-300",
                          )}
                        >
                          {cmd.label}
                        </div>
                        {cmd.hint && (
                          <div className="text-[0.65rem] text-zinc-600">
                            {cmd.hint}
                          </div>
                        )}
                      </div>
                      {isSelected && (
                        <CornerDownLeft className="h-3 w-3 shrink-0 text-cyan-400/60" />
                      )}
                    </button>
                  );
                })}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-2 text-[0.6rem] text-zinc-600">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <ArrowUp className="h-2.5 w-2.5" />
              <ArrowDown className="h-2.5 w-2.5" />
              navigate
            </span>
            <span className="flex items-center gap-1">
              <CornerDownLeft className="h-2.5 w-2.5" />
              select
            </span>
          </div>
          <span>{filtered.length} results</span>
        </div>
      </div>

      <style>{`
        @keyframes paletteEnter {
          from { transform: translateY(-12px) scale(0.98); opacity: 0; }
          to { transform: translateY(0) scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
