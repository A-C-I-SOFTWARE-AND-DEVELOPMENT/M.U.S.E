# Vendored: OpenCode chat renderer

This directory contains source **vendored verbatim** from
[sst/opencode](https://github.com/sst/opencode) so musehq.io can be built
directly on top of OpenCode's own chat layout.

| | |
|---|---|
| Upstream | https://github.com/sst/opencode |
| Commit | `b44bc0a` |
| Version | v1.17.13 |
| License | MIT — Copyright (c) 2025 opencode (see [`LICENSE`](./LICENSE)) |
| Vendored on | 2026-07-03 |

## What was vendored

From `packages/web/src/components/` (OpenCode's self-contained, server-less
**Share viewer** — the same renderer that powers `opencode.ai/s/<id>`):

- `share/part.tsx` — the message/part renderer (text, reasoning, files,
  tool cards for bash/edit/write/read/grep/list/glob/webfetch/task/todo,
  step markers) and `ProviderIcon`.
- `share/content-*.tsx` + `*.module.css` — code, diff, bash, markdown, text,
  error content blocks.
- `share/common.tsx` — the `ShareI18nProvider` / `useShareMessages` context
  and number/duration formatters.
- `share/copy-button.tsx` + `.module.css`, `share/part.module.css`.
- `icons/index.tsx`, `icons/custom.tsx` — the pure-SVG icon set the renderer
  uses.

## Adaptations (the only changes to upstream files)

1. **Import rewrite** in `share/part.tsx`:
   `import type { MessageV2 } from "opencode/session/message-v2"` →
   `from "../message-v2"`.

2. **`message-v2.ts`** is a **trimmed, type-only** re-declaration of the
   `MessageV2` namespace, derived from OpenCode's generated client types
   (`packages/sdk/js/src/v2/gen/types.gen.ts`). Upstream's real module pulls
   in Effect + Zod runtime that the renderer does not need at build time (the
   types are erased). Tool-state `input`/`metadata` are typed `Record<string,
   any>` to match upstream's effective per-tool dynamic shapes.

3. **Security hardening** in `share/content-markdown.tsx`. Upstream renders
   **trusted** shared transcripts, so it injects `marked()` output as
   `innerHTML` unsanitized and interpolates link `href`/`title` into a raw
   anchor string. musehq.io renders live, prompt-injectable LLM output on a
   first-party origin that holds keys, so we:
   - run the rendered HTML through **DOMPurify** before it hits the DOM
     (shiki's escaped code and the link renderer's `target`/`rel` are
     preserved), and
   - **escape** the interpolated `href`/`title` and **allowlist** the URL
     scheme in the custom link renderer (reject `javascript:`/`data:` etc.),
     as a first layer behind DOMPurify.

   The shiki paths (`content-code.tsx`, `content-bash.tsx`) are already safe by
   construction (shiki HTML-escapes code) and are left unchanged.

No other edits. The MUSE **look** is applied without touching these files —
purely by (re)defining the CSS custom properties they consume, in
`../../src/theme.css`.

## Updating

Re-copy the files above from a newer OpenCode checkout, re-apply the two
adaptations, and re-run `npm run build` + `npm run typecheck` in `web/musehq/`.
