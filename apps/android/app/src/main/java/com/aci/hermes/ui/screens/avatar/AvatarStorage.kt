package com.aci.hermes.ui.screens.avatar

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.File
import java.io.FileOutputStream

/**
 * Local-only storage for user-generated avatars.
 *
 * The user-picked image is pixelated on-device by [AvatarPixelator]
 * and written here. The destination is **app-private** —
 * `context.filesDir/avatars/user_avatar.png` — never world-readable,
 * never uploaded.
 *
 * The class intentionally does not import any network type. Its only
 * dependencies are `android.content.Context`, `android.graphics.*`,
 * and `java.io.*`. The picker view-model is similarly network-free;
 * an AST scan in `AvatarPickerNoUploadTest` pins the invariant.
 */
class AvatarStorage(
    private val context: Context,
    private val directoryName: String = AVATAR_DIR,
    private val fileName: String = AVATAR_FILE,
) {

    companion object {
        internal const val AVATAR_DIR: String = "avatars"
        internal const val AVATAR_FILE: String = "user_avatar.png"
    }

    private val dir: File get() = File(context.filesDir, directoryName).also { it.mkdirs() }
    private val file: File get() = File(dir, fileName)

    /** True iff a user-generated avatar exists on disk. */
    fun exists(): Boolean = file.exists() && file.length() > 0L

    /**
     * Absolute path the user-generated avatar lives at. Always inside
     * `context.filesDir`; the picker view-model exposes this as a
     * `JarvisAvatarProfile.Source.UserGenerated.filePath`.
     */
    fun path(): String = file.absolutePath

    /**
     * Save [bitmap] as the current user avatar. Returns the path
     * written. Throws on I/O failure.
     */
    fun save(bitmap: Bitmap): String {
        val target = file
        FileOutputStream(target).use { out ->
            bitmap.compress(Bitmap.CompressFormat.PNG, /* quality */ 100, out)
            out.flush()
        }
        return target.absolutePath
    }

    /** Load the saved user avatar, or null if none exists. */
    fun load(): Bitmap? {
        if (!exists()) return null
        return BitmapFactory.decodeFile(file.absolutePath)
    }

    /** Remove the saved user avatar. Returns true if a file was deleted. */
    fun delete(): Boolean = if (file.exists()) file.delete() else false
}
