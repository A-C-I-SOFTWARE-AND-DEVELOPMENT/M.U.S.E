package com.aci.hermes.util

import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * In-memory ring buffer of log entries surfaced in the Diagnostics screen.
 * Also forwards to Logcat so logs are visible via `adb logcat` during
 * development.
 *
 * Hard-capped at [MAX_ENTRIES] entries so we cannot grow unboundedly even
 * during a flood of SSE events.
 */
class LogBuffer {

    enum class Level { INFO, WARN, ERROR }

    data class Entry(
        val timestamp: Long,
        val level: Level,
        val tag: String,
        val message: String
    ) {
        fun format(): String {
            val ts = SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(Date(timestamp))
            return "$ts ${level.name.padEnd(5)} $tag: $message"
        }
    }

    private val _entries = MutableStateFlow<List<Entry>>(emptyList())
    val entries: StateFlow<List<Entry>> = _entries

    private val _lastError = MutableStateFlow<Entry?>(null)
    val lastError: StateFlow<Entry?> = _lastError

    fun info(tag: String, message: String) = log(Level.INFO, tag, message)
    fun warn(tag: String, message: String) = log(Level.WARN, tag, message)
    fun error(tag: String, message: String) = log(Level.ERROR, tag, message)

    fun clear() {
        _entries.value = emptyList()
        _lastError.value = null
    }

    private fun log(level: Level, tag: String, message: String) {
        val entry = Entry(System.currentTimeMillis(), level, tag, message)
        when (level) {
            Level.INFO -> Log.i(tag, message)
            Level.WARN -> Log.w(tag, message)
            Level.ERROR -> {
                Log.e(tag, message)
                _lastError.value = entry
            }
        }
        // `update` is atomic — OkHttp dispatcher threads and Main can both
        // call this concurrently during streaming and we'd otherwise drop
        // entries in the read-modify-write window.
        _entries.update { (it + entry).takeLast(MAX_ENTRIES) }
    }

    companion object {
        const val MAX_ENTRIES = 200
    }
}
