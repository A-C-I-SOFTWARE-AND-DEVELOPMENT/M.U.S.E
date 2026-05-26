package com.aci.hermes.data.skills

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.ApprovalSeverity
import com.aci.hermes.data.model.SkillDescriptor
import kotlinx.coroutines.flow.StateFlow

/**
 * Skill / capability catalog the user can toggle on or off.
 *
 * On-device only. Disabling a skill prevents Jarvis Prime from
 * surfacing approval cards or task suggestions that depend on it.
 */
class SkillsRepository(context: Context) {

    private val store = JsonStore(
        context = context,
        fileName = "jarvis_skills.json",
        serializer = SkillDescriptor.serializer(),
    )

    val items: StateFlow<List<SkillDescriptor>> = store.items

    suspend fun load() {
        store.load()
        if (store.items.value.isEmpty()) {
            store.replace(DEFAULTS)
        }
    }

    suspend fun setEnabled(id: String, enabled: Boolean) {
        store.update({ it.id == id }) { it.copy(enabled = enabled) }
    }

    suspend fun reset() {
        store.replace(DEFAULTS)
    }

    companion object {
        val DEFAULTS: List<SkillDescriptor> = listOf(
            SkillDescriptor(
                id = "conversation",
                displayName = "Conversation",
                description = "Hold a back-and-forth chat with Jarvis Prime.",
                category = "Core",
                enabled = true,
            ),
            SkillDescriptor(
                id = "voice_capture",
                displayName = "Voice capture",
                description = "One-shot voice input. Mic only opens when you tap capture.",
                category = "Core",
                enabled = true,
            ),
            SkillDescriptor(
                id = "task_planning",
                displayName = "Task planning",
                description = "Break work into worker-ready tasks with target tool and prompt.",
                category = "Worker lane",
                enabled = true,
            ),
            SkillDescriptor(
                id = "handoff",
                displayName = "Tool handoff",
                description = "Copy a structured prompt for Codex / Claude / ChatGPT.",
                category = "Worker lane",
                enabled = true,
                requiresApproval = ApprovalSeverity.ROUTINE,
            ),
            SkillDescriptor(
                id = "memory_inference",
                displayName = "Memory inference",
                description = "Suggest facts to remember; you confirm or reject.",
                category = "Memory",
                enabled = true,
                requiresApproval = ApprovalSeverity.RISKY,
            ),
            SkillDescriptor(
                id = "social_signals",
                displayName = "Social signals",
                description = "Surface communication patterns that might be useful.",
                category = "Awareness",
                enabled = true,
            ),
            SkillDescriptor(
                id = "audit_export",
                displayName = "Audit export",
                description = "Export a proof bundle of recent activity.",
                category = "Proof",
                enabled = true,
            ),
            SkillDescriptor(
                id = "gateway_relay",
                displayName = "Gateway relay",
                description = "Receive events from the local Termux gateway.",
                category = "Gateway",
                enabled = false,
                requiresApproval = ApprovalSeverity.SERIOUS,
            ),
            SkillDescriptor(
                id = "destructive_action",
                displayName = "Destructive action",
                description = "Engage critical actions — deploy, push, delete. Requires double-confirm + impact.",
                category = "Action",
                enabled = false,
                requiresApproval = ApprovalSeverity.CRITICAL,
            ),
        )
    }
}
