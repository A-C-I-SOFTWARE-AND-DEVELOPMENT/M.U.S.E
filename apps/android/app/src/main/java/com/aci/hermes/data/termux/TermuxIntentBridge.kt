package com.aci.hermes.data.termux

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri

/**
 * Phase 18 cockpit ↔ Termux intent bridge — stub.
 *
 * The wire shape and required permissions are specified in
 * docs/android/termux-intent-bridge.md. This stub gives the cockpit UI
 * a typed entry point to build against; the live implementation
 * (RUN_COMMAND envelope, wake-lock acquisition, status polling) lands
 * with the cockpit-screen work in a follow-up phase.
 *
 * Every method here is callable safely from any thread because the
 * Android Intent system is already thread-safe. The stub does not
 * persist anything, does not touch the network, and does not require
 * any new permissions in the manifest at this phase.
 */
class TermuxIntentBridge(private val context: Context) {

    /** Whether Termux is installed and visible to the package manager. */
    fun isTermuxInstalled(): Boolean = runCatching {
        context.packageManager.getPackageInfo(TERMUX_PACKAGE, 0)
        true
    }.getOrDefault(false)

    /** Best-effort detection of the Termux:Files companion app. */
    fun isTermuxFilesInstalled(): Boolean = runCatching {
        context.packageManager.getPackageInfo(TERMUX_FILES_PACKAGE, 0)
        true
    }.getOrDefault(false)

    /**
     * Build (without firing) the RUN_COMMAND intent for an `hermes`
     * subcommand. Centralised so future call sites cannot drift in how
     * they fill the envelope — see `termux-intent-bridge.md` §3.
     */
    fun buildHermesIntent(
        args: List<String>,
        workdir: String = TERMUX_HOME,
        background: Boolean = true,
    ): Intent {
        require(args.isNotEmpty()) { "hermes command requires at least one argument" }
        return Intent(ACTION_RUN_COMMAND).apply {
            setClassName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE)
            putExtra(EXTRA_PATH, HERMES_BIN)
            putExtra(EXTRA_ARGUMENTS, args.toTypedArray())
            putExtra(EXTRA_WORKDIR, workdir)
            putExtra(EXTRA_BACKGROUND, background)
            putExtra(EXTRA_SESSION_ACTION, if (background) SESSION_BACKGROUND else SESSION_OPEN)
        }
    }

    /**
     * Build (without firing) an ACTION_VIEW intent for a job
     * workspace, suitable for Termux:Files. Caller chooses whether to
     * use the file:// URI directly or wrap via FileProvider — for
     * paths under `/data/data/com.termux/files/...` Termux:Files
     * accepts the file URI; for any other location the caller should
     * use a FileProvider URI.
     */
    fun buildOpenJobFolderIntent(workspacePath: String): Intent {
        val uri = Uri.parse("file://$workspacePath")
        return Intent(Intent.ACTION_VIEW).apply {
            setPackage(TERMUX_FILES_PACKAGE)
            setDataAndType(uri, MIME_DIRECTORY)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    /**
     * Build an intent that opens the standard Termux launcher activity
     * so the user lands in a normal shell. Used when Termux:Files is
     * absent and the user picked "Open job folder".
     */
    fun buildOpenTermuxIntent(): Intent? {
        val pm = context.packageManager
        return pm.getLaunchIntentForPackage(TERMUX_PACKAGE)?.apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    /**
     * Sentinel: returns the canonical loopback URL for the on-device
     * Termux gateway. The cockpit's Settings screen overrides this if
     * the user is running on a non-default port.
     */
    val localGatewayUrl: String = LOCAL_GATEWAY_URL

    companion object {
        const val TERMUX_PACKAGE = "com.termux"
        const val TERMUX_FILES_PACKAGE = "com.termux.files"

        const val RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
        const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"

        const val EXTRA_PATH = "com.termux.RUN_COMMAND_PATH"
        const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
        const val EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR"
        const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"
        const val EXTRA_SESSION_ACTION = "com.termux.RUN_COMMAND_SESSION_ACTION"

        const val SESSION_BACKGROUND = "0"
        const val SESSION_OPEN = "1"

        const val TERMUX_PREFIX = "/data/data/com.termux/files/usr"
        const val TERMUX_HOME = "/data/data/com.termux/files/home"
        const val HERMES_BIN = "$TERMUX_PREFIX/bin/hermes"

        const val MIME_DIRECTORY = "resource/folder"

        const val LOCAL_GATEWAY_URL = "http://127.0.0.1:8080"
    }
}

/**
 * Canonical action set the cockpit's Termux Control Panel exposes.
 * Centralised so screen, ViewModel, and tests share the same enum.
 */
enum class TermuxBridgeAction {
    START_GATEWAY,
    STOP_GATEWAY,
    RESTART_GATEWAY,
    OPEN_TERMUX,
    OPEN_JOB_FOLDER,
    TAIL_LOGS,
}

/** Result returned from a fired RUN_COMMAND, surfaced to the UI. */
sealed interface TermuxFireResult {
    data object Sent : TermuxFireResult
    data class TermuxMissing(val message: String) : TermuxFireResult
    data class PermissionDenied(val message: String) : TermuxFireResult
    data class Failed(val cause: Throwable) : TermuxFireResult
}
