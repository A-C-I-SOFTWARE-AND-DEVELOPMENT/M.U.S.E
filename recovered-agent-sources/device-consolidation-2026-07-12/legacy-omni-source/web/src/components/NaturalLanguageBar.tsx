/**
 * NaturalLanguageBar — Type to navigate/control the dashboard.
 *
 * A smart search bar that accepts natural language and maps it to
 * dashboard actions. Examples:
 *   "show me logs" → /logs
 *   "switch to claude" → /models
 *   "what skills do I have" → /skills
 *   "restart gateway" → POST /api/gateway/restart
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CornerDownLeft, Sparkles, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface NLAction {
  id: string;
  label: string;
  hint: string;
  keywords: string[];
  action: () => void;
  type: "navigate" | "command";
}

const SESSION_TOKEN =
  typeof window !== "undefined"
    ? ((window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string) ?? ""
    : "";

export function NaturalLanguageBar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [executing, setExecuting] = useState(false);
  const [lastAction, setLastAction] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const go = (path: string) => () => navigate(path);

  const restartGateway = async () => {
    setExecuting(true);
    try {
      await fetch("/api/gateway/restart", {
        method: "POST",
        headers: { Authorization: `Bearer ${SESSION_TOKEN}` },
      });
      setLastAction("Gateway restarting...");
    } catch {
      setLastAction("Failed to restart gateway");
    }
    setExecuting(false);
    setTimeout(() => setLastAction(null), 2000);
  };

  const actions = useMemo<NLAction[]>(() => {
    return [
      { id: "chat", label: "Open Chat", hint: "AI conversation terminal", keywords: ["chat", "talk", "ask", "prompt", "message", "conversation"], action: go("/chat"), type: "navigate" },
      { id: "studio", label: "Open Studio", hint: "Full-screen cockpit", keywords: ["studio", "cockpit", "overview", "dashboard", "home"], action: go("/studio"), type: "navigate" },
      { id: "sessions", label: "View Sessions", hint: "Conversation history", keywords: ["session", "history", "past", "previous", "record"], action: go("/sessions"), type: "navigate" },
      { id: "models", label: "Switch Model", hint: "Change AI model", keywords: ["model", "switch", "claude", "gpt", "gemini", "glm", "provider"], action: go("/models"), type: "navigate" },
      { id: "logs", label: "View Logs", hint: "System activity", keywords: ["log", "logs", "activity", "debug", "error", "trace"], action: go("/logs"), type: "navigate" },
      { id: "cron", label: "Manage Cron Jobs", hint: "Scheduled tasks", keywords: ["cron", "schedule", "timer", "recurring", "automate", "autopilot"], action: go("/cron"), type: "navigate" },
      { id: "skills", label: "Browse Skills", hint: "133 agent skills", keywords: ["skill", "skills", "browse", "search", "marketplace", "library", "capability"], action: go("/skills"), type: "navigate" },
      { id: "plugins", label: "View Plugins", hint: "Dashboard extensions", keywords: ["plugin", "plugins", "extension", "addon", "module"], action: go("/plugins"), type: "navigate" },
      { id: "config", label: "Edit Config", hint: "System settings", keywords: ["config", "setting", "settings", "configure", "preference"], action: go("/config"), type: "navigate" },
      { id: "keys", label: "API Keys", hint: "Environment variables", keywords: ["key", "keys", "api", "secret", "token", "env", "environment"], action: go("/env"), type: "navigate" },
      { id: "profiles", label: "Agent Profiles", hint: "Persona management", keywords: ["profile", "profiles", "persona", "character", "agent"], action: go("/profiles"), type: "navigate" },
      { id: "docs", label: "Documentation", hint: "Help & guides", keywords: ["doc", "docs", "help", "guide", "manual", "documentation", "how"], action: go("/docs"), type: "navigate" },
      { id: "restart", label: "Restart Gateway", hint: "Restart messaging gateway", keywords: ["restart", "reboot", "gateway", "reload", "start"], action: restartGateway, type: "command" },
    ];
  }, [navigate]);

  const filtered = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase().trim();
    return actions
      .filter((a) => {
        const score = a.keywords.reduce(
          (acc, kw) => acc + (q.includes(kw) || kw.includes(q) ? 1 : 0),
          0,
        );
        return score > 0 || a.label.toLowerCase().includes(q);
      })
      .sort((a, b) => {
        const sa = a.keywords.reduce(
          (acc, kw) => acc + (q.includes(kw) || kw.includes(q) ? 1 : 0),
          0,
        );
        const sb = b.keywords.reduce(
          (acc, kw) => acc + (q.includes(kw) || kw.includes(q) ? 1 : 0),
          0,
        );
        return sb - sa;
      })
      .slice(0, 5);
  }, [query, actions]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Global shortcut: Cmd+/
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      e.preventDefault();
      filtered[selectedIndex].action();
      setQuery("");
      inputRef.current?.blur();
    }
  };

  return (
    <div className="relative w-full max-w-md">
      <div
        className={cn(
          "flex items-center gap-2 rounded-xl border bg-white/[0.02] px-3 py-2 transition-all",
          focused
            ? "border-cyan-400/30 bg-white/[0.04]"
            : "border-white/[0.06]",
        )}
      >
        <Sparkles
          className={cn(
            "h-3.5 w-3.5 shrink-0 transition-colors",
            focused ? "text-cyan-400" : "text-zinc-600",
          )}
        />
        <input
          ref={inputRef}
          type="text"
          placeholder="Ask MUSE to do anything..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          onKeyDown={handleKey}
          className="min-w-0 flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
        />
        <kbd className="shrink-0 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[0.5rem] font-mono text-zinc-600">
          ⌘/
        </kbd>
      </div>

      {/* Results dropdown */}
      {focused && filtered.length > 0 && (
        <div
          className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-xl border border-white/10 bg-zinc-950/95 py-1 shadow-2xl backdrop-blur-xl"
          style={{ animation: "nlBarDrop 0.12s ease-out" }}
        >
          {filtered.map((action, i) => (
            <button
              key={action.id}
              onMouseDown={(e) => {
                e.preventDefault();
                action.action();
                setQuery("");
                inputRef.current?.blur();
              }}
              onMouseEnter={() => setSelectedIndex(i)}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2 text-left transition-colors",
                i === selectedIndex ? "bg-cyan-500/10" : "hover:bg-white/[0.03]",
              )}
            >
              {action.type === "command" ? (
                <Zap className="h-3.5 w-3.5 shrink-0 text-amber-400/70" />
              ) : (
                <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-cyan-400/70" />
              )}
              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    "text-xs font-medium",
                    i === selectedIndex ? "text-zinc-100" : "text-zinc-300",
                  )}
                >
                  {action.label}
                </div>
                <div className="text-[0.6rem] text-zinc-600">{action.hint}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Execution toast */}
      {(executing || lastAction) && (
        <div className="absolute right-0 top-full mt-1 rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-[0.6rem] font-medium text-cyan-300 backdrop-blur-md">
          {executing ? "Executing..." : lastAction}
        </div>
      )}

      <style>{`
        @keyframes nlBarDrop {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
