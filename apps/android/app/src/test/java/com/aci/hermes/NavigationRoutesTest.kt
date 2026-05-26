package com.aci.hermes

import com.aci.hermes.ui.navigation.Screen
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-Kotlin checks against the route catalog. The full navigation
 * runtime is covered by Compose UI tests separately.
 */
class NavigationRoutesTest {

    @Test
    fun all_routes_are_listed_in_companion() {
        val expected = listOf(
            "splash",
            "onboarding",
            "home",
            "chat",
            "voice",
            "tasks",
            "approvals",
            "memory",
            "social",
            "audit",
            "approval_detail/{approvalId}",
            "audit_detail/{auditId}",
            "task_detail/{taskId}?target={target}",
            "settings",
            "diagnostics",
        )
        assertEquals(expected, Screen.allRoutes)
    }

    @Test
    fun approval_detail_route_substitutes_id() {
        assertEquals("approval_detail/abc", Screen.ApprovalDetail.route("abc"))
    }

    @Test
    fun audit_detail_route_substitutes_id() {
        assertEquals("audit_detail/abc", Screen.AuditDetail.route("abc"))
    }

    @Test
    fun task_detail_for_new_with_target_includes_query() {
        assertEquals("task_detail/new?target=CODEX", Screen.TaskDetail.forNew("CODEX"))
    }

    @Test
    fun core_jarvis_routes_present() {
        listOf("home", "chat", "voice", "approvals", "memory", "social", "audit")
            .forEach { assertTrue("missing $it", it in Screen.allRoutes) }
    }
}
