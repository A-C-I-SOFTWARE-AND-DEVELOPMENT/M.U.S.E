/**
 * Trimmed, type-only vendored copy of OpenCode's session message model.
 *
 * Source of truth: sst/opencode `packages/sdk/js/src/v2/gen/types.gen.ts`
 * (the generated v2 client types) exposed by the upstream renderer as the
 * `MessageV2` namespace (`opencode/session/message-v2`). We only vendor the
 * *types* the Share-viewer renderer (`share/part.tsx`) references — they are
 * erased at build time — so MUSE controls the shape of the chat store that
 * feeds OpenCode's exact rendering components.
 *
 * Upstream is MIT licensed (see ./LICENSE). Field names/shapes are preserved
 * verbatim so the vendored components type-check unchanged.
 */

export namespace MessageV2 {
  export interface OutputFormatText {
    type: "text"
  }
  export interface OutputFormatJson {
    type: "json"
    schema?: unknown
  }
  export type OutputFormat = OutputFormatText | OutputFormatJson

  export interface SnapshotFileDiff {
    file: string
    added: number
    removed: number
    status?: string
  }

  export interface Tokens {
    total?: number
    input: number
    output: number
    reasoning: number
    cache: {
      read: number
      write: number
    }
  }

  export interface User {
    id: string
    sessionID: string
    role: "user"
    time: {
      created: number
    }
    format?: OutputFormat
    summary?: {
      title?: string
      body?: string
      diffs: Array<SnapshotFileDiff>
    }
    agent: string
    model: {
      providerID: string
      modelID: string
      variant?: string
    }
    system?: string
    tools?: {
      [key: string]: boolean
    }
  }

  export interface MessageError {
    name: string
    data: {
      message?: string
      [key: string]: unknown
    }
  }

  export interface Assistant {
    id: string
    sessionID: string
    role: "assistant"
    time: {
      created: number
      completed?: number
    }
    error?: MessageError
    parentID: string
    modelID: string
    providerID: string
    mode: string
    agent: string
    path: {
      cwd: string
      root: string
    }
    summary?: boolean
    cost: number
    tokens: Tokens
    structured?: unknown
    variant?: string
    finish?: string
  }

  export type Info = User | Assistant

  export interface TextPart {
    id: string
    sessionID: string
    messageID: string
    type: "text"
    text: string
    synthetic?: boolean
    ignored?: boolean
    time?: {
      start: number
      end?: number
    }
    metadata?: {
      [key: string]: unknown
    }
  }

  export interface ReasoningPart {
    id: string
    sessionID: string
    messageID: string
    type: "reasoning"
    text: string
    metadata?: {
      [key: string]: unknown
    }
    time: {
      start: number
      end?: number
    }
  }

  export interface FilePartSourceText {
    value: string
    start: number
    end: number
  }
  export type FilePartSource =
    | { text: FilePartSourceText; type: "file"; path: string }
    | {
        text: FilePartSourceText
        type: "symbol"
        path: string
        range: {
          start: { line: number; character: number }
          end: { line: number; character: number }
        }
        name: string
        kind: number
      }
    | { text: FilePartSourceText; type: "resource"; clientName: string; uri: string }

  export interface FilePart {
    id: string
    sessionID: string
    messageID: string
    type: "file"
    mime: string
    filename?: string
    url: string
    source?: FilePartSource
  }

  export interface ToolStatePending {
    status: "pending"
    input: Record<string, any>
    raw: string
  }
  export interface ToolStateRunning {
    status: "running"
    input: Record<string, any>
    title?: string
    metadata?: Record<string, any>
    time: { start: number }
  }
  export interface ToolStateCompleted {
    status: "completed"
    input: Record<string, any>
    output: string
    title: string
    metadata: Record<string, any>
    time: {
      start: number
      end: number
      compacted?: number
    }
    attachments?: Array<FilePart>
  }
  export interface ToolStateError {
    status: "error"
    input: Record<string, any>
    error: string
    metadata?: Record<string, any>
    time: { start: number; end: number }
  }
  export type ToolState = ToolStatePending | ToolStateRunning | ToolStateCompleted | ToolStateError

  export interface ToolPart {
    id: string
    sessionID: string
    messageID: string
    type: "tool"
    callID: string
    tool: string
    state: ToolState
    metadata?: Record<string, any>
  }

  export interface StepStartPart {
    id: string
    sessionID: string
    messageID: string
    type: "step-start"
    snapshot?: string
  }
  export interface StepFinishPart {
    id: string
    sessionID: string
    messageID: string
    type: "step-finish"
    reason: string
    snapshot?: string
    cost: number
    tokens: Tokens
  }
  export interface SnapshotPart {
    id: string
    sessionID: string
    messageID: string
    type: "snapshot"
    snapshot: string
  }
  export interface PatchPart {
    id: string
    sessionID: string
    messageID: string
    type: "patch"
    hash: string
    files: Array<string>
  }
  export interface AgentPart {
    id: string
    sessionID: string
    messageID: string
    type: "agent"
    name: string
    source?: { value: string; start: number; end: number }
  }

  export type Part =
    | TextPart
    | ReasoningPart
    | FilePart
    | ToolPart
    | StepStartPart
    | StepFinishPart
    | SnapshotPart
    | PatchPart
    | AgentPart
}
