import {
  useEffect,
  useLayoutEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Database,
  MessageSquare,
  Search,
  Trash2,
  Clock,
  Terminal,
  Globe,
  MessageCircle,
  Hash,
  X,
  Play,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  SessionInfo,
  SessionMessage,
  SessionSearchResult,
  StatusResponse,
} from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { Markdown } from "@/components/Markdown";
import { PlatformsCard } from "@/components/PlatformsCard";
import { Toast } from "@/components/Toast";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyStateCard } from "@/components/EmptyStateCard";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { useConfirmDelete } from "@/hooks/useConfirmDelete";
import { Input } from "@/components/ui/input";
import { useSystemActions } from "@/contexts/useSystemActions";
import { useToast } from "@/hooks/useToast";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";
import { isDashboardEmbeddedChatEnabled } from "@/lib/dashboard-flags";

const SOURCE_CONFIG: Record<string, { icon: typeof Terminal; color: string }> =
  {
    cli: { icon: Terminal, color: "text-[var(--accent)]" },
    telegram: { icon: MessageCircle, color: "text-[var(--info)]" },
    discord: { icon: Hash, color: "text-[var(--accent-dim)]" },
    slack: { icon: MessageSquare, color: "text-[var(--ok)]" },
    whatsapp: { icon: Globe, color: "text-[var(--ok)]" },
    cron: { icon: Clock, color: "text-[var(--warn)]" },
  };

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/** Render an FTS5 snippet with highlighted matches.
 *  The backend wraps matches in >>> and <<< delimiters. */
function SnippetHighlight({ snippet }: { snippet: string }) {
  const parts: React.ReactNode[] = [];
  const regex = />>>(.*?)<<</g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(snippet)) !== null) {
    if (match.index > last) {
      parts.push(snippet.slice(last, match.index));
    }
    parts.push(
      <mark
        key={i++}
        className="bg-[var(--warn)]/25 px-0.5 text-[var(--warn)]"
      >
        {match[1]}
      </mark>,
    );
    last = regex.lastIndex;
  }
  if (last < snippet.length) {
    parts.push(snippet.slice(last));
  }
  return (
    <p className="mt-0.5 min-w-0 max-w-full truncate text-xs text-[var(--fg-dim)]">
      {parts}
    </p>
  );
}

function ToolCallBlock({
  toolCall,
}: {
  toolCall: { id: string; function: { name: string; arguments: string } };
}) {
  const [open, setOpen] = useState(false);
  const { t } = useI18n();

  let args = toolCall.function.arguments;
  try {
    args = JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    // keep as-is
  }

  return (
    <div className="mt-2 rounded-lg border border-[var(--warn)]/20 bg-[var(--warn)]/5">
      <ListItem
        onClick={() => setOpen(!open)}
        aria-label={`${open ? t.common.collapse : t.common.expand} tool call ${toolCall.function.name}`}
        aria-expanded={open}
        className="px-3 py-2 text-xs text-[var(--warn)] hover:bg-[var(--warn)]/10 hover:text-[var(--warn)]"
      >
        {open ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span className="font-mono font-medium">{toolCall.function.name}</span>
        <span className="ml-auto text-[var(--warn)]/50">{toolCall.id}</span>
      </ListItem>
      {open && (
        <pre className="overflow-x-auto whitespace-pre-wrap border-t border-[var(--warn)]/20 px-3 py-2 font-mono text-xs text-[var(--warn)]/80">
          {args}
        </pre>
      )}
    </div>
  );
}

function MessageBubble({
  msg,
  highlight,
}: {
  msg: SessionMessage;
  highlight?: string;
}) {
  const { t } = useI18n();

  const ROLE_STYLES: Record<
    string,
    { bg: string; text: string; label: string }
  > = {
    user: {
      bg: "bg-[var(--accent)]/10",
      text: "text-[var(--accent)]",
      label: t.sessions.roles.user,
    },
    assistant: {
      bg: "bg-[var(--ok)]/10",
      text: "text-[var(--ok)]",
      label: t.sessions.roles.assistant,
    },
    system: {
      bg: "bg-[var(--bg-mute)]",
      text: "text-[var(--fg-dim)]",
      label: t.sessions.roles.system,
    },
    tool: {
      bg: "bg-[var(--warn)]/10",
      text: "text-[var(--warn)]",
      label: t.sessions.roles.tool,
    },
  };

  const style = ROLE_STYLES[msg.role] ?? ROLE_STYLES.system;
  const label = msg.tool_name
    ? `${t.sessions.roles.tool}: ${msg.tool_name}`
    : style.label;

  // Check if any search term appears as a prefix of any word in content
  const isHit = (() => {
    if (!highlight || !msg.content) return false;
    const content = msg.content.toLowerCase();
    const terms = highlight.toLowerCase().split(/\s+/).filter(Boolean);
    return terms.some((term) => content.includes(term));
  })();

  // Split search query into terms for inline highlighting
  const highlightTerms =
    isHit && highlight ? highlight.split(/\s+/).filter(Boolean) : undefined;

  return (
    <div
      className={`${style.bg} rounded-lg p-3 ${isHit ? "ring-1 ring-[var(--warn)]/40" : ""}`}
      data-search-hit={isHit || undefined}
    >
      <div className="mb-1 flex items-center gap-2">
        <span className={`text-xs font-semibold ${style.text}`}>{label}</span>
        {isHit && (
          <Badge tone="warning" className="px-1.5 py-0 text-[9px]">
            {t.common.match}
          </Badge>
        )}
        {msg.timestamp && (
          <span className="text-[10px] text-[var(--fg-faint)]">
            {timeAgo(msg.timestamp)}
          </span>
        )}
      </div>
      {msg.content &&
        (msg.role === "system" ? (
          <div className="text-sm leading-relaxed whitespace-pre-wrap text-[var(--fg)]">
            {msg.content}
          </div>
        ) : (
          <Markdown content={msg.content} highlightTerms={highlightTerms} />
        ))}
      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <div className="mt-1">
          {msg.tool_calls.map((tc) => (
            <ToolCallBlock key={tc.id} toolCall={tc} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Message list with auto-scroll to first search hit. */
function MessageList({
  messages,
  highlight,
}: {
  messages: SessionMessage[];
  highlight?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!highlight || !containerRef.current) return;
    // Scroll to first hit after render
    const timer = setTimeout(() => {
      const hit = containerRef.current?.querySelector("[data-search-hit]");
      if (hit) {
        hit.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 50);
    return () => clearTimeout(timer);
  }, [messages, highlight]);

  return (
    <div
      ref={containerRef}
      className="flex max-h-[600px] flex-col gap-3 overflow-y-auto pr-2"
    >
      {messages.map((msg, i) => (
        <MessageBubble key={i} msg={msg} highlight={highlight} />
      ))}
    </div>
  );
}

/** bgElev session card: title, dim preview, faint metadata, hover actions. */
function SessionRow({
  session,
  snippet,
  searchQuery,
  isExpanded,
  onToggle,
  onDelete,
  resumeInChatEnabled,
}: {
  session: SessionInfo;
  snippet?: string;
  searchQuery?: string;
  isExpanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  resumeInChatEnabled: boolean;
}) {
  const [messages, setMessages] = useState<SessionMessage[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();
  const navigate = useNavigate();

  useEffect(() => {
    if (isExpanded && messages === null && !loading) {
      setLoading(true);
      api
        .getSessionMessages(session.id)
        .then((resp) => setMessages(resp.messages))
        .catch((err) => setError(String(err)))
        .finally(() => setLoading(false));
    }
  }, [isExpanded, session.id, messages, loading]);

  const sourceInfo = (session.source
    ? SOURCE_CONFIG[session.source]
    : null) ?? { icon: Globe, color: "text-[var(--fg-dim)]" };
  const SourceIcon = sourceInfo.icon;
  const hasTitle = session.title && session.title !== "Untitled";
  const totalTokens = session.input_tokens + session.output_tokens;

  return (
    <div
      className={`group max-w-full min-w-0 overflow-hidden rounded-xl border bg-[var(--bg-elev)] transition-colors ${
        session.is_active
          ? "border-[var(--ok)]/40"
          : "border-[var(--border)] hover:border-[var(--accent-dim)]/50"
      }`}
    >
      <div
        className="flex cursor-pointer items-start gap-3 p-3 transition-colors hover:bg-[var(--bg-mute)]/50"
        onClick={onToggle}
      >
        <div className={`shrink-0 pt-0.5 ${sourceInfo.color}`}>
          <SourceIcon className="h-4 w-4" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex min-w-0 items-center gap-2">
            <span
              className={`min-w-0 flex-1 truncate text-sm ${
                hasTitle
                  ? "font-medium text-[var(--fg)]"
                  : "text-[var(--fg-dim)] italic"
              }`}
            >
              {hasTitle ? session.title : t.sessions.untitledSession}
            </span>
            {session.is_active && (
              <Badge tone="success" className="shrink-0 text-[10px]">
                <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
                {t.common.live}
              </Badge>
            )}
            {/* Hover actions — always visible on touch, fade in on desktop hover */}
            <span className="flex shrink-0 items-center gap-1 transition-opacity sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100">
              {resumeInChatEnabled && (
                <Button
                  ghost
                  size="icon"
                  className="text-[var(--fg-dim)] hover:text-[var(--ok)]"
                  aria-label={t.sessions.resumeInChat}
                  title={t.sessions.resumeInChat}
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/chat?resume=${encodeURIComponent(session.id)}`);
                  }}
                >
                  <Play />
                </Button>
              )}
              <Button
                ghost
                destructive
                size="icon"
                aria-label={t.sessions.deleteSession}
                title={t.sessions.deleteSession}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
              >
                <Trash2 />
              </Button>
            </span>
          </div>

          {session.preview && (
            <p className="min-w-0 max-w-full truncate text-xs text-[var(--fg-dim)]">
              {session.preview}
            </p>
          )}

          <div className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-[var(--fg-faint)]">
            <span className="max-w-[min(100%,12rem)] truncate font-mono sm:max-w-[180px]">
              {(session.model ?? t.common.unknown).split("/").pop()}
            </span>
            <span>&#183;</span>
            <span className="shrink-0 tabular-nums">
              {session.message_count} {t.common.msgs}
            </span>
            <span>&#183;</span>
            <span className="shrink-0 tabular-nums">
              {formatTokens(totalTokens)} {t.analytics.tokens.toLowerCase()}
            </span>
            <span>&#183;</span>
            <span className="shrink-0">{timeAgo(session.last_active)}</span>
            <span className="ml-auto shrink-0">
              <Badge tone="outline" className="text-[10px]">
                {session.source ?? "local"}
              </Badge>
            </span>
          </div>

          {snippet && <SnippetHighlight snippet={snippet} />}
        </div>
      </div>

      {isExpanded && (
        <div className="min-w-0 border-t border-[var(--border)] p-4">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Spinner className="text-xl text-[var(--accent)]" />
            </div>
          )}
          {error && (
            <p className="py-4 text-center text-sm text-[var(--err)]">
              {error}
            </p>
          )}
          {messages && messages.length === 0 && (
            <p className="py-4 text-center text-sm text-[var(--fg-dim)]">
              {t.sessions.noMessages}
            </p>
          )}
          {messages && messages.length > 0 && (
            <MessageList messages={messages} highlight={searchQuery} />
          )}
        </div>
      )}
    </div>
  );
}

/** Pulse placeholder matching the session-card shape (design 2.3: skeletons, not spinner storms). */
function SessionRowSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-3">
      <div className="flex items-start gap-3">
        <div className="h-4 w-4 shrink-0 rounded bg-[var(--bg-mute)]" />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="h-3.5 w-2/5 rounded bg-[var(--bg-mute)]" />
          <div className="h-3 w-3/4 rounded bg-[var(--bg-mute)]" />
          <div className="h-2.5 w-1/3 rounded bg-[var(--bg-mute)]" />
        </div>
      </div>
    </div>
  );
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<
    SessionSearchResult[] | null
  >(null);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);
  const logScrollRef = useRef<HTMLPreElement | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [overviewSessions, setOverviewSessions] = useState<SessionInfo[]>([]);
  const { toast, showToast } = useToast();
  const { t } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();
  const { activeAction, actionStatus, dismissLog } = useSystemActions();
  const resumeInChatEnabled = isDashboardEmbeddedChatEnabled();

  useLayoutEffect(() => {
    if (loading) {
      setAfterTitle(null);
      setEnd(null);
      return;
    }
    setAfterTitle(
      <Badge tone="secondary" className="text-xs tabular-nums">
        {total}
      </Badge>,
    );
    setEnd(
      <div className="relative w-full min-w-0 sm:max-w-xs">
        {searching ? (
          <Spinner className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[0.875rem] text-[var(--accent)]" />
        ) : (
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--fg-faint)]" />
        )}
        <Input
          placeholder={t.sessions.searchPlaceholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8 pr-7 pl-8 text-xs"
        />
        {search && (
          <Button
            ghost
            size="xs"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--fg-dim)] hover:text-[var(--fg)]"
            onClick={() => setSearch("")}
            aria-label={t.common.clear}
          >
            <X />
          </Button>
        )}
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [
    loading,
    search,
    searching,
    setAfterTitle,
    setEnd,
    t.common.clear,
    t.sessions.searchPlaceholder,
    total,
  ]);

  const loadSessions = useCallback((p: number) => {
    setLoading(true);
    api
      .getSessions(PAGE_SIZE, p * PAGE_SIZE)
      .then((resp) => {
        setSessions(resp.sessions);
        setTotal(resp.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadSessions(page);
  }, [loadSessions, page]);

  useEffect(() => {
    const loadOverview = () => {
      api
        .getStatus()
        .then(setStatus)
        .catch(() => {});
      api
        .getSessions(50)
        .then((r) => setOverviewSessions(r.sessions))
        .catch(() => {});
    };
    loadOverview();
    const id = setInterval(loadOverview, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const el = logScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [actionStatus?.lines]);

  // Debounced FTS search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!search.trim()) {
      setSearchResults(null);
      setSearching(false);
      return;
    }

    setSearching(true);
    debounceRef.current = setTimeout(() => {
      api
        .searchSessions(search.trim())
        .then((resp) => setSearchResults(resp.results))
        .catch(() => setSearchResults(null))
        .finally(() => setSearching(false));
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search]);

  const sessionDelete = useConfirmDelete({
    onDelete: useCallback(
      async (id: string) => {
        try {
          await api.deleteSession(id);
          setSessions((prev) => prev.filter((s) => s.id !== id));
          setTotal((prev) => prev - 1);
          if (expandedId === id) setExpandedId(null);
          showToast(t.sessions.sessionDeleted, "success");
        } catch {
          showToast(t.sessions.failedToDelete, "error");
          throw new Error("delete failed");
        }
      },
      [
        expandedId,
        showToast,
        t.sessions.sessionDeleted,
        t.sessions.failedToDelete,
      ],
    ),
  });

  const pendingSession = sessionDelete.pendingId
    ? sessions.find((s) => s.id === sessionDelete.pendingId)
    : null;

  // Build snippet map from search results (session_id → snippet)
  const snippetMap = new Map<string, string>();
  if (searchResults) {
    for (const r of searchResults) {
      snippetMap.set(r.session_id, r.snippet);
    }
  }

  // When searching, filter sessions to those with FTS matches;
  // when not searching, show all sessions
  const filtered = searchResults
    ? sessions.filter((s) => snippetMap.has(s.id))
    : sessions;

  const platformEntries = status
    ? Object.entries(status.gateway_platforms ?? {})
    : [];
  const recentSessions = overviewSessions
    .filter((s) => !s.is_active)
    .slice(0, 5);

  const alerts: { message: string; detail?: string }[] = [];
  if (status) {
    if (status.gateway_state === "startup_failed") {
      alerts.push({
        message: t.status.gatewayFailedToStart,
        detail: status.gateway_exit_reason ?? undefined,
      });
    }
    const failedPlatformEntries = platformEntries.filter(
      ([, info]) => info.state === "fatal" || info.state === "disconnected",
    );
    for (const [name, info] of failedPlatformEntries) {
      const stateLabel =
        info.state === "fatal"
          ? t.status.platformError
          : t.status.platformDisconnected;
      alerts.push({
        message: `${name.charAt(0).toUpperCase() + name.slice(1)} ${stateLabel}`,
        detail: info.error_message ?? undefined,
      });
    }
  }

  return (
    <div className="flex min-w-0 w-full max-w-full flex-col gap-4">
      <PluginSlot name="sessions:top" />
      <Toast toast={toast} />

      <DeleteConfirmDialog
        open={sessionDelete.isOpen}
        onCancel={sessionDelete.cancel}
        onConfirm={sessionDelete.confirm}
        title={t.sessions.confirmDeleteTitle}
        description={
          pendingSession?.title && pendingSession.title !== "Untitled"
            ? `"${pendingSession.title}" — ${t.sessions.confirmDeleteMessage}`
            : t.sessions.confirmDeleteMessage
        }
        loading={sessionDelete.isDeleting}
      />

      <p className="text-sm text-[var(--fg-dim)]">
        Browse, search, and resume your past conversations.
      </p>

      {alerts.length > 0 && (
        <div className="rounded-xl border border-[var(--err)]/30 bg-[var(--err)]/[0.06] p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-[var(--err)]" />
            <div className="flex min-w-0 flex-col gap-2">
              {alerts.map((alert, i) => (
                <div key={i}>
                  <p className="text-sm font-medium text-[var(--err)]">
                    {alert.message}
                  </p>
                  {alert.detail && (
                    <p className="mt-0.5 text-xs text-[var(--err)]/70">
                      {alert.detail}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeAction && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elev)]">
          <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              {actionStatus?.running ? (
                <Spinner className="shrink-0 text-[0.875rem] text-[var(--warn)]" />
              ) : actionStatus?.exit_code === 0 ? (
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[var(--ok)]" />
              ) : actionStatus !== null ? (
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[var(--err)]" />
              ) : (
                <Spinner className="shrink-0 text-[0.875rem] text-[var(--fg-dim)]" />
              )}

              <span className="truncate text-xs font-medium tracking-wide text-[var(--fg-dim)]">
                {activeAction === "restart"
                  ? t.status.restartGateway
                  : t.status.updateHermes}
              </span>

              <Badge
                tone={
                  actionStatus?.running
                    ? "warning"
                    : actionStatus?.exit_code === 0
                      ? "success"
                      : actionStatus
                        ? "destructive"
                        : "outline"
                }
                className="shrink-0 text-[10px]"
              >
                {actionStatus?.running
                  ? t.status.running
                  : actionStatus?.exit_code === 0
                    ? t.status.actionFinished
                    : actionStatus
                      ? `${t.status.actionFailed} (${actionStatus.exit_code ?? "?"})`
                      : t.common.loading}
              </Badge>
            </div>

            <Button
              ghost
              size="icon"
              onClick={dismissLog}
              className="shrink-0 opacity-60 hover:opacity-100"
              aria-label={t.common.close}
            >
              <X />
            </Button>
          </div>

          <pre
            ref={logScrollRef}
            className="max-h-72 overflow-auto px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-all"
          >
            {actionStatus?.lines && actionStatus.lines.length > 0
              ? actionStatus.lines.join("\n")
              : t.status.waitingForOutput}
          </pre>
        </div>
      )}

      {platformEntries.length > 0 && status && (
        <PlatformsCard platforms={platformEntries} />
      )}

      {recentSessions.length > 0 && !loading && (
        <Card className="min-w-0 max-w-full overflow-hidden rounded-xl">
          <CardHeader className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <Clock className="h-5 w-5 shrink-0 text-[var(--fg-dim)]" />
              <CardTitle className="min-w-0 truncate text-base normal-case tracking-normal">
                {t.status.recentSessions}
              </CardTitle>
            </div>
          </CardHeader>

          <CardContent className="grid min-w-0 gap-3">
            {recentSessions.map((s) => (
              <div
                key={s.id}
                className="flex min-w-0 max-w-full flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="min-w-0 truncate text-sm font-medium text-[var(--fg)]">
                    {s.title ?? t.common.untitled}
                  </span>

                  <span className="min-w-0 break-words text-xs text-[var(--fg-faint)]">
                    <span className="font-mono">
                      {(s.model ?? t.common.unknown).split("/").pop()}
                    </span>{" "}
                    · {s.message_count} {t.common.msgs} ·{" "}
                    {formatTokens(s.input_tokens + s.output_tokens)}{" "}
                    {t.analytics.tokens.toLowerCase()} ·{" "}
                    {timeAgo(s.last_active)}
                  </span>

                  {s.preview && (
                    <p className="min-w-0 max-w-full text-xs leading-snug text-[var(--fg-dim)] [overflow-wrap:anywhere]">
                      {s.preview}
                    </p>
                  )}
                </div>

                <Badge
                  tone="outline"
                  className="shrink-0 self-start text-[10px] sm:self-center"
                >
                  <Database className="mr-1 h-3 w-3" />
                  {s.source ?? "local"}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex min-w-0 flex-col gap-2">
          {Array.from({ length: 6 }, (_, i) => (
            <SessionRowSkeleton key={i} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyStateCard
          icon={Clock}
          title={search ? t.sessions.noMatch : t.sessions.noSessions}
          description={search ? undefined : t.sessions.startConversation}
        />
      ) : (
        <>
          <div className="flex min-w-0 flex-col gap-2">
            {filtered.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                snippet={snippetMap.get(s.id)}
                searchQuery={search || undefined}
                isExpanded={expandedId === s.id}
                onToggle={() =>
                  setExpandedId((prev) => (prev === s.id ? null : s.id))
                }
                onDelete={() => sessionDelete.requestDelete(s.id)}
                resumeInChatEnabled={resumeInChatEnabled}
              />
            ))}
          </div>

          {!searchResults && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-[var(--fg-dim)]">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)}{" "}
                {t.common.of} {total}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  outlined
                  size="icon"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  aria-label={t.sessions.previousPage}
                >
                  <ChevronLeft />
                </Button>
                <span className="px-2 text-xs text-[var(--fg-dim)]">
                  {t.common.page} {page + 1} {t.common.of}{" "}
                  {Math.ceil(total / PAGE_SIZE)}
                </span>
                <Button
                  outlined
                  size="icon"
                  disabled={(page + 1) * PAGE_SIZE >= total}
                  onClick={() => setPage((p) => p + 1)}
                  aria-label={t.sessions.nextPage}
                >
                  <ChevronRight />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
      <PluginSlot name="sessions:bottom" />
    </div>
  );
}
