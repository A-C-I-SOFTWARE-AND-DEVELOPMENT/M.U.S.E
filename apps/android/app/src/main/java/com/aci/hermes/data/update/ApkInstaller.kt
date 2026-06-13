package com.aci.hermes.data.update

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File

/**
 * Downloads a MUSE APK and launches the system package installer to apply it.
 *
 * Everything here is **visible and user-approved**: DownloadManager shows a
 * system download notification, and the install always goes through the OS
 * package-installer UI (the user taps "Install"/"Update"). If the app hasn't
 * been granted "install unknown apps" we send the user to the system settings
 * screen to grant it first. There is no silent, background, or self-reinstall
 * path — installing a newer build over the current one is how it "updates".
 */
object ApkInstaller {
    private const val APK_NAME = "muse-update.apk"
    private const val APK_MIME = "application/vnd.android.package-archive"

    /** True once the user has granted us "install unknown apps". */
    fun canInstall(context: Context): Boolean =
        context.packageManager.canRequestPackageInstalls()

    /** Open the system screen where the user grants install permission to MUSE. */
    fun requestInstallPermission(context: Context) {
        val intent = Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:${context.packageName}"),
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    /**
     * Visibly download [apkUrl] and, on completion, launch the system package
     * installer. The download surfaces in the notification shade; the install
     * is the standard OS confirmation dialog.
     */
    fun downloadAndInstall(context: Context, apkUrl: String) {
        val app = context.applicationContext
        val downloadManager =
            app.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager

        // Clear any stale copy so the installer always sees the fresh download.
        File(app.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), APK_NAME)
            .takeIf { it.exists() }
            ?.delete()

        val request = DownloadManager.Request(Uri.parse(apkUrl))
            .setTitle("MUSE update")
            .setDescription("Downloading the latest MUSE build")
            .setMimeType(APK_MIME)
            .setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED,
            )
            .setDestinationInExternalFilesDir(app, Environment.DIRECTORY_DOWNLOADS, APK_NAME)
        val downloadId = downloadManager.enqueue(request)

        // One-shot receiver: when *our* download finishes, launch the installer.
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                val finishedId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L)
                if (finishedId != downloadId) return
                try {
                    app.unregisterReceiver(this)
                } catch (_: IllegalArgumentException) {
                    // Already unregistered — ignore.
                }
                launchInstaller(app)
            }
        }
        // ACTION_DOWNLOAD_COMPLETE is a system broadcast; flag exported so the
        // context-registered receiver is accepted on Android 13+ (API 33+).
        ContextCompat.registerReceiver(
            app,
            receiver,
            IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE),
            ContextCompat.RECEIVER_EXPORTED,
        )
    }

    private fun launchInstaller(context: Context) {
        val file = File(
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),
            APK_NAME,
        )
        if (!file.exists()) return
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file,
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, APK_MIME)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
