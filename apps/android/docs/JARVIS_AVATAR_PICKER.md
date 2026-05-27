# Jarvis Avatar Picker

A privacy-safe personalization surface for the Hermes cockpit. The user picks
a Jarvis avatar without granting the app **any** storage, media, or camera
permission. All image processing happens on-device; only the pixelated PNG is
persisted, in app-private storage.

## Privacy design

The picker is built around three rules:

1. **No new permissions.** The app ships with `POST_NOTIFICATIONS`,
   `FOREGROUND_SERVICE`, and `FOREGROUND_SERVICE_DATA_SYNC` — and nothing
   else. Specifically there is no `READ_MEDIA_IMAGES`, no
   `READ_EXTERNAL_STORAGE`, no `CAMERA`, no `RECORD_AUDIO`. A unit test
   (`ManifestPermissionsTest`) asserts this invariant at every build.
2. **No network.** The pixelation pipeline is fully local. No bitmap, file
   path, or chosen built-in is ever transmitted off-device.
3. **No persistent original.** The image the user picks is read through a
   one-shot `ContentResolver` stream, immediately transformed, and the
   resulting PNG is written to `filesDir/avatar/`. The source `Uri` is
   not stored — only held in `AvatarPickerViewModel`'s in-memory `var`
   while the user is iterating on size/style.

## Why the Android Photo Picker

We use `ActivityResultContracts.PickVisualMedia` with
`PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)`.

- It is the system-provided, scoped photo picker. The user explicitly hands
  the app one image — nothing else in the media library is visible to us.
- It requires **zero** runtime permissions. No `READ_*` prompt.
- It is backported on AP I 26+ via `androidx.activity`, so the app's `minSdk`
  doesn't change.

This is the strongest off-the-shelf privacy posture available for image
selection on Android.

## Pixelation pipeline

```
content:// Uri
   │
   ▼  ContentResolver.openInputStream (bounded decode, sample down to ~1024 px)
Bitmap (decoded)
   │
   ▼  center-crop to square
Bitmap (square)
   │
   ▼  filtered downscale to 16 / 32 / 48 px (PixelSize)
Bitmap (small, smooth)
   │
   ▼  per-pixel style pass (NONE / NAVY_GOLD / CYAN_GLOW / MONOCHROME_TERMINAL)
Bitmap (small, styled)
   │
   ▼  nearest-neighbor upscale to 256 × 256
Bitmap (256² pixel art)
   │
   ▼  PNG encode → filesDir/avatar/avatar_<timestamp>.png
File
```

All intermediate bitmaps are `recycle()`'d. The PNG is the only artifact
that ever lands on disk.

## Storage layout

```
<app filesDir>/avatar/
  avatar_<epoch-ms>.png   # the active avatar
DataStore: avatar_prefs
  profile_json = { source, builtin?, generatedPath?, pixelSize, style }
```

`AvatarImageStore.pathInAppPrivate(file)` is the gatekeeper for any path
flowing back out of `AvatarProfile.generatedPath`. It rejects paths outside
`filesDir/avatar/` (e.g. `/sdcard/...`) so a future bug or migration error
cannot exfiltrate data out of the sandbox.

## Built-in avatars (v1)

Four placeholder built-ins ship with material-icon stubs:

| Enum | Icon (Material) | Label |
|---|---|---|
| `GUARDIAN_SHIELD` | `Icons.Filled.Shield` | Guardian |
| `FAST_WORKER_BOLT` | `Icons.Filled.Bolt` | Fast worker |
| `KNOWLEDGE_MEMORY` | `Icons.Filled.Memory` | Knowledge |
| `COMMAND_AUTO` | `Icons.Filled.AutoAwesome` | Command |

These are explicit placeholders. Custom Jarvis vector drawables are a
follow-up; enum names are pinned by `AvatarStyleStabilityTest` so swapping
the artwork does not break persisted user data.

## Integration

The picker is reached from **Settings → Personalization → Open avatar
picker**. There is exactly one wired entry point in the app, by design.

Nav wiring (`HermesNavGraph.kt`):

```kotlin
composable(Screen.Settings.route) {
    val vm: SettingsViewModel = viewModel(factory = remember { container.settingsVmFactory() })
    SettingsScreen(
        viewModel = vm,
        onBack = { nav.popBackStack() },
        onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
        onOpenAvatarPicker = { nav.navigate(Screen.AvatarPicker.route) },
    )
}
composable(Screen.AvatarPicker.route) {
    val vm: AvatarPickerViewModel = viewModel(factory = remember { container.avatarPickerVmFactory() })
    AvatarPickerScreen(viewModel = vm, onBack = { nav.popBackStack() })
}
```

A future Jarvis live screen can add a second entry point ("edit avatar")
by calling `nav.navigate(Screen.AvatarPicker.route)` from its own
composable; no further wiring is needed.

## Tests

Local JVM (`./gradlew :app:testDebugUnitTest`):

- `AvatarStyleStabilityTest` — enum names + counts are pinned.
- `ManifestPermissionsTest` — only the original three permissions appear.
- `AvatarPixelatorTest` (Robolectric) — output is 256×256 square; output
  file path is app-private; nearest-neighbor preserves a solid color;
  the picker source path is not embedded in the output filename.
- `AvatarImageStoreTest` (Robolectric) — saved files live under
  `filesDir/avatar/`; external paths are rejected; `deleteAll` clears the
  directory.
- `AvatarRepositoryTest` (Robolectric) — save/load round-trip for both
  builtin and generated profiles; persisted JSON never contains the
  picker `content://` URI; `clear()` empties both prefs and image store.

## Future work (non-launch)

- Replace material-icon built-ins with custom Jarvis vector drawables.
- Optional on-device AI avatar generation (must remain on-device — no
  cloud calls).
- Draggable crop region instead of fixed center-crop.
- Surface the chosen avatar in JarvisLive top bar and orchestrator chip.

Each of these is additive and respects the same hard rules above.
