# JARVIS Capability UI

This document describes the mobile-native capability picker that
closes the `/skills` gap called out in
[`apps/android/README.md`](../README.md#whats-not-wired-up-yet).

> Status: alpha. The picker lives under the orchestrator screen at
> **JARVIS capabilities** (AutoAwesome icon in the top app bar).

> **Not to be confused with Device control.** This picker is about *chat
> lanes / agent modes* — it stages a prompt, it never touches the phone.
> The separate **Device control** surface (Control → Device control) is
> about *device permissions and on-screen actions* — letting Jarvis tap,
> swipe, and launch apps through a consent + broker + action-log path. See
> the data package `com.aci.hermes.data.devicecontrol`, the screen
> `ui/screens/devicecontrol/DeviceControlScreen.kt`, and
> [`docs/mobile/mobile-app-guide.md`](../../../docs/mobile/mobile-app-guide.md#device-control--letting-jarvis-operate-the-phone).

---

## Design intent

JARVIS Prime is **one visible assistant**. The full agent surface is
hundreds of specialist agents, council members, and worker lanes —
showing that list directly on a phone would create the exact
"chaotic swarm" experience the project is set up to avoid.

The mobile picker enforces a few invariants:

1. **One assistant, curated capabilities.** Only ~12 capabilities are
   visible by default. Power users opt into the long tail via the
   **Show advanced** toggle.
2. **No direct execution from the UI.** A tap never invokes a tool.
   The picker only stages a prompt for the owner to review and
   dispatch through the chat / gateway surface.
3. **Route preview before dispatch.** Every capability includes a
   structured preview (surface, lane, gateway requirement, owner
   gate) so the owner can see where their words will land.
4. **Owner-gated capabilities are explicitly marked.** They render a
   red-tinted badge on the card and a full warning banner on the
   invocation sheet. The underlying lane refuses to act without an
   explicit "Yes, with authorization." follow-up message.

---

## File map

```
apps/android/app/src/main/java/com/aci/hermes/
├── data/
│   ├── model/Capability.kt                          # Capability + Route + Category
│   └── capability/
│       ├── CapabilityCatalog.kt                     # curated capabilities (source of truth)
│       └── CapabilityRepository.kt                  # search / filter / route preview
└── ui/
    └── screens/capability/
        ├── CapabilityScreen.kt                      # main screen (search, filter, list, sheet)
        ├── CapabilityViewModel.kt                   # query + selected + snackbar state
        └── SkillCard.kt                             # one capability card

apps/android/app/src/test/java/com/aci/hermes/data/capability/
├── CapabilityCatalogTest.kt
└── CapabilityRepositoryTest.kt
```

---

## Capability model

```kotlin
data class Capability(
    val id: String,                  // stable, used for search keying
    val name: String,
    val category: CapabilityCategory,
    val summary: String,             // phone-width one-liner
    val examplePrompt: String,       // safe-invocation payload
    val route: CapabilityRoute,
    val ownerGated: Boolean = false,
    val isAdvanced: Boolean = false,
    val tags: List<String> = emptyList(),
)
```

Categories (deliberate, fixed at ten):

- Conversation
- Build
- Review
- Research
- Memory
- Mobile
- Safety
- AOS Council
- Worker Lane
- Social Intelligence

```kotlin
data class CapabilityRoute(
    val surface: RouteSurface,       // CHAT | GATEWAY | LOCAL_HANDOFF
    val lane: String,                // human-readable, e.g. "jarvis-prime: critic-mode"
    val requiresGateway: Boolean,
    val requiresOwnerAuth: Boolean,
    val notes: String? = null,
)
```

---

## Safe-invocation contract

When the owner taps a capability card, the screen opens a modal
bottom sheet with two halves:

### Route preview

A structured summary of how the invocation would route:

| Surface     | Lane                                | Gateway   | Owner gate |
|-------------|-------------------------------------|-----------|------------|
| Chat        | `jarvis-prime: critic-mode`         | Required  | Not required |
| Chat        | `aos-council: codex-dispatch-...`   | Required  | Required   |

### Staged prompt

The text the owner would dispatch. The preview always prefixes a
machine-readable route header so the gateway can audit-log which
lane the message came from:

```
[route] chat :: jarvis-prime: critic-mode
JARVIS, critic mode. Pressure-test this: <plan or doc>.
```

The **Stage to clipboard** action only copies that block to the
clipboard. **No network call, no tool invocation, no implicit
dispatch.** The owner pastes the staged block into chat (or any
other channel they choose) when ready.

This is intentional. The chaotic-swarm failure mode the project is
explicitly designed to avoid begins the moment the UI starts
firing tools on its own.

---

## Owner-gated warning

A capability is owner-gated if either of:

- `Capability.ownerGated == true`
- `Capability.route.requiresOwnerAuth == true`

The catalog guarantees these stay in sync (see
[`CapabilityCatalogTest.owner_gated_capabilities_are_marked`](../app/src/test/java/com/aci/hermes/data/capability/CapabilityCatalogTest.kt)).

The UI surfaces the gate three times:

1. **Card** — red-tinted `Owner-gated` chip beside the name.
2. **Sheet** — `Owner gate: Required` line in the route preview.
3. **Sheet** — full banner with the message "This lane will not
   act without explicit owner authorization."

The convention on the lane side is unchanged from JARVIS Prime:
the owner must respond with literally `Yes, with authorization.`
before the lane proceeds.

---

## Advanced toggle

The `Show advanced` switch flips
`CapabilityViewModel.setIncludeAdvanced(true)`. The repository's
`search()` honors the flag — when off, any capability with
`isAdvanced = true` is filtered out before the category and
free-text filters run. The header chip counts both visible and
total ("Showing 12 of 18") so the user can see what's being
hidden.

---

## Wiring

```
HermesNavGraph
└── composable(Screen.Capability.route) {
        val vm = viewModel(factory = container.capabilityVmFactory())
        CapabilityScreen(viewModel = vm, onBack = { ... })
    }
```

Entry point: `OrchestratorScreen` shows an `AutoAwesome` icon in
the app bar and a `Capabilities` overflow menu item, both calling
`onOpenCapabilities()` which navigates to `Screen.Capability`.

DI: `AppContainer.capabilityRepository` and
`AppContainer.capabilityVmFactory()` — same hand-rolled pattern
the other screens use.

---

## Tests

Plain JUnit, no Android instrumentation needed:

```
apps/android/app/src/test/java/com/aci/hermes/data/capability/
├── CapabilityCatalogTest.kt
└── CapabilityRepositoryTest.kt
```

Coverage:

- `every_category_has_at_least_one_capability` — the curated set
  honors the ten-category contract.
- `catalog_ids_are_unique` — guards a copy-paste regression.
- `curated_default_excludes_advanced` — proves the advanced toggle
  actually hides things.
- `owner_gated_capabilities_are_marked` — the card-level flag and
  the route-level flag never drift.
- `empty_query_returns_curated_set` / `empty_query_with_advanced_returns_everything`
- `search_is_case_insensitive_and_matches_name` / `_matches_tags`
- `search_filters_by_category` / `search_with_no_matches_returns_empty`
- `advanced_results_are_hidden_until_toggled`
- `route_preview_includes_required_lines` — surface, lane,
  gateway, owner gate.
- `route_preview_marks_owner_gate_when_capability_is_gated`
- `staged_prompt_includes_route_header_and_example`
- `staged_prompt_never_invokes_a_tool_directly` — the safe-
  invocation invariant; no shells, no outbound HTTP.

Run them with:

```bash
cd apps/android
./gradlew :app:testDebugUnitTest
```

The full build remains:

```bash
cd apps/android
./gradlew assembleDebug
```

---

## Future work

- **Composable route preview component.** Today the preview is
  inline in `CapabilityScreen.kt`. Once the orchestrator screen
  also wants to show a route preview for tasks, extract it.
- **Lane → telemetry binding.** The route header is a stable
  prefix; the gateway can already log it, but a future cycle
  could surface lane-level latency / cost in the SkillCard.
- **Per-capability custom-prompt edits.** Today the staged prompt
  is rendered read-only. An obvious next step is letting the user
  tweak the placeholder before staging. Skipped for v0.1 because
  it adds a textfield-validation surface without changing the
  safe-invocation contract.
