package com.aci.hermes.data.devicecontrol

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** The append-only device-action ledger: append, bound, and persist. */
class DeviceActionLedgerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private fun entry(label: String, ts: Long = 0L) = DeviceActionLogEntry(
        timestamp = ts,
        intentLabel = label,
        sensitivity = DeviceActionSensitivity.STANDARD,
        outcome = DeviceActionLogEntry.Outcome.APPROVED,
    )

    @Test
    fun `records append in order and are exposed via the flow`() = runBlocking {
        val ledger = DeviceActionLedger(tempFolder.root)
        ledger.record(entry("a", 1))
        ledger.record(entry("b", 2))
        assertEquals(listOf("a", "b"), ledger.entries.value.map { it.intentLabel })
    }

    @Test
    fun `ledger is bounded to MAX_ENTRIES keeping the newest`() = runBlocking {
        val ledger = DeviceActionLedger(tempFolder.root)
        repeat(DeviceActionLogEntry.MAX_ENTRIES + 25) { i -> ledger.record(entry("e$i", i.toLong())) }
        val entries = ledger.entries.value
        assertEquals(DeviceActionLogEntry.MAX_ENTRIES, entries.size)
        // Oldest rolled off; the newest is retained.
        assertEquals("e${DeviceActionLogEntry.MAX_ENTRIES + 24}", entries.last().intentLabel)
    }

    @Test
    fun `entries survive a reload from disk`() = runBlocking {
        val first = DeviceActionLedger(tempFolder.root)
        first.record(entry("persisted", 7))

        val second = DeviceActionLedger(tempFolder.root)
        second.load()
        assertEquals(listOf("persisted"), second.entries.value.map { it.intentLabel })
    }
}
