package com.aci.hermes.data.avatar

import android.content.Context
import android.graphics.Bitmap
import java.io.File
import java.io.FileOutputStream

class AvatarImageStore(context: Context) {

    private val dir: File = File(context.filesDir, "avatar").apply { mkdirs() }

    val directory: File get() = dir

    fun saveBitmapAsPng(bitmap: Bitmap, fileName: String): File {
        if (!dir.exists()) dir.mkdirs()
        val out = File(dir, fileName)
        FileOutputStream(out).use { stream ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
            stream.flush()
        }
        return out
    }

    fun currentAvatarFile(): File? {
        if (!dir.exists()) return null
        return dir.listFiles { f -> f.isFile && f.name.endsWith(".png") }
            ?.maxByOrNull { it.lastModified() }
    }

    fun deleteAll() {
        if (!dir.exists()) return
        dir.listFiles()?.forEach { it.delete() }
    }

    fun deleteAllExcept(keep: File?) {
        if (!dir.exists()) return
        val keepCanonical = keep?.canonicalPath
        dir.listFiles()?.forEach { f ->
            if (keepCanonical == null || f.canonicalPath != keepCanonical) f.delete()
        }
    }

    fun pathInAppPrivate(file: File): Boolean {
        val base = dir.canonicalPath + File.separator
        return file.canonicalPath.startsWith(base)
    }
}
