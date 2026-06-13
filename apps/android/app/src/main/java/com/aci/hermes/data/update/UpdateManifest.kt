package com.aci.hermes.data.update

import org.json.JSONObject

/**
 * Parsed contents of `android-latest.json` — the small manifest the release
 * workflow publishes beside the rolling APK so the app can tell whether a newer
 * build exists. Shape:
 *
 * ```json
 * {"versionCode": 123, "versionName": "2026.06.13.107",
 *  "apkUrl": "https://.../android-latest/jarvis-prime-android.apk",
 *  "notes": "…"}
 * ```
 */
data class UpdateManifest(
    val versionCode: Int,
    val versionName: String,
    val apkUrl: String,
    val notes: String,
) {
    companion object {
        /**
         * Defensive parse — returns `null` on any malformed/missing required
         * field (a missing manifest must never crash the app or be mistaken for
         * an update). Uses `org.json` (Android runtime); not exercised by JVM
         * unit tests because this module sets `unitTests.isReturnDefaultValues`.
         */
        fun parse(json: String): UpdateManifest? = try {
            val o = JSONObject(json)
            val code = o.optInt("versionCode", -1)
            val apkUrl = o.optString("apkUrl", "")
            if (code <= 0 || apkUrl.isBlank()) {
                null
            } else {
                UpdateManifest(
                    versionCode = code,
                    versionName = o.optString("versionName", ""),
                    apkUrl = apkUrl,
                    notes = o.optString("notes", ""),
                )
            }
        } catch (_: Throwable) {
            null
        }
    }
}

/**
 * Outcome of an update check. The decision in [evaluate] is pure (no IO, no
 * Android types) so it is fully JVM-unit-testable.
 */
sealed interface UpdateState {
    /** A check is in flight. */
    data object Checking : UpdateState

    /** The running build is the latest published one. */
    data class UpToDate(val versionName: String) : UpdateState

    /** A newer build is available to install. */
    data class Available(
        val versionName: String,
        val apkUrl: String,
        val notes: String,
    ) : UpdateState

    /** The channel couldn't be read (offline, malformed manifest, …). */
    data class Unknown(val reason: String) : UpdateState

    companion object {
        /**
         * Pure comparison of the running build against a fetched manifest.
         * `manifest == null` (unreachable/malformed) → [Unknown]; a strictly
         * greater `versionCode` → [Available]; otherwise [UpToDate].
         */
        fun evaluate(
            currentVersionCode: Int,
            currentVersionName: String,
            manifest: UpdateManifest?,
        ): UpdateState = when {
            manifest == null -> Unknown("Couldn't reach the update channel.")
            manifest.versionCode > currentVersionCode ->
                Available(manifest.versionName, manifest.apkUrl, manifest.notes)
            else -> UpToDate(currentVersionName)
        }
    }
}
