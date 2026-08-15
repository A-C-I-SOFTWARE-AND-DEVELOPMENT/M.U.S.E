import {
  detectVSCodeLikeTerminal,
  type FileOps,
  isRemoteShellSession,
  shouldPromptForTerminalSetup
} from './terminalSetup.js'

export type MacTerminalHint = {
  key: string
  message: string
  tone: 'info' | 'warn'
}

export type MacTerminalContext = {
  isAppleTerminal: boolean
  isRemote: boolean
  isTmux: boolean
  vscodeLike: null | 'cursor' | 'vscode' | 'windsurf'
}

export function detectMacTerminalContext(env: NodeJS.ProcessEnv = process.env): MacTerminalContext {
  const termProgram = env['TERM_PROGRAM'] ?? ''

  return {
    isAppleTerminal: termProgram === 'Apple_Terminal' || !!env['TERM_SESSION_ID'],
    isRemote: isRemoteShellSession(env),
    isTmux: !!env['TMUX'],
    vscodeLike: detectVSCodeLikeTerminal(env)
  }
}

export async function terminalParityHints(
  env: NodeJS.ProcessEnv = process.env,
  // `platform` completes the seam its callee already had: shouldPrompt-
  // ForTerminalSetup takes one, but this wrapper never forwarded it, so the
  // host's platform always won. That made the hint untestable off POSIX —
  // on Windows the config dir resolves from %APPDATA% instead of homeDir.
  options?: { fileOps?: Partial<FileOps>; homeDir?: string; platform?: NodeJS.Platform }
): Promise<MacTerminalHint[]> {
  const ctx = detectMacTerminalContext(env)
  const hints: MacTerminalHint[] = []

  if (
    ctx.vscodeLike &&
    (await shouldPromptForTerminalSetup({
      env,
      fileOps: options?.fileOps,
      homeDir: options?.homeDir,
      platform: options?.platform
    }))
  ) {
    hints.push({
      key: 'ide-setup',
      tone: 'info',
      message: `Detected ${ctx.vscodeLike} terminal · run /terminal-setup for best Cmd+Enter / undo parity`
    })
  }

  if (ctx.isAppleTerminal) {
    hints.push({
      key: 'apple-terminal',
      tone: 'warn',
      message:
        'Apple Terminal detected · use /paste for image-only clipboard fallback, and try Ctrl+A / Ctrl+E / Ctrl+U if Cmd+←/→/⌫ gets rewritten'
    })
  }

  if (ctx.isTmux) {
    hints.push({
      key: 'tmux',
      tone: 'warn',
      message:
        'tmux detected · clipboard copy/paste uses passthrough when available; allow-passthrough improves OSC52 reliability'
    })
  }

  if (ctx.isRemote) {
    hints.push({
      key: 'remote',
      tone: 'warn',
      message:
        'SSH session detected · text clipboard can bridge via OSC52, but image clipboard and local screenshot paths still depend on the machine running muse'
    })
  }

  return hints
}
