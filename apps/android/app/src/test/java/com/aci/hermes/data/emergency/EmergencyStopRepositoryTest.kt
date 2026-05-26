package com.aci.hermes.data.emergency

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class EmergencyStopRepositoryTest {

    @get:Rule val tempDir = TemporaryFolder()

    @Test
    fun `commit writes and load reads the latest state`() = runTest {
        val baseDir = tempDir.newFolder("filesDir")
        val repo = EmergencyStopRepository(baseDir = baseDir)
        repo.commit(
            state = EmergencyStopState.LOCKDOWN,
            event = EmergencyStopAuditEvent(
                timestamp = 42L,
                type = EmergencyStopAuditEvent.EventType.ENGAGE,
                from = EmergencyStopState.INACTIVE,
                to = EmergencyStopState.LOCKDOWN,
                source = "test",
                reason = "drill",
            ),
        )

        val fresh = EmergencyStopRepository(baseDir = baseDir)
        fresh.load()
        assertEquals(EmergencyStopState.LOCKDOWN, fresh.state.value)
        assertEquals(1, fresh.audit.value.size)
        assertEquals("drill", fresh.audit.value.first().reason)
    }

    @Test
    fun `snapshot json is parseable round-trip`() = runTest {
        val baseDir = tempDir.newFolder("filesDir")
        val repo = EmergencyStopRepository(baseDir = baseDir)
        repo.commit(state = EmergencyStopState.HARD_STOP)
        val json = repo.snapshotJson()
        assertTrue(json.contains("HARD_STOP"))
        assertTrue(File(baseDir, EmergencyStopRepository.FILE_NAME).exists())
    }

    @Test
    fun `clearApproval removes pending approval`() = runTest {
        val baseDir = tempDir.newFolder("filesDir")
        val repo = EmergencyStopRepository(baseDir = baseDir)
        repo.setPendingApproval(
            ResumeApproval(
                id = "abc",
                requestedAt = 1L,
                fromState = EmergencyStopState.HARD_STOP,
                requestedBy = "tester",
            ),
        )
        assertEquals("abc", repo.pendingApproval.value?.id)

        repo.commit(state = EmergencyStopState.INACTIVE, clearApproval = true)
        assertNull(repo.pendingApproval.value)
    }
}
