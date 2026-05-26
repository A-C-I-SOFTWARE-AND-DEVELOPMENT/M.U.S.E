package com.aci.hermes.data.orchestrator

import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PromptBuilderTest {

    private val builder = PromptBuilder()

    @Test fun every_target_renders_full_section_set() {
        for (target in TargetTool.entries) {
            val task = HermesTask(title = "demo", description = "do the thing", targetTool = target)
            val out = builder.build(task, DefaultToolProfiles.byTargetTool(target))
            val expectedSections = listOf(
                "## Role",
                "## Goal",
                "## Project context",
                "## Files or workspace notes",
                "## Constraints",
                "## Safety requirements",
                "## Desired output",
                "## Acceptance criteria",
                "## Build / test instructions",
                "## Return format",
            )
            for (section in expectedSections) {
                assertTrue("missing $section for $target", out.contains(section))
            }
        }
    }

    @Test fun safety_block_is_invariant_across_targets() {
        val seen = mutableSetOf<String>()
        for (target in TargetTool.entries) {
            val task = HermesTask(title = "x", description = "y", targetTool = target)
            val rendered = builder.build(task, DefaultToolProfiles.byTargetTool(target))
            val safetyStart = rendered.indexOf("## Safety requirements")
            val safetyEnd = rendered.indexOf("\n## ", startIndex = safetyStart + 1)
            seen += rendered.substring(safetyStart, safetyEnd)
        }
        assertTrue("safety block diverged across targets: ${seen.size} variants", seen.size == 1)
    }

    @Test fun codex_target_pulls_in_build_test_constraint() {
        val task = HermesTask(title = "build", description = "x", targetTool = TargetTool.CODEX)
        val out = builder.build(task, DefaultToolProfiles.byTargetTool(TargetTool.CODEX))
        assertTrue(out.contains("./gradlew assembleDebug"))
    }

    @Test fun review_task_demands_repro_line_in_acceptance() {
        val task = HermesTask(
            title = "audit", description = "x",
            targetTool = TargetTool.CLAUDE_CODE, taskType = TaskType.REVIEW,
        )
        val out = builder.build(task, DefaultToolProfiles.byTargetTool(TargetTool.CLAUDE_CODE))
        assertTrue(out.contains("reproducible"))
    }

    @Test fun manual_handoff_works_with_null_profile() {
        val task = HermesTask(title = "x", description = "y", targetTool = TargetTool.MANUAL)
        val out = builder.build(task, null)
        assertFalse("Builder must not throw on null profile", out.isBlank())
        assertTrue(out.contains("Manual handoff"))
    }
}
