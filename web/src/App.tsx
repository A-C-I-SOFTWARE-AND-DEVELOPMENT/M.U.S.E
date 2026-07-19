import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import {
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  Clock,
  Code,
  Cpu,
  Database,
  Download,
  Eye,
  FileText,
  Globe,
  Heart,
  KeyRound,
  Menu,
  MessageSquare,
  Package,
  Puzzle,
  RotateCw,
  Settings,
  Shield,
  Sparkles,
  Star,
  Terminal,
  Users,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { SelectionSwitcher } from "@nous-research/ui/ui/components/selection-switcher";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { cn } from "@/lib/utils";
import { Backdrop } from "@/components/Backdrop";
import { ObservatoryCanvas } from "@/components/observatory/ObservatoryCanvas";
import { CursorRing } from "@/components/cursor/CursorRing";
import { BootSplash } from "@/components/BootSplash";
import { CrossSpaBanner } from "@/components/CrossSpaBanner";
import { SidebarFooter } from "@/components/SidebarFooter";
import { SidebarStatusStrip } from "@/components/SidebarStatusStrip";
import { PageHeaderProvider } from "@/contexts/PageHeaderProvider";
import { useSystemActions } from "@/contexts/useSystemActions";
import type { SystemAction } from "@/contexts/system-actions-context";
import ConfigPage from "@/pages/ConfigPage";
import DocsPage from "@/pages/DocsPage";
import EnvPage from "@/pages/EnvPage";
import SessionsPage from "@/pages/SessionsPage";
import StudioPage from "@/pages/StudioPage";
import LogsPage from "@/pages/LogsPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import ModelsPage from "@/pages/ModelsPage";
import CronPage from "@/pages/CronPage";
import ProfilesPage from "@/pages/ProfilesPage";
import SkillsPage from "@/pages/SkillsPage";
import PluginsPage from "@/pages/PluginsPage";
import ChatPage from "@/pages/ChatPage";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { CommandPalette } from "@/components/CommandPalette";
import { MuseChatBox } from "@/components/chat/MuseChatBox";
import { useI18n } from "@/i18n";
import type { Translations } from "@/i18n/types";
import { PluginPage, PluginSlot, usePlugins } from "@/plugins";
import type { PluginManifest } from "@/plugins";
import { useTheme } from "@/themes";
import { isDashboardEmbeddedChatEnabled } from "@/lib/dashboard-flags";
import { api } from "@/lib/api";

function RootRedirect() {
  return <Navigate to="/sessions" replace />;
}

function UnknownRouteFallback({ pluginsLoading }: { pluginsLoading: boolean }) {
  const navigate = useNavigate();
  if (pluginsLoading) {
    // Render nothing during the plugin-load window — a spinner here would just flash.
    return null;
  }
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="text-7xl font-bold text-muted-foreground/30">404</div>
      <div className="space-y-1">
        <p className="text-lg font-medium text-foreground">Page not found</p>
        <p className="text-sm text-muted-foreground">
          The route <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{window.location.pathname}</code> doesn't exist.
        </p>
      </div>
      <button
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        onClick={() => navigate("/sessions")}
      >
        Go to Sessions
      </button>
    </div>
  );
}

const CHAT_NAV_ITEM: NavItem = {
  path: "/chat",
  labelKey: "chat",
  label: "Chat",
  icon: Terminal,
};

/**
 * Built-in routes except /chat.  Chat is rendered persistently (outside
 * <Routes>) when embedded — see the persistent chat host block rendered
 * inline near the bottom of this file — so the PTY child, WebSocket,
 * and xterm instance survive when the user visits another tab and comes
 * back.  A `display:none` toggle hides the terminal without unmounting.
 * Routing still owns the URL so /chat deep-links, browser back/forward,
 * and nav highlight keep working.
 */
const BUILTIN_ROUTES_CORE: Record<string, ComponentType> = {
  "/": RootRedirect,
  "/sessions": SessionsPage,
  "/analytics": AnalyticsPage,
  "/models": ModelsPage,
  "/logs": LogsPage,
  "/cron": CronPage,
  "/skills": SkillsPage,
  "/plugins": PluginsPage,
  "/profiles": ProfilesPage,
  "/config": ConfigPage,
  "/env": EnvPage,
  "/docs": DocsPage,
  "/studio": StudioPage,
};

// Route placeholder for /chat.  The persistent ChatPage host (rendered
// outside <Routes> when embedded chat is on) paints on top; this empty
// element just claims the path so the `*` catch-all redirect doesn't
// fire when the user navigates to /chat.
function ChatRouteSink() {
  return null;
}

const BUILTIN_NAV_REST: NavItem[] = [
  {
    path: "/studio",
    labelKey: "studio",
    label: "Studio",
    icon: Sparkles,
  },
  {
    path: "/sessions",
    labelKey: "sessions",
    label: "Sessions",
    icon: MessageSquare,
  },
  {
    path: "/analytics",
    labelKey: "analytics",
    label: "Analytics",
    icon: BarChart3,
  },
  {
    path: "/models",
    labelKey: "models",
    label: "Models",
    icon: Cpu,
  },
  { path: "/logs", labelKey: "logs", label: "Logs", icon: FileText },
  { path: "/cron", labelKey: "cron", label: "Cron", icon: Clock },
  { path: "/skills", labelKey: "skills", label: "Skills", icon: Package },
  { path: "/plugins", labelKey: "plugins", label: "Plugins", icon: Puzzle },
  { path: "/profiles", labelKey: "profiles", label: "Profiles", icon: Users },
  { path: "/config", labelKey: "config", label: "Config", icon: Settings },
  { path: "/env", labelKey: "keys", label: "Keys", icon: KeyRound },
  {
    path: "/docs",
    labelKey: "documentation",
    label: "Documentation",
    icon: BookOpen,
  },
];

/**
 * Sidebar hub sections (design contract Part 2.1). Items are resolved by
 * path against the merged built-in nav, so the /analytics config-flag hide
 * and the embedded-chat /chat inclusion keep working unchanged — a path
 * absent from the built-in nav simply drops out of its section.
 * Section labels are sentence case; i18n keys are requested in
 * wiring/shell.manifest.md (currently English-only).
 */
const NAV_SECTIONS: Array<{ id: string; label: string; paths: string[] }> = [
  { id: "chat", label: "Chat", paths: ["/chat", "/sessions"] },
  { id: "agents", label: "Agents", paths: ["/studio", "/skills", "/plugins"] },
  { id: "automate", label: "Automate", paths: ["/cron"] },
  { id: "observe", label: "Observe", paths: ["/analytics", "/logs"] },
  {
    id: "system",
    label: "System",
    paths: ["/models", "/profiles", "/config", "/env", "/docs"],
  },
];

const ICON_MAP: Record<string, ComponentType<{ className?: string }>> = {
  Activity,
  BarChart3,
  Clock,
  Cpu,
  FileText,
  KeyRound,
  MessageSquare,
  Package,
  Settings,
  Puzzle,
  Sparkles,
  Terminal,
  Globe,
  Database,
  Shield,
  Users,
  Wrench,
  Zap,
  Heart,
  Star,
  Code,
  Eye,
};

function resolveIcon(name: string): ComponentType<{ className?: string }> {
  return ICON_MAP[name] ?? Puzzle;
}

function buildNavItems(
  builtIn: NavItem[],
  manifests: PluginManifest[],
): NavItem[] {
  const items = [...builtIn];

  for (const manifest of manifests) {
    if (manifest.tab.override) continue;
    if (manifest.tab.hidden) continue;

    const pluginItem: NavItem = {
      path: manifest.tab.path,
      label: manifest.label,
      icon: resolveIcon(manifest.icon),
    };

    const pos = manifest.tab.position ?? "end";
    if (pos === "end") {
      items.push(pluginItem);
    } else if (pos.startsWith("after:")) {
      const target = "/" + pos.slice(6);
      const idx = items.findIndex((i) => i.path === target);
      items.splice(idx >= 0 ? idx + 1 : items.length, 0, pluginItem);
    } else if (pos.startsWith("before:")) {
      const target = "/" + pos.slice(7);
      const idx = items.findIndex((i) => i.path === target);
      items.splice(idx >= 0 ? idx : items.length, 0, pluginItem);
    } else {
      items.push(pluginItem);
    }
  }

  return items;
}

/** Split merged nav into built-in sidebar entries vs plugin tabs, preserving plugin order hints. */
function partitionSidebarNav(
  builtIn: NavItem[],
  manifests: PluginManifest[],
): { coreItems: NavItem[]; pluginItems: NavItem[] } {
  const merged = buildNavItems(builtIn, manifests);
  const builtinPaths = new Set(builtIn.map((i) => i.path));
  const coreItems: NavItem[] = [];
  const pluginItems: NavItem[] = [];
  for (const item of merged) {
    if (builtinPaths.has(item.path)) coreItems.push(item);
    else pluginItems.push(item);
  }
  return { coreItems, pluginItems };
}

function buildRoutes(
  builtinRoutes: Record<string, ComponentType>,
  manifests: PluginManifest[],
): Array<{
  key: string;
  path: string;
  element: ReactNode;
}> {
  const byOverride = new Map<string, PluginManifest>();
  const addons: PluginManifest[] = [];

  for (const m of manifests) {
    if (m.tab.override) {
      byOverride.set(m.tab.override, m);
    } else {
      addons.push(m);
    }
  }

  const routes: Array<{
    key: string;
    path: string;
    element: ReactNode;
  }> = [];

  for (const [path, Component] of Object.entries(builtinRoutes)) {
    const om = byOverride.get(path);
    if (om) {
      routes.push({
        key: `override:${om.name}`,
        path,
        element: <PluginPage name={om.name} />,
      });
    } else {
      routes.push({ key: `builtin:${path}`, path, element: <Component /> });
    }
  }

  for (const m of addons) {
    if (m.tab.hidden) continue;
    if (m.tab.path === "/plugins") continue;
    if (builtinRoutes[m.tab.path]) continue;
    routes.push({
      key: `plugin:${m.name}`,
      path: m.tab.path,
      element: <PluginPage name={m.name} />,
    });
  }

  for (const m of manifests) {
    if (!m.tab.hidden) continue;
    if (m.tab.path === "/plugins") continue;
    if (builtinRoutes[m.tab.path] || m.tab.override) continue;
    routes.push({
      key: `plugin:hidden:${m.name}`,
      path: m.tab.path,
      element: <PluginPage name={m.name} />,
    });
  }

  return routes;
}

export default function App() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { manifests, loading: pluginsLoading } = usePlugins();
  const { theme } = useTheme();
  const { runAction } = useSystemActions();
  const [mobileOpen, setMobileOpen] = useState(false);
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  const isDocsRoute = pathname === "/docs" || pathname === "/docs/";
  const normalizedPath = pathname.replace(/\/$/, "") || "/";
  const isChatRoute = normalizedPath === "/chat";
  const embeddedChat = isDashboardEmbeddedChatEnabled();

  // One-shot version fetch for the sidebar wordmark (the 10s polling
  // instance stays in SidebarFooter — no second poller added here).
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    api
      .getStatus()
      .then((st) => setVersion(st.version ?? null))
      .catch(() => {});
  }, []);

  // CommandPalette system actions: restart/update have real endpoints via
  // the SystemActions provider (api.restartGateway / api.updateHermes), so
  // wire them through — never leave a silent no-op in the palette. Mirrors
  // SidebarSystemActions: kick the action, then land on /sessions.
  const handlePaletteSystemAction = useCallback(
    (action: SystemAction) => {
      void runAction(action);
      navigate("/sessions");
    },
    [runAction, navigate],
  );

  // `dashboard.show_token_analytics` gates the Analytics nav item.  The
  // page itself remains reachable by URL (it renders an explanation when
  // the flag is off — see AnalyticsPage), but hiding the nav entry avoids
  // surfacing misleading token/cost numbers in the sidebar.  Default off.
  const [showTokenAnalytics, setShowTokenAnalytics] = useState(false);
  useEffect(() => {
    api
      .getConfig()
      .then((cfg) => {
        const dash = (cfg?.dashboard ?? {}) as { show_token_analytics?: unknown };
        setShowTokenAnalytics(dash.show_token_analytics === true);
      })
      .catch(() => setShowTokenAnalytics(false));
  }, []);

  // A plugin can replace the built-in /chat page via `tab.override: "/chat"`
  // in its manifest.  When one does, `buildRoutes` already swaps the route
  // element for <PluginPage /> — but we also have to suppress the
  // persistent ChatPage host below, or the plugin's page and the built-in
  // terminal would paint on top of each other.  The override is niche
  // (nothing ships overriding /chat today) but it's an advertised
  // extension point, so preserve the pre-persistence contract: when a
  // plugin owns /chat, the built-in chat UI is entirely absent.
  //
  // Waiting on `pluginsLoading` is load-bearing: manifests arrive
  // asynchronously from /api/dashboard/plugins, so on initial render
  // `chatOverriddenByPlugin` is always false.  Without the loading
  // gate, the persistent host would mount, spawn a PTY, and THEN get
  // yanked out from under the user when the plugin's manifest resolves
  // — killing the session mid-paint.  Delaying host mount by the
  // plugin-load window (typically <50ms, worst case 2s safety timeout)
  // is the cheaper trade-off.
  const chatOverriddenByPlugin = useMemo(
    () => manifests.some((m) => m.tab.override === "/chat"),
    [manifests],
  );

  const builtinRoutes = useMemo(
    () => ({
      ...BUILTIN_ROUTES_CORE,
      ...(embeddedChat ? { "/chat": ChatRouteSink } : {}),
    }),
    [embeddedChat],
  );

  const builtinNav = useMemo(() => {
    const base = embeddedChat
      ? [CHAT_NAV_ITEM, ...BUILTIN_NAV_REST]
      : BUILTIN_NAV_REST;
    return showTokenAnalytics ? base : base.filter((n) => n.path !== "/analytics");
  }, [embeddedChat, showTokenAnalytics]);

  const sidebarNav = useMemo(
    () => partitionSidebarNav(builtinNav, manifests),
    [builtinNav, manifests],
  );
  // Resolve hub sections against the merged built-in nav by path. Paths
  // missing from coreItems (analytics flag off, embedded chat disabled)
  // simply drop out; plugin tabs stay in their own group below.
  const navSections = useMemo(
    () =>
      NAV_SECTIONS.map((section) => ({
        ...section,
        items: section.paths
          .map((p) => sidebarNav.coreItems.find((i) => i.path === p))
          .filter((i): i is NavItem => i != null),
      })).filter((section) => section.items.length > 0),
    [sidebarNav.coreItems],
  );
  const routes = useMemo(
    () => buildRoutes(builtinRoutes, manifests),
    [builtinRoutes, manifests],
  );
  const pluginTabMeta = useMemo(
    () =>
      manifests
        .filter((m) => !m.tab.hidden)
        .map((m) => ({
          path: m.tab.override ?? m.tab.path,
          label: m.label,
        })),
    [manifests],
  );

  const layoutVariant = theme.layoutVariant ?? "standard";

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [mobileOpen]);

  useEffect(() => {
    const mql = window.matchMedia("(min-width: 1024px)");
    const onChange = (e: MediaQueryListEvent) => {
      if (e.matches) setMobileOpen(false);
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return (
    <div
      data-layout-variant={layoutVariant}
      className="flex h-dvh max-h-dvh min-h-0 flex-col overflow-hidden bg-background-base text-midground antialiased"
    >
      <SelectionSwitcher />
      <Backdrop />
      <ObservatoryCanvas />
      <CursorRing />
      <BootSplash />
      <PluginSlot name="backdrop" />
      <CrossSpaBanner />

      <header
        className={cn(
          "lg:hidden fixed top-0 left-0 right-0 z-40 min-h-14",
          "flex items-center gap-2 px-4 py-2",
          "border-b border-current/20",
          "bg-background-base/90 backdrop-blur-sm",
        )}
        style={{
          background: "var(--component-header-background)",
          borderImage: "var(--component-header-border-image)",
          clipPath: "var(--component-header-clip-path)",
        }}
      >
        <Button
          ghost
          size="icon"
          onClick={() => setMobileOpen(true)}
          aria-label={t.app.openNavigation}
          aria-expanded={mobileOpen}
          aria-controls="app-sidebar"
          className="text-midground/70 hover:text-midground"
          data-magnetic
        >
          <Menu />
        </Button>

        <span className="muse-wordmark font-display font-bold text-[0.95rem] leading-none tracking-[0.04em] text-midground">
          M.U.S.E.
        </span>
      </header>

      {mobileOpen && (
        <Button
          ghost
          aria-label={t.app.closeNavigation}
          onClick={closeMobile}
          className={cn(
            "lg:hidden fixed inset-0 z-40 p-0 block",
            "bg-black/60 backdrop-blur-sm",
          )}
        />
      )}

      <PluginSlot name="header-banner" />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden pt-14 lg:pt-0">
        <div className="flex min-h-0 min-w-0 flex-1">
          <aside
            id="app-sidebar"
            aria-label={t.app.navigation}
            className={cn(
              "fixed top-0 left-0 z-50 flex h-dvh max-h-dvh w-64 min-h-0 flex-col",
              "border-r border-current/20",
              "bg-background-base/95 backdrop-blur-sm",
              "transition-transform duration-200 ease-out",
              mobileOpen ? "translate-x-0" : "-translate-x-full",
              "lg:sticky lg:top-0 lg:translate-x-0 lg:shrink-0",
            )}
            style={{
              background: "var(--component-sidebar-background)",
              clipPath: "var(--component-sidebar-clip-path)",
              borderImage: "var(--component-sidebar-border-image)",
            }}
          >
            <div
              className={cn(
                "flex h-14 shrink-0 items-center justify-between gap-2 px-4",
                "border-b border-current/20",
              )}
            >
              <div className="flex min-w-0 items-baseline gap-2">
                <PluginSlot name="header-left" />

                <span className="muse-wordmark font-display font-bold text-[1.125rem] leading-none tracking-[0.04em] text-midground">
                  M.U.S.E.
                </span>
                <span aria-hidden className="muse-status-dot shrink-0 self-center" />
                {version != null && (
                  <span
                    className="shrink-0 font-mono text-[11px]"
                    style={{ color: "var(--fg-faint)" }}
                  >
                    v{version}
                  </span>
                )}
              </div>

              <Button
                ghost
                size="icon"
                onClick={closeMobile}
                aria-label={t.app.closeNavigation}
                className="lg:hidden text-midground/70 hover:text-midground"
                data-magnetic
              >
                <X />
              </Button>
            </div>

            <nav
              className="min-h-0 w-full flex-1 overflow-y-auto overflow-x-hidden border-t border-current/10 py-2"
              aria-label={t.app.navigation}
            >
              {navSections.map((section, sectionIdx) => (
                <div
                  key={section.id}
                  role="group"
                  aria-label={section.label}
                  className={cn("flex flex-col", sectionIdx > 0 && "mt-1")}
                >
                  <span
                    className="block px-5 pb-1 pt-2.5 text-[11px] font-medium"
                    style={{ color: "var(--fg-faint)" }}
                  >
                    {section.label}
                  </span>
                  <ul className="flex flex-col">
                    {section.items.map((item) => (
                      <SidebarNavLink
                        closeMobile={closeMobile}
                        item={item}
                        key={item.path}
                        t={t}
                      />
                    ))}
                  </ul>
                </div>
              ))}

              {sidebarNav.pluginItems.length > 0 && (
                <div
                  aria-labelledby="hermes-sidebar-plugin-nav-heading"
                  className="flex flex-col border-t border-current/10 pb-2"
                  role="group"
                >
                  <span
                    className="block px-5 pb-1 pt-2.5 text-[11px] font-medium"
                    style={{ color: "var(--fg-faint)" }}
                    id="hermes-sidebar-plugin-nav-heading"
                  >
                    {t.app.pluginNavSection}
                  </span>

                  <ul className="flex flex-col">
                    {sidebarNav.pluginItems.map((item) => (
                      <SidebarNavLink
                        closeMobile={closeMobile}
                        item={item}
                        key={item.path}
                        t={t}
                      />
                    ))}
                  </ul>
                </div>
              )}
            </nav>

            <SidebarSystemActions onNavigate={closeMobile} />

            <div
              className={cn(
                "flex shrink-0 items-center justify-between gap-2",
                "px-3 py-2",
                "border-t border-current/20",
              )}
            >
              <div className="flex min-w-0 items-center gap-2">
                <PluginSlot name="header-right" />
                <ThemeSwitcher dropUp />
                <LanguageSwitcher dropUp />
              </div>
            </div>

            <SidebarFooter />
          </aside>

          <PageHeaderProvider pluginTabs={pluginTabMeta}>
            <div
              className={cn(
                "relative z-10 flex min-w-0 min-h-0 flex-1 flex-col",
                "px-3 sm:px-6",
                isChatRoute
                  ? "pb-0 pt-1 sm:pt-2 lg:pt-4"
                  : "pt-2 sm:pt-4 lg:pt-6",
                isDocsRoute && "min-h-0 flex-1",
              )}
            >
              <PluginSlot name="pre-main" />
              <div
                key={pathname}
                className={cn(
                  "muse-route-enter w-full min-w-0",
                  !isChatRoute &&
                    "pb-[calc(2rem+env(safe-area-inset-bottom,0px))] lg:pb-8",
                  (isDocsRoute || isChatRoute) &&
                    "min-h-0 flex flex-1 flex-col",
                )}
              >
                <Routes>
                  {routes.map(({ key, path, element }) => (
                    <Route key={key} path={path} element={element} />
                  ))}
                  <Route
                    path="*"
                    element={
                      <UnknownRouteFallback pluginsLoading={pluginsLoading} />
                    }
                  />
                </Routes>
              </div>

              {/* Persistent chat host lives OUTSIDE the pathname-keyed
                  route container above — keying remounts on every route
                  change, and remounting the host would kill the PTY,
                  WebSocket, and xterm instance it exists to preserve. */}
              {embeddedChat &&
                  !chatOverriddenByPlugin &&
                  (pluginsLoading ? (
                    isChatRoute ? (
                      <div
                        className="flex min-h-0 min-w-0 flex-1 items-center justify-center"
                        aria-busy="true"
                        aria-live="polite"
                      >
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Spinner />
                          <span>Loading chat…</span>
                        </div>
                      </div>
                    ) : null
                  ) : (
                    <div
                      data-chat-active={isChatRoute ? "true" : "false"}
                      className={cn(
                        "min-h-0 min-w-0",
                        isChatRoute ? "flex flex-1 flex-col" : "hidden",
                      )}
                      aria-hidden={!isChatRoute}
                    >
                      <ChatPage isActive={isChatRoute} />
                    </div>
                  ))}
              <PluginSlot name="post-main" />
            </div>
          </PageHeaderProvider>
        </div>
      </div>

      <PluginSlot name="overlay" />
      <MuseChatBox />
      <CommandPalette onSystemAction={handlePaletteSystemAction} />
    </div>
  );
}

function SidebarNavLink({ closeMobile, item, t }: SidebarNavLinkProps) {
  const { path, label, labelKey, icon: Icon } = item;

  const navLabel = labelKey
    ? ((t.app.nav as Record<string, string>)[labelKey] ?? label)
    : label;

  return (
    <li>
      <NavLink
        to={path}
        end={path === "/sessions"}
        onClick={closeMobile}
        data-magnetic
        className={cn(
          "group relative flex items-center gap-3",
          "px-5 py-2.5",
          "text-[13px] leading-5",
          "whitespace-nowrap transition-colors cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground",
        )}
        style={({ isActive }) => ({
          clipPath: "var(--component-tab-clip-path)",
          background: isActive ? "var(--bg-mute)" : undefined,
          color: isActive ? "var(--fg)" : "var(--fg-dim)",
        })}
      >
        {({ isActive }) => (
          <>
            <Icon className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{navLabel}</span>

            {!isActive && (
              <span
                aria-hidden
                className="absolute inset-y-0.5 left-1.5 right-1.5 opacity-0 pointer-events-none transition-opacity duration-200 group-hover:opacity-100"
                style={{ background: "var(--bg-mute)" }}
              />
            )}

            {isActive && (
              <span
                aria-hidden
                className="absolute left-0 top-0 bottom-0 w-0.5"
                style={{ background: "var(--accent)" }}
              />
            )}
          </>
        )}
      </NavLink>
    </li>
  );
}

function SidebarSystemActions({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { activeAction, isBusy, isRunning, pendingAction, runAction } =
    useSystemActions();

  const items: SystemActionItem[] = [
    {
      action: "restart",
      icon: RotateCw,
      label: t.status.restartGateway,
      runningLabel: t.status.restartingGateway,
      spin: true,
    },
    {
      action: "update",
      icon: Download,
      label: t.status.updateHermes,
      runningLabel: t.status.updatingHermes,
      spin: false,
    },
  ];

  const handleClick = (action: SystemAction) => {
    if (isBusy) return;
    void runAction(action);
    navigate("/sessions");
    onNavigate();
  };

  return (
    <div
      className={cn(
        "shrink-0 flex flex-col",
        "border-t border-current/10",
        "py-1",
      )}
    >
      <span
        className="block px-5 pb-1 pt-2 text-[11px] font-medium"
        style={{ color: "var(--fg-faint)" }}
      >
        {t.app.system}
      </span>

      <SidebarStatusStrip />

      <ul className="flex flex-col">
        {items.map(({ action, icon: Icon, label, runningLabel, spin }) => {
          const isPending = pendingAction === action;
          const isActionRunning =
            activeAction === action && isRunning && !isPending;
          const busy = isPending || isActionRunning;
          const displayLabel = isActionRunning ? runningLabel : label;
          const disabled = isBusy && !busy;

          return (
            <li key={action}>
              <ListItem
                onClick={() => handleClick(action)}
                disabled={disabled}
                aria-busy={busy}
                active={busy}
                className={cn(
                  "gap-3 px-5 py-1.5 whitespace-nowrap",
                  "text-[13px]",
                  "transition-opacity",
                  busy
                    ? "text-midground opacity-100"
                    : "opacity-60 hover:opacity-100",
                  "disabled:opacity-30",
                )}
              >
                {isPending ? (
                  <Spinner className="shrink-0 text-[0.875rem]" />
                ) : isActionRunning && spin ? (
                  <Spinner className="shrink-0 text-[0.875rem]" />
                ) : (
                  <Icon
                    className={cn(
                      "h-3.5 w-3.5 shrink-0",
                      isActionRunning && !spin && "animate-pulse",
                    )}
                  />
                )}

                <span className="truncate">{displayLabel}</span>

                <span
                  aria-hidden
                  className="absolute inset-y-0.5 left-1.5 right-1.5 bg-midground opacity-0 pointer-events-none transition-opacity duration-200 group-hover:opacity-5"
                />

                {busy && (
                  <span
                    aria-hidden
                    className="absolute left-0 top-0 bottom-0 w-px bg-midground"
                    style={{ mixBlendMode: "plus-lighter" }}
                  />
                )}
              </ListItem>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface NavItem {
  icon: ComponentType<{ className?: string }>;
  label: string;
  labelKey?: string;
  path: string;
}

interface SidebarNavLinkProps {
  closeMobile: () => void;
  item: NavItem;
  t: Translations;
}

interface SystemActionItem {
  action: SystemAction;
  icon: ComponentType<{ className?: string }>;
  label: string;
  runningLabel: string;
  spin: boolean;
}
