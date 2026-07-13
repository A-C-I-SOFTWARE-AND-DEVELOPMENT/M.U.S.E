/**
 * Dock quick-commands — the single source of the dock's input bindings.
 *
 * The floating MUSE dock is driven by a small, fixed set of "quick commands."
 * Every dock action is one of these, and each is bound BOTH to a click target
 * (a button in the dock chrome) and to a keyboard chord, so the mouse and the
 * keyboard drive exactly the same command set. This module owns *what triggers*
 * a command (ids, labels, key hints, and the KeyboardEvent → id matcher); the
 * Dock component owns *what each command does*. Keeping the binding here means
 * the chrome buttons and the global key handler can never drift apart.
 */

export type DockCommandId =
  | "toggle"
  | "minimize"
  | "clear"
  | "focusInput"
  | "close"
  | "send";

export type DockCommand = {
  id: DockCommandId;
  /** Human label — button text / tooltip. */
  label: string;
  /** Display string for the bound chord, e.g. "Ctrl/⌘ + `". */
  hint: string;
  /** Whether this command is exposed as a clickable button in the dock chrome. */
  inChrome: boolean;
};

/** The fixed quick-command set, in chrome display order. */
export const DOCK_COMMANDS: readonly DockCommand[] = [
  { id: "clear", label: "Clear", hint: "Ctrl/⌘ + ⇧ + K", inChrome: true },
  { id: "minimize", label: "Minimize", hint: "Ctrl/⌘ + ⇧ + M", inChrome: true },
  { id: "close", label: "Close", hint: "Esc", inChrome: true },
  { id: "toggle", label: "Toggle dock", hint: "Ctrl/⌘ + `", inChrome: false },
  { id: "focusInput", label: "Focus input", hint: "Ctrl/⌘ + /", inChrome: false },
  { id: "send", label: "Send", hint: "Enter", inChrome: false },
] as const;

/** Commands rendered as buttons in the dock title bar. */
export const DOCK_CHROME_COMMANDS = DOCK_COMMANDS.filter((c) => c.inChrome);

const hasMod = (e: KeyboardEvent): boolean => e.metaKey || e.ctrlKey;

/**
 * Map a *global* keydown to a dock command id, or null. Global chords work from
 * anywhere in the app (not just when the composer is focused): toggle / minimize
 * / clear / focusInput. `send` and `close` are composer-local — they are handled
 * by the textarea's own onKeyDown so they don't hijack Enter/Esc app-wide.
 */
export function matchGlobalDockCommand(e: KeyboardEvent): DockCommandId | null {
  if (!hasMod(e) || e.altKey) return null;
  // Backtick toggles regardless of Shift — some layouts put ` behind Shift.
  if (e.key === "`") return "toggle";
  if (e.shiftKey && (e.key === "M" || e.key === "m")) return "minimize";
  if (e.shiftKey && (e.key === "K" || e.key === "k")) return "clear";
  if (!e.shiftKey && e.key === "/") return "focusInput";
  return null;
}
