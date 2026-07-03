import { For, Show, createMemo, createEffect, onCleanup } from "solid-js"
import { Part } from "../vendor/opencode/share/part"
import { store } from "./store"
import type { MessageWithParts } from "./store"

// Mirror of upstream Share's part filter: drop structural / synthetic parts that
// must not render as chat bubbles.
function renderableParts(msg: MessageWithParts) {
  return msg.parts.filter((x, index) => {
    if (x.type === "step-start" && index > 0) return false
    if (x.type === "snapshot") return false
    if (x.type === "patch") return false
    if (x.type === "step-finish") return false
    if (x.type === "text" && (x as { synthetic?: boolean }).synthetic === true) return false
    if (x.type === "text" && !(x as { text?: string }).text) return false
    if (x.type === "tool" && (x.state.status === "pending" || x.state.status === "running")) return false
    return true
  })
}

export function Thread() {
  const session = store.activeSession
  const messages = createMemo(() => session()?.messages ?? [])
  let scroller: HTMLDivElement | undefined

  // Keep pinned to the bottom as parts stream in.
  createEffect(() => {
    // Track the total streamed length so the effect re-runs on every delta.
    const _tick = messages().reduce(
      (n, m) => n + m.parts.reduce((k, p) => k + ((p as { text?: string }).text?.length ?? 1), 0),
      0,
    )
    void _tick
    if (!scroller) return
    const el = scroller
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 240
    if (nearBottom) queueMicrotask(() => (el.scrollTop = el.scrollHeight))
  })

  return (
    <div class="muse-thread-scroll" ref={scroller}>
      <Show
        when={messages().length > 0}
        fallback={
          <div class="muse-thread">
            <div class="muse-empty">
              <div class="muse-orb muse-empty__orb" aria-hidden="true" />
              <h1>Ask muse anything</h1>
              <p>
                Your local-first AI operating partner. Chat here, or jump to the Atlas, Studio, or your connected
                platforms from the rail.
              </p>
            </div>
          </div>
        }
      >
        <div class="muse-thread">
          <For each={messages()}>
            {(msg, msgIndex) => {
              const parts = createMemo(() => renderableParts(msg))
              return (
                <Show when={parts().length > 0}>
                  <For each={parts()}>
                    {(part, partIndex) => {
                      const last = () =>
                        messages().length === msgIndex() + 1 && parts().length === partIndex() + 1
                      return <Part last={last()} part={part} index={partIndex()} message={msg} />
                    }}
                  </For>
                </Show>
              )
            }}
          </For>
        </div>
      </Show>
    </div>
  )
}
