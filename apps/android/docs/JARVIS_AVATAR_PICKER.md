# Jarvis Avatar Picker — On-Device Only

The picker lets the operator choose an avatar for Jarvis. Two
sources are supported:

1. **Bundled defaults** — four vector avatars (Cyan, Gold, Slate,
   Violet). Selecting one updates the profile in-memory; no I/O, no
   permission needed.
2. **User-picked photo** — Android Photo Picker returns a URI, the
   screen decodes it once, hands the bitmap to the view-model,
   which pixelates on `Dispatchers.Default` and writes the result
   to app-private storage on `Dispatchers.IO`.

## Permission contract — zero new permissions

The picker **does not** request, declare, or rely on:

- `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`, `READ_MEDIA_VISUAL_USER_SELECTED`
- `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`, `MANAGE_EXTERNAL_STORAGE`
- `RECORD_AUDIO`, `CAMERA`
- `SYSTEM_ALERT_WINDOW`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`

The Android Photo Picker (`ActivityResultContracts.PickVisualMedia`)
runs in a system process, shows only what the user picks, and
returns a URI with one-shot read permission to the calling
activity. No media permission needed.

`AvatarPickerPermissionAuditTest` parses `AndroidManifest.xml` and
fails the build if any forbidden permission appears.

## No-upload contract

`AvatarPickerNoUploadTest` is an AST-style guard: it scans every
`.kt` file under `ui/screens/avatar/` and fails the build if any
import line contains a known network root (`okhttp3.`, `okio.`,
`retrofit2.`, `java.net.HttpURLConnection`, etc.). A future PR that
quietly adds `import okhttp3.OkHttpClient` to the picker view-model
would fail this test before it ships.

## Storage location

User-generated avatars live at:

```
{context.filesDir}/avatars/user_avatar.png
```

- App-private — never world-readable, never on shared storage.
- One file at a time — saving a new avatar overwrites the old one.
- Encoded as PNG, lossless (preserves the pixelator's flat tones).

`AvatarStorage` is the single class that reads/writes this path.
Nothing outside it should construct that file path directly.

## Pixelator

`AvatarPixelator.pixelate(source, outputSize, grid, paletteSize)`:

1. Downsamples to `grid × grid` (default 64×64) with `filter=false`
   — each source-region collapses into one hard-edged sample.
2. Optionally quantizes to a small palette (default 16 colors)
   using cheap bucket-average quantization. No ML, no network, all
   work synchronous on the calling thread (the VM dispatches to
   `Dispatchers.Default`).
3. Upscales back to `outputSize × outputSize` with `filter=false`
   — preserves crisp blocky edges.

The transform is **pure** `Bitmap → Bitmap` — no filesystem, no
network, no `Context` dependency.

## Flow

```
[Photo Picker] -- URI --> [Screen]
                              |
                       decode once (BitmapFactory)
                              |
                              v
              [ViewModel.pixelate(bitmap)]
                              |
                  Dispatchers.Default
                              |
                              v
                       previewBitmap = ...
                              |
            (user reviews; can re-pick or save)
                              |
                              v
            [ViewModel.savePreview()] -- Dispatchers.IO -->
                              |
                  AvatarStorage.save(preview)  →  filesDir/avatars/user_avatar.png
                              |
                              v
                 current = JarvisAvatarProfile(UserGenerated(path))
```

Delete + Reset both fall back to the bundled default
(`DefaultAvatars.defaultProfile()`).

## Tests

| Test file | Coverage |
|---|---|
| `AvatarPixelatorTest` | default constants are in the pixel-art band; bucket math separates visually-distant colors. |
| `AvatarStorageTest` | path lives inside `filesDir/avatars/`; `delete()` semantics; `exists()` requires a non-empty file. |
| `AvatarPickerNoUploadTest` | AST scan asserts zero network imports under `ui/screens/avatar/`. |
| `AvatarPickerPermissionAuditTest` | `AndroidManifest.xml` permission set matches the launch allowlist exactly; no forbidden permission declared. |
| `DefaultAvatarsTest` | bundled-avatar set is resolvable, unique, and Cyan is the launch default. |

A Robolectric / on-device Bitmap test for the pixelator's
end-to-end transform is intentionally **not** added — the codebase
hasn't adopted Robolectric, and the bucket math + downscale-upscale
contract is robust enough to exercise via smoke testing on the
emulator before launch.

## What was **not** touched

- `AndroidManifest.xml` — zero new permissions.
- Owner-gated actions, in-app authorization phrase, emergency-stop
  controller, redaction modules — all untouched.
- Package identity (`applicationId = "com.aci.hermes"`).
