# MUSE — App Identity Migration

This is the **compatibility contract** for the Hermes → MUSE
visual rebrand of the Android app. It tells the next person on this
branch what changed, what intentionally did **not** change, and why.

---

## 1. What is MUSE?

MUSE is the **user-facing product name** for the personal AI
command center that runs as the Android app under `apps/android/`.

The backend / runtime is still called **Hermes** — that name appears in
docs, repo paths, code identifiers, and developer-facing diagnostics.
The agent runtime, gateway protocol, REST surface, and Python core
remain Hermes.

> MUSE is the cockpit. Hermes is the airframe.

---

## 2. Compatibility guarantees

### 2.1 Android package identity — unchanged

| Item | Value |
|---|---|
| Application ID | `com.aci.hermes` |
| Debug variant | `com.aci.hermes.debug` |
| Namespace | `com.aci.hermes` |
| Launcher activity | `com.aci.hermes.MainActivity` |
| Foreground service | `com.aci.hermes.service.HermesService` |
| Signing identity | unchanged from previous release |

Renaming the package would invalidate installs, break the Termux intent
bridge, and lose tester install history. **Do not rename.**

### 2.2 Kotlin module structure — unchanged

The source tree still rooted at `com.aci.hermes`:

```
com.aci.hermes
├── HermesApplication.kt
├── MainActivity.kt
├── data/                  // unchanged
├── di/AppContainer.kt     // unchanged
├── service/HermesService.kt
├── ui/
│   ├── components/        // NEW — MUSE component library
│   ├── navigation/        // unchanged
│   ├── screens/           // unchanged signatures
│   └── theme/             // rebranded internals; old names still alias
└── util/
```

No screen ViewModel signatures, navigation routes, or DI factory names
changed.

### 2.3 Theme API — back-compat aliases

| Old symbol | New symbol | Status |
|---|---|---|
| `HermesTheme` | `JarvisPrimeTheme` | Old name is now a `@Composable` alias that delegates to the new one. Both still resolve. |
| `HermesTypography` | `JarvisTypography` | Old name is a `val` alias. |
| `HermesGold`, `HermesInk`, `HermesViolet`, `HermesError`, `HermesSurfaceDim`, `HermesSurfaceBright`, `HermesGoldDeep`, `HermesInkSoft`, `HermesPaper` | Re-pointed at `MUSE*` tokens | Old names compile; render with the new palette. |

`MainActivity.kt` and `HermesNavGraph.kt` keep their old import lines
and still work.

### 2.4 String resource IDs — additive

Every `R.string.*` key that existed before still exists. The values
were edited to say "MUSE" where appropriate; the keys are
additive only. A grep verified that all 123 unique `R.string.*` call
sites in Kotlin resolve against the new `strings.xml`.

New strings cluster in the following families:

- `welcome_*`
- `ask_jarvis_*`
- `voice_*`
- `approval_*`, `serious_*`, `critical_*`, `emergency_*`
- `gateway_*`, `mock_mode_*`, `termux_mode_*`
- `memory_*`, `audit_*`
- `task_status_*`, `task_complete_*`, `worker_failed_*`
- `permission_education_*`

### 2.5 XML resource references — back-compat

`@color/hermes_ink` is preserved alongside the new `@color/jarvis_*`
tokens, because the existing `drawable/splash_background.xml` previously
referenced it. (`splash_background.xml` is now updated to reference
`@color/jarvis_ink_abyss` directly, but the legacy color stays for any
out-of-tree drawable that might still reference it.)

XML `style` names like `Theme.HermesAgent` are unchanged.
`AndroidManifest.xml` keeps its `android:theme="@style/Theme.HermesAgent"`
references. Renaming the style would force every manifest entry to
change and risks build breakage.

### 2.6 Permissions — unchanged

`AndroidManifest.xml` retains exactly the three permissions the app
already declared:

- `android.permission.POST_NOTIFICATIONS`
- `android.permission.FOREGROUND_SERVICE`
- `android.permission.FOREGROUND_SERVICE_DATA_SYNC`

**No new permissions were added by this rebrand.** Voice / microphone
copy was added to `strings.xml` for future use, but the Android
manifest entry for `RECORD_AUDIO` is intentionally **not** declared in
this commit. Adding it is a separate, scoped change with its own
permission-education flow.

---

## 3. What changed

### 3.1 Visual identity

- Dark navy / black foundation (was: mixed light/dark with violet accent)
- Gold = approval / authority
- Cyan = listening / activity
- Crimson = critical / destructive
- Jade = success
- Amber = warning
- Violet = memory (now narrower; was: secondary brand)
- Material 3 colour scheme rewritten in `Theme.kt`

### 3.2 Launcher icon

The caduceus glyph is retired. The new mark is:

- gold authority ring (outer)
- cyan listening ring (inner)
- **"J"** monogram in gold
- a gold "prime dot" above the J — the watchful eye

Background: deep navy with a faint cross-hair grid.

### 3.3 New component library

`ui/components/` is new. It contains every shareable MUSE
surface: header, status pill, ask bar, tier-coloured cards, emergency
stop, permission education. Existing screens (`OrchestratorScreen`,
`SettingsScreen`, `TaskDetailScreen`, `DiagnosticsScreen`) are **not**
rewritten in this commit — they continue to render against the existing
Material 3 scaffolding and pick up the new palette automatically through
the theme. A follow-up commit can migrate each screen to the new
component primitives one at a time without breaking the build.

### 3.4 Splash

`SplashScreen.kt` now renders the new brand glyph and the
`R.string.app_name` resource ("MUSE"), plus a tagline. The XML
splash window background is still the deepest navy so there is no
flash-of-old-colour during cold start.

---

## 4. Rebrand-safety checklist

When touching this branch, keep these invariants:

- [ ] Application ID stays `com.aci.hermes`
- [ ] No new entries in `AndroidManifest.xml` `<uses-permission>` block
- [ ] No removal of any `R.string.*` key
- [ ] No removal of any Kotlin top-level symbol named `Hermes*` in
      `ui/theme/` (it may now be an alias — keep the alias)
- [ ] Notification channel ID and foreground service type remain the
      same (rebuilding the channel would re-prompt the user)
- [ ] Termux intent bridge (`TermuxIntentBridge.kt`) is untouched
- [ ] `versionCode` only bumps in a release commit, not a rebrand commit

---

## 5. Future work — not in this commit

1. **Migrate `OrchestratorScreen` to `JarvisStatusHeader` + `TaskCard`.**
   The current `StatusCard` / `TaskRow` will be replaced screen-by-screen.
2. **Wire `EmergencyStopButton` to `HermesService.stopForeground()`.**
   The button exists as a reusable composable but is not yet placed on a
   screen.
3. **Wire `AskJarvisBar` to the local orchestrator's intake.** Today
   the orchestrator builds prompts via the existing `TaskDetailScreen`.
4. **Microphone permission flow.** When `RECORD_AUDIO` is added, gate
   the system permission prompt behind `PermissionEducationCard`.
5. **Adaptive light-mode polish.** The dark scheme is canonical; the
   light scheme is functional but un-tuned.
