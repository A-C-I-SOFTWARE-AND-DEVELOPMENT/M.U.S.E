/**
 * ChatPage — persistent host for the dashboard's /chat tab.
 *
 * Two modes share the tab:
 *
 *   "chat"     — ChatMode: a full-page conversational chat with the muse
 *                agent over the tui_gateway JSON-RPC sidecar (the tab's
 *                centerpiece; Markdown transcript, streaming, slash
 *                commands). See components/chat/ChatMode.tsx.
 *   "terminal" — TerminalMode: the embedded `hermes --tui` PTY via
 *                xterm.js, with the model/tools sidebar. See
 *                components/chat/TerminalMode.tsx.
 *
 * App.tsx renders this host persistently (outside <Routes>) so nothing
 * here unmounts on tab switches. Mode switches likewise keep both modes
 * mounted: ChatMode stays mounted from the start (it owns the gateway
 * session + transcript in React state), and TerminalMode mounts lazily
 * the first time it is selected, then stays mounted so the PTY child,
 * WebSocket, and xterm instance survive. Inactive modes are hidden with
 * display:none; each mode receives `isActive` = tab-active && selected.
 *
 * `/chat?resume=<id>` (resume-in-chat from the Sessions page) forces the
 * terminal mode, which owns PTY resume semantics.
 */

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { MessageSquare, Terminal as TerminalIcon } from "lucide-react";

import {
  ChatMode,
  ChatSigil,
  type ChatModeStatus,
} from "@/components/chat/ChatMode";
import { TerminalMode } from "@/components/chat/TerminalMode";
import type { ConnectionState } from "@/lib/gatewayClient";
import { cn } from "@/lib/utils";
import { PluginSlot } from "@/plugins";

type ChatPageMode = "chat" | "terminal";

const DOT_COLOR: Record<ConnectionState, string> = {
  idle: "var(--fg-faint)",
  connecting: "var(--warn)",
  open: "var(--ok)",
  closed: "var(--fg-faint)",
  error: "var(--err)",
};

function shortModel(model: string): string {
  const parts = model.split("/");
  return parts[parts.length - 1] || model;
}

export default function ChatPage({ isActive = true }: { isActive?: boolean }) {
  const [searchParams] = useSearchParams();
  const resumeParam = searchParams.get("resume");

  const [mode, setMode] = useState<ChatPageMode>(() =>
    resumeParam ? "terminal" : "chat",
  );
  // TerminalMode mounts lazily on first selection so the PTY child only
  // spawns when the user actually wants the terminal.
  const [terminalMounted, setTerminalMounted] = useState(
    () => resumeParam !== null,
  );
  const [chatStatus, setChatStatus] = useState<ChatModeStatus>({
    connState: "idle",
    model: null,
    provider: null,
    sessionId: null,
  });

  // Resume-in-chat targets the PTY session — switch to terminal mode.
  useEffect(() => {
    if (resumeParam) setMode("terminal");
  }, [resumeParam]);

  useEffect(() => {
    if (mode === "terminal") setTerminalMounted(true);
  }, [mode]);

  const handleChatStatus = useCallback((s: ChatModeStatus) => {
    setChatStatus(s);
  }, []);

  const chatActive = isActive && mode === "chat";
  const terminalActive = isActive && mode === "terminal";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 normal-case">
      <PluginSlot name="chat:top" />

      {/* Tab strip — wordmark + live session state + mode toggle */}
      <div
        className="flex h-10 shrink-0 items-center gap-2.5 border-b px-1 sm:px-2"
        style={{
          borderColor: "color-mix(in srgb, var(--midground-base) 8%, transparent)",
        }}
      >
        <ChatSigil className="h-4 w-4 shrink-0" />
        <span className="font-display text-[0.85rem] font-bold leading-none tracking-[0.04em] text-midground">
          M.U.S.E.
        </span>

        {mode === "chat" && (
          <>
            <span
              aria-hidden
              className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ background: DOT_COLOR[chatStatus.connState] }}
            />
            <span
              className="hidden min-w-0 truncate font-mono-ui text-[0.65rem] tracking-[0.06em] min-[420px]:inline"
              style={{ color: "var(--fg-faint)" }}
              title={
                chatStatus.sessionId
                  ? `session ${chatStatus.sessionId}`
                  : undefined
              }
            >
              {chatStatus.model
                ? `${shortModel(chatStatus.model)}${
                    chatStatus.provider ? ` · ${chatStatus.provider}` : ""
                  }${chatStatus.sessionId ? ` · ${chatStatus.sessionId.slice(0, 8)}` : ""}`
                : chatStatus.connState === "open"
                  ? "ready"
                  : chatStatus.connState === "connecting"
                    ? "connecting"
                    : chatStatus.connState === "error"
                      ? "offline"
                      : ""}
            </span>
          </>
        )}

        <div
          role="tablist"
          aria-label="Chat mode"
          className="ml-auto flex shrink-0 items-center gap-0.5 rounded-md border p-0.5"
          style={{
            borderColor: "color-mix(in srgb, var(--midground-base) 12%, transparent)",
            background: "var(--bg-elev)",
          }}
        >
          <ModeTab
            active={mode === "chat"}
            onSelect={() => setMode("chat")}
            icon={<MessageSquare className="h-3 w-3" />}
            label="Chat"
          />
          <ModeTab
            active={mode === "terminal"}
            onSelect={() => setMode("terminal")}
            icon={<TerminalIcon className="h-3 w-3" />}
            label="Terminal"
          />
        </div>
      </div>

      {/* Modes — both stay mounted once created; display:none hides the
          inactive one so gateway session, transcript, PTY child, and xterm
          instance all survive mode toggles and tab switches. */}
      <div
        className={cn("min-h-0 min-w-0", mode === "chat" ? "flex flex-1 flex-col" : "hidden")}
        aria-hidden={mode !== "chat"}
      >
        <ChatMode isActive={chatActive} onStatus={handleChatStatus} />
      </div>
      {terminalMounted && (
        <div
          className={cn(
            "min-h-0 min-w-0",
            mode === "terminal" ? "flex flex-1 flex-col" : "hidden",
          )}
          aria-hidden={mode !== "terminal"}
        >
          <TerminalMode isActive={terminalActive} />
        </div>
      )}

      <PluginSlot name="chat:bottom" />
    </div>
  );
}

function ModeTab({
  active,
  onSelect,
  icon,
  label,
}: {
  active: boolean;
  onSelect: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onSelect}
      className={cn(
        "muse-press inline-flex items-center gap-1.5 rounded px-2.5 py-1",
        "text-[0.68rem] font-medium tracking-[0.05em] transition-colors",
      )}
      style={
        active
          ? {
              background: "color-mix(in srgb, var(--accent) 12%, transparent)",
              color: "var(--fg)",
            }
          : { color: "var(--fg-dim)" }
      }
    >
      {icon}
      {label}
    </button>
  );
}
