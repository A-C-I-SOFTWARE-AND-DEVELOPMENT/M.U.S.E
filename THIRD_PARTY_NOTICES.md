# Third-Party Notices

Hermes Agent (MIT, Copyright (c) 2025 Nous Research) incorporates or
adapts material from the third-party open-source projects listed below.
Each remains under its own license; this file preserves the required
attribution.

---

## OpenCode (sst/opencode) — chat renderer for musehq.io

- **Project:** OpenCode — the open-source, provider-agnostic AI coding agent.
- **Source:** https://github.com/sst/opencode (commit `b44bc0a`, v1.17.13)
- **License:** MIT License — Copyright (c) 2025 opencode.

**How MUSE uses it.** musehq.io (`web/musehq/`) is built **on top of
OpenCode's own chat layout**. We vendor OpenCode's self-contained
Share-viewer chat renderer verbatim under
`web/musehq/vendor/opencode/` — the SolidJS message/part components
(`share/part.tsx`, `share/content-*.tsx`, `share/common.tsx`,
`share/copy-button.tsx`), the icon set (`icons/`), and the accompanying
CSS modules — and compose them into a MUSE Solid+Vite app. Their chat
**layout** is preserved; the MUSE **look** is applied entirely through
CSS custom properties (see `web/musehq/src/theme.css`), so the vendored
components are unmodified except for two documented adaptations recorded
in `web/musehq/vendor/opencode/VENDOR.md`:

1. one import-path rewrite (`opencode/session/message-v2` →
   the local trimmed types module `../message-v2`), and
2. `message-v2.ts` is a trimmed, type-only re-declaration of the
   `MessageV2` namespace (derived from OpenCode's generated
   `packages/sdk/js/src/v2/gen/types.gen.ts`), since the upstream module
   pulls in Effect/Zod runtime we don't need.

The vendored license is preserved at
`web/musehq/vendor/opencode/LICENSE`.

### MIT License (OpenCode)

```
MIT License

Copyright (c) 2025 opencode

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## SIA — Self-Improving AI (Hexo Labs)

- **Project:** SIA (Self-Improving AI / Self-Improving Auto-researcher)
- **Source:** https://github.com/hexo-ai/sia
- **PyPI:** `sia-agent`
- **License:** MIT License — Copyright (c) Hexo Labs and the `hexo-ai/sia`
  contributors.

**How Hermes uses it.** Hermes shells out to the separately-installed
`sia` CLI (the upstream `sia-agent` package, unmodified) — it is an
external tool detected on `PATH`, not vendored or pinned as a Hermes
dependency. In addition, Hermes **adapts** the following from SIA, as
permitted by the MIT license:

- The **task-directory format** (`data/public/task.md`,
  `reference/reference_target_agent.py`,
  `reference/SAMPLE_TASK_DESCRIPTIONS.md`) and the three-role
  (meta / target / feedback) generation design, reflected in
  `hermes_cli/workers/sia_assets.py`. The template *text* in that module
  is Hermes-original; only the directory layout and role design are
  adapted from SIA.

No SIA source files are copied verbatim into this repository; the
runnable SIA code is consumed only via the `sia-agent` dependency.

### MIT License (SIA)

```
MIT License

Copyright (c) Hexo Labs and the hexo-ai/sia contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> Note: the copyright line above reflects the upstream MIT grant. If the
> upstream `LICENSE` names a specific holder, mirror that exact line here.

---

## TokenJuice rule set (Vincent Koc)

- **Project:** TokenJuice — terminal-output compaction rules
- **Source:** https://github.com/vincentkoc/tokenjuice
- **License:** MIT License — Copyright (c) 2026 Vincent Koc

**How Hermes uses it.** The JSON rule files under
`tools/tokenjuice/rules/*.json` are vendored **verbatim** from the upstream
`vincentkoc/tokenjuice` project (the generic, non-proprietary rule set). They
are MIT-licensed *data*. The Python reducer in `tools/tokenjuice/` is a
**clean-room reimplementation** of TokenJuice behavior written from the public
upstream specification — **no** source code from any TokenJuice port (including
GPL-licensed ports) is copied. Only the MIT rule JSON is reused, with the
attribution preserved here and in `tools/tokenjuice/rules/NOTICE.md`.

### MIT License (TokenJuice)

```
MIT License

Copyright (c) 2026 Vincent Koc

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## autoresearch (Andrej Karpathy)

- **Source:** <https://github.com/karpathy/autoresearch> (March 2026 snapshot)
- **License:** MIT — Copyright (c) Andrej Karpathy
- **Where:** vendored **byte-identical** at
  `hermes_cli/jarvis_prime/research_fabric/autoresearch/vendor/`
  (sha256 manifest: `hermes_cli/jarvis_prime/research_fabric/autoresearch/checksums.json`).
  muse adaptations (device shim, governance, cost ceilings, swarm) live in
  sibling modules and never modify the vendored files; the experiment loop
  mutates only copies inside disposable `$HERMES_HOME/autoresearch/` workspaces.

### MIT License (autoresearch)

```
MIT License

Copyright (c) Andrej Karpathy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
