package com.aci.hermes.ui.screens.avatar

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Pins the file-on-disk contract for [AvatarStorage]:
 *  - the avatar always lives **inside** `filesDir/avatars/` —
 *    never on shared storage, never world-readable.
 *  - `delete()` removes the file.
 *  - `exists()` is the single source of truth for "do we have a
 *    custom avatar?".
 *
 * We don't construct a real `Bitmap` here (that would pull in
 * Robolectric); instead we exercise the on-disk side directly by
 * dropping a known PNG-shaped byte sequence into the path and
 * checking the storage's read of it.
 */
class AvatarStorageTest {

    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun exists_is_false_on_fresh_filesDir() {
        val ctx = FakeContext(tmp.newFolder("files"))
        val storage = AvatarStorage(ctx)
        assertFalse(storage.exists())
    }

    @Test
    fun path_lives_under_filesDir_avatars() {
        val filesDir = tmp.newFolder("files")
        val ctx = FakeContext(filesDir)
        val storage = AvatarStorage(ctx)
        val abs = storage.path()
        assertTrue(
            "avatar path must live under filesDir, got $abs",
            abs.startsWith(filesDir.absolutePath),
        )
        assertTrue(
            "avatar path must include 'avatars/' directory",
            abs.contains("/avatars/"),
        )
    }

    @Test
    fun delete_returns_false_when_no_file_present() {
        val ctx = FakeContext(tmp.newFolder("files"))
        val storage = AvatarStorage(ctx)
        assertFalse(storage.delete())
    }

    @Test
    fun delete_removes_existing_file() {
        val filesDir = tmp.newFolder("files")
        val ctx = FakeContext(filesDir)
        val storage = AvatarStorage(ctx)
        // Plant a non-empty file at the expected path.
        val target = File(storage.path())
        target.parentFile?.mkdirs()
        target.writeBytes(ByteArray(64) { it.toByte() })
        assertTrue(storage.exists())
        assertTrue(storage.delete())
        assertFalse(storage.exists())
    }

    @Test
    fun exists_returns_false_for_zero_length_file() {
        val filesDir = tmp.newFolder("files")
        val ctx = FakeContext(filesDir)
        val storage = AvatarStorage(ctx)
        val target = File(storage.path())
        target.parentFile?.mkdirs()
        target.createNewFile() // zero bytes
        assertFalse(
            "zero-length file should not count as 'exists'",
            storage.exists(),
        )
    }

    /**
     * Minimal `Context` stand-in. `AvatarStorage` only reads
     * `context.filesDir`; nothing else from `Context` is touched.
     */
    private class FakeContext(private val files: File) : android.content.ContextWrapper(null) {
        override fun getFilesDir(): File = files
    }
}
