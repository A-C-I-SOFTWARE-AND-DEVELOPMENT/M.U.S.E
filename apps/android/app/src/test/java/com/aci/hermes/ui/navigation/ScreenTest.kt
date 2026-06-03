package com.aci.hermes.ui.navigation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for the Jarvis Prime route model. These run on the JVM without
 * an emulator, so they cover the route catalog and bottom-nav wiring without
 * exercising Compose rendering.
 */
class ScreenTest {

    private val requiredScreens: List<Screen> = listOf(
        Screen.Splash,
        Screen.Onboarding,
        Screen.Home,
        Screen.Chat,
        Screen.Jobs,
        Screen.Tasks,
        Screen.Approvals,
        Screen.Memory,
        Screen.Audit,
        Screen.Control,
        Screen.Settings,
        Screen.Diagnostics,
        Screen.TaskDetail,
        Screen.JobDetail,
    )

    @Test
    fun every_required_screen_has_a_unique_route() {
        val routes = requiredScreens.map { it.route }
        assertEquals(
            "Every required screen should have a unique route",
            routes.size,
            routes.toSet().size,
        )
    }

    @Test
    fun every_required_screen_has_a_non_blank_route() {
        for (screen in requiredScreens) {
            assertTrue(
                "Route for ${screen.javaClass.simpleName} must not be blank",
                screen.route.isNotBlank(),
            )
        }
    }

    @Test
    fun home_is_a_shell_destination() {
        assertTrue(
            "Home must render inside the shell so it is the primary landing surface",
            Screen.Home.route in Screen.shellRoutes,
        )
    }

    @Test
    fun all_main_destinations_are_shell_routes() {
        // Capability is rendered inside JarvisShell (the nav graph wraps
        // it in ShellHost) but intentionally not on the bottom nav — it
        // is reached from Home quick-links and Settings. It still
        // belongs in shellRoutes so the shell wrapper drives its
        // top-bar / emergency-stop chrome.
        val expectedShellRoutes = setOf(
            Screen.Home.route,
            Screen.Chat.route,
            Screen.Jobs.route,
            Screen.Tasks.route,
            Screen.Approvals.route,
            Screen.Memory.route,
            Screen.Audit.route,
            Screen.Capability.route,
            Screen.Control.route,
        )
        assertEquals(expectedShellRoutes, Screen.shellRoutes)
    }

    @Test
    fun emergency_stop_path_exists_via_orchestrator_service_controller() {
        // Compile-time pin: every shell-wrapped destination surfaces
        // emergency stop via OrchestratorServiceController.emergencyStop.
        // If that symbol disappears or is renamed, the launch surface
        // loses its emergency stop and this test stops passing.
        val method = com.aci.hermes.service.OrchestratorServiceController::class.java.declaredMethods
            .firstOrNull { it.name == "emergencyStop" }
        assertNotNull(
            "OrchestratorServiceController.emergencyStop() must exist on the launch surface",
            method,
        )
    }

    @Test
    fun full_screen_pushes_are_not_shell_routes() {
        val fullScreenRoutes = listOf(
            Screen.Splash.route,
            Screen.Onboarding.route,
            Screen.Settings.route,
            Screen.Diagnostics.route,
            Screen.TaskDetail.route,
        )
        for (route in fullScreenRoutes) {
            assertTrue(
                "$route must NOT be inside the JarvisShell (it owns its own top bar)",
                route !in Screen.shellRoutes,
            )
        }
    }

    @Test
    fun bottom_tabs_cover_the_advertised_navigation_targets() {
        val bottomRoutes = Screen.bottomTabs.map { it.screen.route }.toSet()
        val expected = setOf(
            Screen.Home.route,
            Screen.Jobs.route,
            Screen.Chat.route,
            Screen.Approvals.route,
            Screen.Control.route,
        )
        assertEquals(
            "Bottom navigation must surface Home, Jobs, Chat, Approvals, and Control",
            expected,
            bottomRoutes,
        )
    }

    @Test
    fun legacy_tasks_stays_reachable_as_a_shell_route() {
        // The Jobs cockpit takes the bottom tab; the legacy clipboard-handoff
        // Tasks list is preserved as a shell destination (reached from Home).
        assertTrue(Screen.Tasks.route in Screen.shellRoutes)
        assertTrue(Screen.Tasks.route !in Screen.bottomTabs.map { it.screen.route })
    }

    @Test
    fun task_detail_route_builders_produce_expected_paths() {
        assertEquals("task_detail/abc", Screen.TaskDetail.forTask("abc"))
        assertEquals("task_detail/new", Screen.TaskDetail.forNew())
        assertEquals("task_detail/new?target=CODEX", Screen.TaskDetail.forNew("CODEX"))
    }

    @Test
    fun job_detail_route_builder_produces_expected_path() {
        assertEquals("job_detail/job_123", Screen.JobDetail.forJob("job_123"))
    }

    @Test
    fun every_bottom_tab_resolves_to_a_known_screen() {
        for (tab in Screen.bottomTabs) {
            assertNotNull(tab.screen)
            assertTrue(
                "Bottom tab ${tab.labelKey} must point to a shell route",
                tab.screen.route in Screen.shellRoutes,
            )
        }
    }
}
