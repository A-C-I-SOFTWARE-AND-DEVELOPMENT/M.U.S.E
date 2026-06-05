package com.aci.hermes.ui.screens.audit

import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.testutil.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AuditDetailViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(UnconfinedTestDispatcher())

    @Test
    fun `resolves the record for a known id`() = runTest {
        val repo = AuditRepository()
        val target = repo.records.value.first()
        val vm = AuditDetailViewModel(repo, target.id)
        advanceUntilIdle()
        val state = vm.state.value
        assertEquals(target.id, state.record?.id)
        assertFalse(state.notFound)
    }

    @Test
    fun `unknown id is reported as not found`() = runTest {
        val repo = AuditRepository()
        val vm = AuditDetailViewModel(repo, "no-such-audit-id")
        advanceUntilIdle()
        assertTrue(vm.state.value.notFound)
        assertEquals(null, vm.state.value.record)
    }
}
