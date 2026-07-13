/**
 * StudioShell — Full-screen M.U.S.E Studio container.
 *
 * Renders the pure-React StudioCockpit (no iframe, no demo data)
 * with a floating dock for navigation to dashboard tools.
 *
 * Power-user features:
 * - Keyboard shortcut Cmd/Ctrl+K to toggle dock
 * - Live API data overlay (status, sessions, models, cron, skills, logs)
 * - Mobile-responsive status bar
 */

import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
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
  LayoutGrid,
  Search,
  ChevronRight,
} from "lucide-react";
import StudioCockpit from "@/components/StudioCockpit";

/* ── Dock navigation items ── */

const DOCK_ITEMS = [
  { path: "/chat", label: "Chat", icon: Terminal },
  { path: "/sessions", label: "Sessions", icon: MessageSquare },
  { path: "/models", label: "Models", icon: Cpu },
  { path: "/logs", label: "Logs", icon: FileText },
  { path: "/cron", label: "Cron", icon: Clock },
  { path: "/skills", label: "Skills", icon: Package },
  { path: "/plugins", label: "Plugins", icon: Puzzle },
  { path: "/musehq", label: "MuseHQ", icon: Sparkles },
  { path: "/nexus", label: "Nexus", icon: Globe },
  { path: "/profiles", label: "Profiles", icon: Users },
  { path: "/config", label: "Config", icon: Settings },
  { path: "/env", label: "Keys", icon: KeyRound },
  { path: "/docs", label: "Docs", icon: BookOpen },
];

export default function StudioShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [dockOpen, setDockOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // ── Keyboard shortcut: Cmd/Ctrl+K to toggle dock ──
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setDockOpen((p) => !p);
      }
      if (e.key === "Escape") setDockOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ── Close dock on navigation ──
  useEffect(() => {
    setDockOpen(false);
  }, [location.pathname]);

  // ── Filtered dock items for search ──
  const filteredDock = useMemo(() => {
    if (!searchQuery) return DOCK_ITEMS;
    const q = searchQuery.toLowerCase();
    return DOCK_ITEMS.filter((d) => d.label.toLowerCase().includes(q));
  }, [searchQuery]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-[#050507]">
      {/* ── Pure React Cockpit (replaces iframe) ── */}
      <StudioCockpit />

      {/* ── Floating Nav button (bottom-right) ── */}
      {!dockOpen && (
        <button
          onClick={() => setDockOpen(true)}
          className="group fixed bottom-4 right-4 z-20 flex items-center gap-2 rounded-full border border-cyan-400/20 bg-zinc-950/90 px-5 py-2.5 shadow-2xl shadow-cyan-500/5 backdrop-blur-xl transition-all duration-200 hover:border-cyan-400/40 hover:shadow-cyan-500/10"
          aria-label="Open navigation (Cmd+K)"
        >
          <LayoutGrid className="h-4 w-4 text-cyan-400 transition-transform group-hover:scale-110" />
          <span className="text-xs font-semibold uppercase tracking-widest text-zinc-300">
            Navigate
          </span>
          <kbd className="ml-1 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[0.55rem] font-mono text-zinc-500">
            ⌘K
          </kbd>
        </button>
      )}

      {/* ── Slide-up dock panel ── */}
      {dockOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-black/60 backdrop-blur-md"
            onClick={() => setDockOpen(false)}
            style={{ animation: "studioFadeIn 0.15s ease-out" }}
          />
          <div
            className="fixed bottom-0 left-0 right-0 z-40 max-h-[75vh] overflow-y-auto border-t border-white/[0.06] bg-zinc-950/95 backdrop-blur-2xl"
            style={{ animation: "studioSlideUp 0.2s cubic-bezier(0.16,1,0.3,1)" }}
          >
            <div className="border-b border-white/[0.04] px-4 py-3">
              <div className="mx-auto flex max-w-2xl items-center gap-3">
                <Search className="h-4 w-4 text-zinc-500" />
                <input
                  autoFocus
                  type="text"
                  placeholder="Search navigation..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
                />
                <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[0.55rem] font-mono text-zinc-500">
                  ESC
                </kbd>
              </div>
            </div>

            <div className="px-4 py-4">
              <div className="mx-auto max-w-2xl">
                <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 md:grid-cols-4">
                  {filteredDock.map((item) => {
                    const Icon = item.icon;
                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className="group flex items-center gap-2.5 rounded-xl border border-transparent bg-white/[0.02] px-3 py-3 transition-all hover:border-white/10 hover:bg-white/[0.05]"
                      >
                        <Icon className="h-4 w-4 shrink-0 text-zinc-500 transition-colors group-hover:text-cyan-400" />
                        <span className="text-xs font-medium uppercase tracking-wider text-zinc-400 transition-colors group-hover:text-zinc-200">
                          {item.label}
                        </span>
                        <ChevronRight className="ml-auto h-3 w-3 text-zinc-700 opacity-0 transition-opacity group-hover:opacity-100" />
                      </NavLink>
                    );
                  })}
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-white/[0.04] pt-3">
                  <NavLink
                    to="/studio"
                    onClick={() => setDockOpen(false)}
                    className="text-[0.65rem] uppercase tracking-widest text-zinc-600 transition-colors hover:text-zinc-400"
                  >
                    Studio Home
                  </NavLink>
                  <button
                    onClick={() => {
                      setDockOpen(false);
                      navigate("/chat");
                    }}
                    className="flex items-center gap-1 text-[0.65rem] uppercase tracking-widest text-zinc-600 transition-colors hover:text-zinc-400"
                  >
                    Go to Chat
                    <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      <style>{`
        @keyframes studioSlideUp {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        @keyframes studioFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
