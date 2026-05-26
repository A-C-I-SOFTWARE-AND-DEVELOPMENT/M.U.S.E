# JARVIS Chat — Compose surface

The Jarvis Prime chat surface is an isolated Compose screen + ViewModel
that drives a mobile-first conversation against a pluggable
`JarvisChatGateway`. PR #117 originally added it; PR #131 reverted the
UI half after the integration build failed; this lane revives it as a
self-contained feature with no nav wiring so it can be integrated
safely.

## What this lane delivers

- `com.aci.hermes.ui.screens.chat.ChatScreen` — Compose screen that is
  shell-friendly (no internal `Scaffold` / `TopAppBar`; takes a
  `Modifier` so the existing `ShellHost` keeps owning the chrome).
- `com.aci.hermes.ui.screens.chat.ChatViewModel` — Conversation engine
  with stop/retry/copy/clear, inline-card state, snackbar plumbing.
- 22 unit tests across three files (intent classifier, mock gateway,
  view model).
- One gradle config tweak (`isReturnDefaultValues = true` for
  `android.util.Log`) and one test dep (`kotlinx-coroutines-test`).

## What this lane deliberately does not do

- **No navigation wiring.** `HermesNavGraph.kt`, `Screen.kt`, and
  `AppContainer.kt` are untouched. The `Screen.Chat` route still
  renders the `PlaceholderScreen` shipped in PR #131.
- **No voice capture.** PR #117 used `RecognizerIntent` for STT; this
  revision drops it. The cockpit still ships zero new permissions —
  the manifest is unchanged.
- **No real gateway.** `MockJarvisChatGateway` is the only
  implementation. A real HTTP/SSE gateway plugs into the same
  `JarvisChatGateway` interface in a follow-up lane.

## Public entry points

The integrator wires exactly these two symbols:

```kotlin
class ChatViewModel(
    private val gateway: JarvisChatGateway,
    private val taskSink: JarvisTaskSink,
    private val logBuffer: LogBuffer,
    private val clipboard: JarvisClipboard,
    private val scopeOverride: CoroutineScope? = null,  // test seam — leave null in production
) : ViewModel()

@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    modifier: Modifier = Modifier,
    onBack: () -> Unit = {},
)
```

`onBack` is a no-op default — pass `{ navController.popBackStack() }`
if you render the screen outside `ShellHost`. Inside `ShellHost` the
back affordance comes from the shell itself.

`scopeOverride` is a test-only seam. Production callers always omit
it; the VM uses `viewModelScope` automatically.

## How the conversation engine routes prompts

`MockJarvisChatGateway` defers to the pure-Kotlin
`JarvisIntentClassifier` in `data/jarvis/`. The mapping (kept stable
since PR #117) is:

| Sample prompt                                  | Intent       | Reply shape                                                  |
|------------------------------------------------|--------------|--------------------------------------------------------------|
| `hi` / `thanks` / `good morning`               | CASUAL       | One-line ack, no detail, no card                             |
| `walk me through the architecture`             | ARCHITECTURE | Short body + expandable detail                               |
| `build a chat screen for jarvis`               | TASK         | Short body + **Task card** (promote to orchestrator)         |
| `deploy gateway to prod`                       | APPROVAL     | Formal body + **Approval card** (Approve / Hold)             |
| `audit the api key handling for leaks`         | SERIOUS      | Slow-down body + **Serious card**                            |
| `drop table users in prod`                     | CRITICAL     | Stop-the-line body + **Critical card** (typed-ack required)  |
| `/error simulate`                              | ERROR_TRIGGER| Single `Failure` → red error bubble with Retry               |
| `/stall please`                                | ABORT_TRIGGER| Streams chunks deliberately slowly — exercise Stop           |
| anything else                                  | DEFAULT      | Short body + expandable detail                               |

## Integration steps (for the next lane)

Four edits, none of which are in this lane's allowed surface:

1. **Add a factory in `di/AppContainer.kt`:**
   ```kotlin
   fun chatVmFactory(): ViewModelProvider.Factory =
       object : ViewModelProvider.Factory {
           @Suppress("UNCHECKED_CAST")
           override fun <T : ViewModel> create(modelClass: Class<T>): T =
               ChatViewModel(
                   gateway = MockJarvisChatGateway(),
                   taskSink = RepositoryTaskSink(hermesTaskRepository),
                   logBuffer = logBuffer,
                   clipboard = AndroidJarvisClipboard(appContext),
               ) as T
       }
   ```

2. **Swap the placeholder in `ui/navigation/HermesNavGraph.kt`** —
   inside `composable(Screen.Chat.route) { ... }` around line 244:
   ```kotlin
   val vm: ChatViewModel = viewModel(factory = remember { container.chatVmFactory() })
   ShellHost(currentRoute = Screen.Chat.route, /* …existing args… */) { padding ->
       ChatScreen(viewModel = vm, modifier = Modifier.padding(padding))
   }
   ```

3. **No `Screen.kt` change.** `Screen.Chat` route already exists.

4. **No `AndroidManifest.xml` change.** No new permissions.

That's it. After those edits, `Screen.Chat` renders the live chat
surface instead of the placeholder, with all card actions wired
end-to-end.

## Tests

Run from `apps/android/`:

```bash
./gradlew testDebugUnitTest
./gradlew assembleDebug
```

> **Note on full-tree validation.** PR #131's integration branch
> currently fails `compileDebugKotlin` with **528 errors across 9
> files** in the `audit`, `capability`, `control`, `home`, and
> `memory` subsystems (missing string resources, missing repository
> methods, missing data-layer types). Those errors are unrelated to
> the chat surface and exist on the unmodified PR #131 head — none
> are in this lane's allowed surface. The new chat files
> (`ui/screens/chat/**` and the three test files) emit **zero**
> compile errors. The integrator either rebases on a clean base
> before merging this lane, or fixes the unrelated breaks in
> separate lanes before running the full `assembleDebug` /
> `testDebugUnitTest` validation.

Three new test files cover the chat surface:

- **`JarvisIntentClassifierTest`** — every classifier rule
  (CRITICAL / APPROVAL / SERIOUS / ARCHITECTURE / TASK / CASUAL /
  DEFAULT / `/error` / `/stall`) plus target-tool and task-type
  inference.
- **`MockJarvisChatGatewayTest`** — the streaming contract: leading
  `Thinking`, trailing `Done`, single `Failure` for `/error`, and
  one inline card per recognised intent.
- **`ChatViewModelTest`** — 11 cases covering send, every inline
  card variant, typed-ack rejection + acceptance, stop mid-stream
  (uses a stalling test gateway with `awaitCancellation()`),
  retry-after-error, copy, transcript reset, and task promotion.

Tests inject a `CoroutineScope` into the VM via the `scopeOverride`
seam, so they never touch `Dispatchers.Main`. The stop test uses
`runTest { ... }` with an `UnconfinedTestDispatcher`.

## Build-config tweaks added by this lane

- `apps/android/app/build.gradle.kts`:
  ```kotlin
  testOptions {
      unitTests {
          isReturnDefaultValues = true
      }
  }
  ```
  Required because `LogBuffer` wraps `android.util.Log`, which throws
  "not mocked" in JVM unit tests by default. The chat VM logs through
  `LogBuffer`. This was the likely root cause of the PR #131 revert.
- `apps/android/gradle/libs.versions.toml` + `app/build.gradle.kts`:
  add `kotlinx-coroutines-test` as a `testImplementation`. Required
  for the stop-streaming test (and unblocks the pre-existing
  `MemoryViewModelTest` that already imports
  `kotlinx.coroutines.test.*`).

## What's still pending after this lane lands

- Replace `MockJarvisChatGateway` with a real streaming gateway
  implementation behind the same `JarvisChatGateway` interface.
- Wire `Screen.Chat` to render `ChatScreen` (4 edits above).
- Optional: re-introduce voice capture via `RecognizerIntent` if/when
  the product wants it back. `RecognizerIntent` does **not** require
  `RECORD_AUDIO` — it's an Activity-result hop to the system speech
  app. Add only if voice is in scope for that lane.
