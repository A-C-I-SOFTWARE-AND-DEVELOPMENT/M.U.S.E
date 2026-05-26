package com.aci.hermes.data.orchestrator

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.core.net.toUri
import com.aci.hermes.data.model.AiToolProfile

/**
 * Safe manual-handoff helpers. Every action here is triggered by an
 * explicit user tap — there is no silent or automated handoff.
 */
object HandoffLauncher {

    /**
     * Copies [text] to the system clipboard. Returns true on success.
     * Callers are responsible for confirming this is the right text
     * to copy — the prompt builder never embeds API keys or tokens,
     * but the user is still asked in the docs not to paste secrets
     * into task descriptions.
     */
    fun copyPrompt(context: Context, label: String, text: String): Boolean {
        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            ?: return false
        cm.setPrimaryClip(ClipData.newPlainText(label, text))
        return true
    }

    /**
     * Attempts to open the official tool for [profile]. If
     * [allowExternal] is false, returns [LaunchResult.Blocked] — the
     * dashboard surfaces manual instructions in that case.
     *
     * Best-effort: tries known package launch intents first, then
     * falls back to the profile's web URL via ACTION_VIEW. We do not
     * declare any `<queries>` in the manifest — that means
     * `getLaunchIntentForPackage` may return null on Android 11+ for
     * packages the user has installed but we can't see; that's an
     * acceptable degradation since the web fallback handles it.
     */
    fun openOfficialTool(
        context: Context,
        profile: AiToolProfile,
        allowExternal: Boolean,
    ): LaunchResult {
        if (!allowExternal) return LaunchResult.Blocked
        val pm = context.packageManager

        for (pkg in profile.candidatePackages) {
            val launch = pm.getLaunchIntentForPackage(pkg) ?: continue
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            val launched = runCatching { context.startActivity(launch) }.isSuccess
            if (launched) return LaunchResult.Opened(via = "package:$pkg")
        }

        val fallback = profile.webFallbackUrl
        if (fallback != null) {
            val intent = Intent(Intent.ACTION_VIEW, fallback.toUri()).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            val launched = try {
                context.startActivity(intent); true
            } catch (_: ActivityNotFoundException) {
                false
            } catch (_: SecurityException) {
                false
            }
            if (launched) return LaunchResult.Opened(via = "web:$fallback")
        }

        return LaunchResult.ManualOnly(
            message = "No installed app or browser fallback resolved for ${profile.displayName}."
        )
    }

    sealed interface LaunchResult {
        data class Opened(val via: String) : LaunchResult
        data class ManualOnly(val message: String) : LaunchResult
        data object Blocked : LaunchResult
    }
}
