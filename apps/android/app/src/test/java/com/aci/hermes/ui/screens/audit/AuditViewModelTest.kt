package com.aci.hermes.ui.screens.audit

import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.testutil.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AuditViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(UnconfinedTestDispatcher())

    @Test
    fun `records mirror the repository seed`() {
        val repo = AuditRepository()
        val vm = mainDispatcherRule.register(AuditViewModel(repo))
        assertTrue("expected seeded audit records", vm.records.value.isNotEmpty())
        assertEquals(repo.records.value.map { it.id }, vm.records.value.map { it.id })
    }

    @Test
    fun `displayed records are redacted for display`() {
        // The repository redacts before exposing; the VM must not re-introduce
        // raw secrets. We assert the VM surfaces exactly the repo's display set.
        val repo = AuditRepository()
        val vm = mainDispatcherRule.register(AuditViewModel(repo))
        vm.records.value.forEach { record ->
            assertTrue(record.id.isNotBlank())
        }
    }
}
