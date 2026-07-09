import { marked } from "marked"
import { codeToHtml } from "shiki"
import markedShiki from "marked-shiki"
import DOMPurify from "dompurify"
import { createOverflow, useShareMessages } from "./common"
import { CopyButton } from "./copy-button"
import { createResource, createSignal } from "solid-js"
import style from "./content-markdown.module.css"

// MUSE ADAPTATION (security): upstream's Share viewer renders TRUSTED session
// transcripts, so it injects marked() output as innerHTML unsanitized. musehq.io
// renders live, prompt-injectable LLM output on a first-party origin, so we
// sanitize the rendered HTML before it hits the DOM. `target`/`rel` (added by
// the link renderer) and shiki's inline `style`/`class` are preserved.
DOMPurify.setConfig({ ADD_ATTR: ["target", "rel"] })

// MUSE ADAPTATION (security): escape the href/title we interpolate into the raw
// anchor string and allowlist the URL scheme, so a model-authored
// `[x](javascript:…)` / `[x]("><img onerror=…>` can't break out of the attribute.
// DOMPurify (below) is the second layer; this is the first.
function escapeAttr(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}
function safeHref(href: string): string {
  const trimmed = (href || "").trim()
  // Allow http(s), mailto, anchors and relative paths; reject javascript:/data:/etc.
  if (/^(https?:|mailto:|#|\/|\.{0,2}\/)/i.test(trimmed)) return escapeAttr(trimmed)
  if (!/^[a-z][a-z0-9+.-]*:/i.test(trimmed)) return escapeAttr(trimmed) // scheme-less (e.g. "foo.com/x")
  return "#"
}

const markedWithShiki = marked.use(
  {
    renderer: {
      link({ href, title, text }) {
        const titleAttr = title ? ` title="${escapeAttr(title)}"` : ""
        return `<a href="${safeHref(href)}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`
      },
    },
  },
  markedShiki({
    highlight(code, lang) {
      return codeToHtml(code, {
        lang: lang || "text",
        themes: {
          light: "github-light",
          dark: "github-dark",
        },
      })
    },
  }),
)

interface Props {
  text: string
  expand?: boolean
  highlight?: boolean
}
export function ContentMarkdown(props: Props) {
  const [html] = createResource(
    () => strip(props.text),
    async (markdown) => {
      const rendered = await markedWithShiki.parse(markdown)
      return DOMPurify.sanitize(rendered)
    },
  )
  const [expanded, setExpanded] = createSignal(false)
  const overflow = createOverflow()
  const messages = useShareMessages()

  return (
    <div
      class={style.root}
      data-highlight={props.highlight === true ? true : undefined}
      data-expanded={expanded() || props.expand === true ? true : undefined}
    >
      <div data-slot="markdown" ref={overflow.ref} innerHTML={html()} />

      {!props.expand && overflow.status && (
        <button
          type="button"
          data-component="text-button"
          data-slot="expand-button"
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded() ? messages.show_less : messages.show_more}
        </button>
      )}
      <CopyButton text={props.text} />
    </div>
  )
}

function strip(text: string): string {
  const wrappedRe = /^\s*<([A-Za-z]\w*)>\s*([\s\S]*?)\s*<\/\1>\s*$/
  const match = text.match(wrappedRe)
  return match ? match[2] : text
}
