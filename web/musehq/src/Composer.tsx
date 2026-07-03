import { createSignal, Show } from "solid-js"
import { store } from "./store"

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 12L20 4L14 20L11 13L4 12Z" fill="currentColor" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
    </svg>
  )
}

export function Composer() {
  const [text, setText] = createSignal("")
  let ta: HTMLTextAreaElement | undefined

  // `streaming` = THIS (active) session's turn is streaming — drives the Stop
  // button and "responding" text. `anyStreaming` = some session is streaming;
  // sends are single-flight so we disable the composer everywhere meanwhile.
  const streaming = () => store.state.streamingId === store.activeSession()?.id
  const anyStreaming = () => store.state.streamingId !== null

  function autosize() {
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px"
  }

  function submit() {
    const body = text().trim()
    if (!body || anyStreaming()) return
    setText("")
    if (ta) ta.style.height = "auto"
    void store.send(body)
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div class="muse-composer">
      <div class="muse-composer__inner">
        <div class="muse-composer__row">
          <textarea
            ref={ta}
            rows={1}
            placeholder="Tell muse what to do…"
            value={text()}
            aria-label="Message muse"
            onInput={(e) => {
              setText(e.currentTarget.value)
              autosize()
            }}
            onKeyDown={onKeyDown}
          />
          <Show
            when={streaming()}
            fallback={
              <button
                class="muse-send"
                type="button"
                disabled={!text().trim() || anyStreaming()}
                aria-label="Send message"
                onClick={submit}
              >
                <SendIcon />
              </button>
            }
          >
            <button class="muse-send" type="button" aria-label="Stop" onClick={() => store.stop()}>
              <StopIcon />
            </button>
          </Show>
        </div>
        <div class="muse-composer__meta">
          <span>{streaming() ? "muse is responding…" : "Enter to send · Shift+Enter for newline"}</span>
          <span style={{ "margin-left": "auto" }}>{store.state.model}</span>
        </div>
      </div>
    </div>
  )
}
