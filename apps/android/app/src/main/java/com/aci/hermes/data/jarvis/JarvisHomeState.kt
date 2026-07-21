package com.aci.hermes.data.jarvis

import com.aci.hermes.data.cockpit.CockpitHomeSnapshot
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.voice.VoicePhase
import java.time.OffsetDateTime

/**
 * Single source of truth for the muse home screen.
 *
 * The screen reads one [JarvisHomeState] and renders every component
 * (icon, header, ask bar, voice button, cards) directly from it. State
 * derivation is a pure function ([JarvisHomeStateDeriver.derive]) so the
 * rules are testable without a running Android runtime.
 */
data class JarvisHomeState(
    val presence: JarvisPresence = JarvisPresence.IDLE,
    val gateway: GatewayStatus = GatewayStatus.CONNECTED,
    val mockMode: Boolean = false,
    val emergencyStopActive: Boolean = false,
    val activeTask: ActiveTaskSnapshot? = null,
    val pendingApprovals: List<PendingApproval> = emptyList(),
    val workers: List<WorkerStatus> = emptyList(),
    val memoryPulse: List<MemoryPulseEntry> = emptyList(),
    val suggestedNextAction: SuggestedAction? = null,
    // ── Live backend overlay (populated from the cockpit gateway) ──────────
    val backendSync: HomeBackendSync = HomeBackendSync.UNKNOWN,
    val backendMessage: String? = null,
    val modelRouter: ModelRouterSummary? = null,
    val cockpitJobs: List<JobSummary> = emptyList(),
    val auditEvents: List<AuditEventSummary> = emptyList(),
    val evidence: List<EvidenceSummary> = emptyList(),
    val deviceCapability: DeviceCapabilitySummary? = null,
    val voicePhase: VoicePhase = VoicePhase.DORMANT,
) {
    val hasCriticalApproval: Boolean get() = pendingApprovals.any { it.risk == ApprovalRisk.CRITICAL }
    val hasSeriousApproval: Boolean get() = pendingApprovals.any { it.risk == ApprovalRisk.SERIOUS }
    val hasAnyApproval: Boolean get() = pendingApprovals.isNotEmpty()

    /** True when a paired gateway is answering — drives the live/offline UI. */
    val backendLive: Boolean get() = backendSync == HomeBackendSync.LIVE
}

/**
 * How the live backend overlay was sourced. [UNKNOWN] is the pre-refresh
 * default; the rest mirror [com.aci.hermes.data.cockpit.HomeSync] so the
 * home screen can show a *useful* (never blank) state when the gateway is
 * unpaired or unreachable.
 */
enum class HomeBackendSync { UNKNOWN, LIVE, NOT_PAIRED, OFFLINE }

/** Compact model/router policy line for the home Model card. */
data class ModelRouterSummary(
    val headline: String,
    val detail: String,
    val freeFirst: Boolean?,
)

/** One cockpit job, projected for the home Jobs card. */
data class JobSummary(
    val id: String,
    val title: String,
    val worker: String,
    val status: JobStatus?,
    val statusLabel: String,
    val active: Boolean,
)

/** One decision-ledger event, projected for the home Audit card. */
data class AuditEventSummary(
    val timestamp: Long?,
    val level: String,
    val source: String,
    val message: String,
)

/** One Research Vault artifact, projected for the home Evidence card. */
data class EvidenceSummary(
    val id: String,
    val title: String,
    val strength: String,
    val summary: String,
)

/** On-device capability line for the home Device card. */
data class DeviceCapabilitySummary(
    val headline: String,
    val detail: String,
)

/**
 * The 11 visible presence states declared in the brief. Transient states
 * (LISTENING, THINKING) are driven by the UI layer through
 * [JarvisHomeViewModel] direct setters; the rest are derived from the
 * service + task state.
 */
enum class JarvisPresence {
    IDLE,
    LISTENING,
    THINKING,
    WORKING,
    WAITING_FOR_APPROVAL,
    SERIOUS_ACTION_PENDING,
    CRITICAL_ACTION_PENDING,
    GATEWAY_DISCONNECTED,
    SERVICE_STOPPED,
    EMERGENCY_STOP_ACTIVE,
    OFFLINE_MOCK,
}

enum class GatewayStatus { CONNECTED, DEGRADED, DISCONNECTED }

enum class ApprovalRisk { LOW, SERIOUS, CRITICAL }

data class ActiveTaskSnapshot(
    val taskId: String,
    val title: String,
    val taskType: TaskType,
    val status: TaskStatus,
    val target: TargetTool,
    val updatedAt: Long,
)

data class PendingApproval(
    val taskId: String,
    val title: String,
    val target: TargetTool,
    val risk: ApprovalRisk,
    val reason: String,
)

data class WorkerStatus(
    val target: TargetTool,
    val displayName: String,
    val busy: Boolean,
    val lastActivityAt: Long?,
)

data class MemoryPulseEntry(
    val timestamp: Long,
    val label: String,
)

data class SuggestedAction(
    val label: String,
    val kind: SuggestedKind,
    val taskId: String? = null,
)

enum class SuggestedKind {
    OPEN_APPROVAL,
    OPEN_ACTIVE_TASK,
    START_SERVICE,
    DEACTIVATE_EMERGENCY_STOP,
    OPEN_CHAT,
    OPEN_VOICE,
}

/**
 * Inputs to the deriver. All sourced from existing repositories — no new
 * remote calls. [serviceRunning] comes from
 * [com.aci.hermes.service.HermesService] presence check; [tasks] from
 * [com.aci.hermes.data.orchestrator.HermesTaskRepository]; the rest from
 * [com.aci.hermes.data.preferences.SettingsRepository].
 */
data class JarvisHomeInputs(
    val serviceRunning: Boolean,
    val tasks: List<HermesTask>,
    val localOnlyMode: Boolean,
    val emergencyStopActive: Boolean,
    val transientPresence: JarvisPresence? = null,
    val nowMs: Long = System.currentTimeMillis(),
    // ── Live overlay inputs (all optional; absent ⇒ pure local derivation) ──
    /** Aggregated cockpit reads; null when unpaired/not-yet-loaded. */
    val cockpit: CockpitHomeSnapshot? = null,
    /** How [cockpit] was sourced — drives the backend-availability UI. */
    val backendSync: HomeBackendSync = HomeBackendSync.UNKNOWN,
    val backendMessage: String? = null,
    val voicePhase: VoicePhase = VoicePhase.DORMANT,
    val deviceCapability: DeviceCapabilitySummary? = null,
)

object JarvisHomeStateDeriver {

    private const val MEMORY_PULSE_SIZE = 6
    private const val WORKER_BUSY_WINDOW_MS = 5 * 60 * 1000L
    private const val AUDIT_EVENTS_SIZE = 6
    private const val EVIDENCE_SIZE = 5

    fun derive(inputs: JarvisHomeInputs): JarvisHomeState {
        val pendingApprovals = inputs.tasks
            .filter { it.status == TaskStatus.NEEDS_REVISION || it.status == TaskStatus.READY_FOR_HANDOFF }
            .map { task ->
                val risk = riskFor(task)
                PendingApproval(
                    taskId = task.id,
                    title = task.title.ifBlank { "(untitled task)" },
                    target = task.targetTool,
                    risk = risk,
                    reason = task.reviewNotes?.takeIf { it.isNotBlank() }
                        ?: defaultApprovalReason(task.status),
                )
            }

        val activeTask = inputs.tasks
            .filter { it.status == TaskStatus.HANDED_TO_CODEX ||
                it.status == TaskStatus.HANDED_TO_CLAUDE ||
                it.status == TaskStatus.IN_REVIEW }
            .maxByOrNull { it.updatedAt }
            ?.let {
                ActiveTaskSnapshot(
                    taskId = it.id,
                    title = it.title.ifBlank { "(untitled task)" },
                    taskType = it.taskType,
                    status = it.status,
                    target = it.targetTool,
                    updatedAt = it.updatedAt,
                )
            }

        val workers = TargetTool.values().filter { it != TargetTool.MANUAL }.map { target ->
            val mostRecent = inputs.tasks.filter { it.targetTool == target }.maxByOrNull { it.updatedAt }
            val isActiveTarget = activeTask?.target == target
            WorkerStatus(
                target = target,
                displayName = displayNameFor(target),
                busy = isActiveTarget || (mostRecent != null &&
                    inputs.nowMs - mostRecent.updatedAt < WORKER_BUSY_WINDOW_MS &&
                    mostRecent.status != TaskStatus.COMPLETE),
                lastActivityAt = mostRecent?.updatedAt,
            )
        }

        val memoryPulse = inputs.tasks
            .sortedByDescending { it.updatedAt }
            .take(MEMORY_PULSE_SIZE)
            .map { MemoryPulseEntry(it.updatedAt, memoryLabel(it)) }

        // ── Live backend overlay ──────────────────────────────────────────
        // When a paired gateway is answering, prefer its data field-by-field;
        // otherwise fall back to the (already-computed) local derivation, so
        // the offline experience is unchanged.
        val live = inputs.cockpit?.takeIf { inputs.backendSync == HomeBackendSync.LIVE }

        val effectiveApprovals = live?.let { backendApprovals(it) } ?: pendingApprovals
        val effectiveWorkers = live?.let { backendWorkers(it) } ?: workers
        val effectiveMemory = live?.let { backendMemory(it) } ?: memoryPulse
        val cockpitJobs = live?.let { backendJobs(it) } ?: emptyList()
        // With the live Jobs card present, the single local active-task card is
        // redundant — the Jobs card supersedes it.
        val effectiveActiveTask = if (live != null) null else activeTask
        val modelRouter = live?.let { modelRouterSummary(it) }
        val auditEvents = live?.let { backendAuditEvents(it) } ?: emptyList()
        val evidence = live?.let { backendEvidence(it) } ?: emptyList()

        val hasCritical = effectiveApprovals.any { it.risk == ApprovalRisk.CRITICAL }
        val hasSerious = effectiveApprovals.any { it.risk == ApprovalRisk.SERIOUS }
        val hasAnyApproval = effectiveApprovals.isNotEmpty()
        val hasActiveTask = effectiveActiveTask != null || cockpitJobs.any { it.active }

        // A live gateway can run headless, so backend liveness implies the
        // runtime is up even when the local foreground-service probe is false.
        val serviceUp = inputs.serviceRunning || live != null

        val gateway = when {
            live != null -> GatewayStatus.CONNECTED
            !inputs.serviceRunning -> GatewayStatus.DISCONNECTED
            inputs.localOnlyMode -> GatewayStatus.DEGRADED
            else -> GatewayStatus.CONNECTED
        }

        val presence = derivePresence(
            transient = inputs.transientPresence,
            serviceRunning = serviceUp,
            emergencyStopActive = inputs.emergencyStopActive,
            localOnlyMode = inputs.localOnlyMode,
            hasCritical = hasCritical,
            hasSerious = hasSerious,
            hasAnyApproval = hasAnyApproval,
            hasActiveTask = hasActiveTask,
        )

        val suggested = suggestedNextAction(
            presence = presence,
            pendingApprovals = effectiveApprovals,
            activeTask = effectiveActiveTask,
            emergencyStopActive = inputs.emergencyStopActive,
            serviceRunning = serviceUp,
        )

        return JarvisHomeState(
            presence = presence,
            gateway = gateway,
            mockMode = inputs.localOnlyMode,
            emergencyStopActive = inputs.emergencyStopActive,
            activeTask = effectiveActiveTask,
            pendingApprovals = effectiveApprovals,
            workers = effectiveWorkers,
            memoryPulse = effectiveMemory,
            suggestedNextAction = suggested,
            backendSync = inputs.backendSync,
            backendMessage = inputs.backendMessage,
            modelRouter = modelRouter,
            cockpitJobs = cockpitJobs,
            auditEvents = auditEvents,
            evidence = evidence,
            deviceCapability = inputs.deviceCapability,
            voicePhase = inputs.voicePhase,
        )
    }

    // ── Live-overlay mappers (cockpit DTOs → home display types) ───────────

    private fun backendApprovals(snapshot: CockpitHomeSnapshot): List<PendingApproval> =
        snapshot.approvals?.approvals
            ?.filter { it.status.equals("PENDING", ignoreCase = true) }
            ?.map { card ->
                PendingApproval(
                    taskId = card.id,
                    title = card.title.ifBlank { card.summary.ifBlank { "(approval)" } },
                    target = TargetTool.MANUAL,
                    risk = when (card.tier.uppercase()) {
                        "CRITICAL" -> ApprovalRisk.CRITICAL
                        "SERIOUS" -> ApprovalRisk.SERIOUS
                        else -> ApprovalRisk.LOW
                    },
                    reason = card.proposedAction.ifBlank { card.summary }
                        .ifBlank { "Owner approval required." },
                )
            }
            ?: emptyList()

    private fun backendWorkers(snapshot: CockpitHomeSnapshot): List<WorkerStatus> {
        val runningWorkerIds = snapshot.jobs?.jobs
            ?.filter { JobStatus.fromWire(it.status) == JobStatus.RUNNING }
            ?.map { it.workerId }
            ?.toSet()
            ?: emptySet()
        return snapshot.workers?.workers?.map { w ->
            WorkerStatus(
                target = TargetTool.MANUAL,
                displayName = w.displayName.ifBlank { w.id },
                busy = w.id in runningWorkerIds,
                lastActivityAt = null,
            )
        } ?: emptyList()
    }

    private fun backendMemory(snapshot: CockpitHomeSnapshot): List<MemoryPulseEntry> =
        snapshot.memory?.items
            ?.sortedByDescending { parseIsoMillis(it.updatedAt ?: it.createdAt) ?: 0L }
            ?.take(MEMORY_PULSE_SIZE)
            ?.map {
                MemoryPulseEntry(
                    timestamp = parseIsoMillis(it.updatedAt ?: it.createdAt) ?: 0L,
                    label = "${it.category} · ${it.title.ifBlank { it.content.take(40) }}",
                )
            }
            ?: emptyList()

    private fun backendJobs(snapshot: CockpitHomeSnapshot): List<JobSummary> =
        snapshot.jobs?.jobs?.map { job ->
            val status = JobStatus.fromWire(job.status)
            JobSummary(
                id = job.id,
                title = job.title.ifBlank { "(untitled job)" },
                worker = job.workerId,
                status = status,
                statusLabel = (status?.wire ?: job.status).lowercase().replace('_', ' '),
                active = status?.isTerminal == false,
            )
        }
            // Active jobs first, then by recency proxy (kept stable otherwise).
            ?.sortedByDescending { it.active }
            ?: emptyList()

    private fun modelRouterSummary(snapshot: CockpitHomeSnapshot): ModelRouterSummary? {
        val policy = snapshot.models ?: return null
        val routeCount = policy.routes.size
        val primary = policy.defaultRoute
            ?: policy.routes.values.firstOrNull { it.enabled == true }?.let {
                listOfNotNull(it.provider, it.model).joinToString(" · ")
            }
            ?: policy.routes.values.firstOrNull()?.let {
                listOfNotNull(it.provider, it.model).joinToString(" · ")
            }
        val headline = primary?.takeIf { it.isNotBlank() } ?: "Router policy loaded"
        val detail = buildString {
            append(if (routeCount == 1) "1 route" else "$routeCount routes")
            if (policy.freeFirst == true) append(" · free-first")
            if (policy.paidOptIn == true) append(" · paid opt-in")
        }
        return ModelRouterSummary(headline = headline, detail = detail, freeFirst = policy.freeFirst)
    }

    private fun backendAuditEvents(snapshot: CockpitHomeSnapshot): List<AuditEventSummary> =
        snapshot.audit?.records
            ?.sortedByDescending { parseIsoMillis(it.timestamp) ?: 0L }
            ?.take(AUDIT_EVENTS_SIZE)
            ?.map { record ->
                AuditEventSummary(
                    timestamp = parseIsoMillis(record.timestamp),
                    level = record.riskTier,
                    source = record.route.destination.ifBlank { "ledger" },
                    message = record.action.ifBlank { record.userRequest }
                        .ifBlank { "(decision)" },
                )
            }
            ?: emptyList()

    private fun backendEvidence(snapshot: CockpitHomeSnapshot): List<EvidenceSummary> =
        snapshot.research?.items
            ?.take(EVIDENCE_SIZE)
            ?.map {
                EvidenceSummary(
                    id = it.id,
                    title = it.title.ifBlank { "(untitled source)" },
                    strength = it.evidenceStrength,
                    summary = it.summary.ifBlank { it.excerpt.take(120) },
                )
            }
            ?: emptyList()

    private fun parseIsoMillis(iso: String?): Long? {
        if (iso.isNullOrBlank()) return null
        return runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }.getOrNull()
    }

    private fun derivePresence(
        transient: JarvisPresence?,
        serviceRunning: Boolean,
        emergencyStopActive: Boolean,
        localOnlyMode: Boolean,
        hasCritical: Boolean,
        hasSerious: Boolean,
        hasAnyApproval: Boolean,
        hasActiveTask: Boolean,
    ): JarvisPresence {
        // Hard blocks come first — they always win regardless of transient UI state.
        if (emergencyStopActive) return JarvisPresence.EMERGENCY_STOP_ACTIVE
        if (!serviceRunning) return JarvisPresence.SERVICE_STOPPED
        if (hasCritical) return JarvisPresence.CRITICAL_ACTION_PENDING
        if (hasSerious) return JarvisPresence.SERIOUS_ACTION_PENDING
        // Transient UI states (LISTENING / THINKING) only apply while no
        // higher-priority block is active.
        if (transient == JarvisPresence.LISTENING || transient == JarvisPresence.THINKING) {
            return transient
        }
        if (hasAnyApproval) return JarvisPresence.WAITING_FOR_APPROVAL
        if (hasActiveTask) return JarvisPresence.WORKING
        if (localOnlyMode) return JarvisPresence.OFFLINE_MOCK
        return JarvisPresence.IDLE
    }

    private fun riskFor(task: HermesTask): ApprovalRisk = when {
        task.taskType == TaskType.AUDIT && task.status == TaskStatus.NEEDS_REVISION -> ApprovalRisk.CRITICAL
        task.taskType == TaskType.BUILD && task.status == TaskStatus.NEEDS_REVISION -> ApprovalRisk.SERIOUS
        task.status == TaskStatus.NEEDS_REVISION -> ApprovalRisk.SERIOUS
        else -> ApprovalRisk.LOW
    }

    private fun defaultApprovalReason(status: TaskStatus): String = when (status) {
        TaskStatus.NEEDS_REVISION -> "Worker reported issues. Review and decide next step."
        TaskStatus.READY_FOR_HANDOFF -> "Prompt ready to dispatch to the official tool."
        else -> "Awaiting your approval."
    }

    private fun displayNameFor(target: TargetTool): String = when (target) {
        TargetTool.CODEX -> "Codex"
        TargetTool.CHATGPT -> "ChatGPT"
        TargetTool.CLAUDE_CODE -> "Claude Code"
        TargetTool.CLAUDE -> "Claude"
        TargetTool.MANUAL -> "Manual"
    }

    private fun memoryLabel(task: HermesTask): String {
        val verb = when (task.status) {
            TaskStatus.DRAFT -> "drafted"
            TaskStatus.READY_FOR_HANDOFF -> "queued"
            TaskStatus.HANDED_TO_CODEX -> "dispatched to Codex"
            TaskStatus.HANDED_TO_CLAUDE -> "dispatched to Claude"
            TaskStatus.IN_REVIEW -> "reviewing"
            TaskStatus.NEEDS_REVISION -> "flagged for revision"
            TaskStatus.COMPLETE -> "completed"
        }
        val title = task.title.ifBlank { "(untitled task)" }
        return "$verb · $title"
    }

    private fun suggestedNextAction(
        presence: JarvisPresence,
        pendingApprovals: List<PendingApproval>,
        activeTask: ActiveTaskSnapshot?,
        emergencyStopActive: Boolean,
        serviceRunning: Boolean,
    ): SuggestedAction? {
        if (emergencyStopActive) {
            return SuggestedAction(
                label = "Deactivate emergency stop",
                kind = SuggestedKind.DEACTIVATE_EMERGENCY_STOP,
            )
        }
        if (!serviceRunning) {
            return SuggestedAction(label = "Start muse service", kind = SuggestedKind.START_SERVICE)
        }
        val critical = pendingApprovals.firstOrNull { it.risk == ApprovalRisk.CRITICAL }
        if (critical != null) {
            return SuggestedAction(
                label = "Review critical approval: ${critical.title}",
                kind = SuggestedKind.OPEN_APPROVAL,
                taskId = critical.taskId,
            )
        }
        val serious = pendingApprovals.firstOrNull { it.risk == ApprovalRisk.SERIOUS }
        if (serious != null) {
            return SuggestedAction(
                label = "Approve: ${serious.title}",
                kind = SuggestedKind.OPEN_APPROVAL,
                taskId = serious.taskId,
            )
        }
        val firstApproval = pendingApprovals.firstOrNull()
        if (firstApproval != null) {
            return SuggestedAction(
                label = "Approve: ${firstApproval.title}",
                kind = SuggestedKind.OPEN_APPROVAL,
                taskId = firstApproval.taskId,
            )
        }
        if (activeTask != null) {
            return SuggestedAction(
                label = "Check active task: ${activeTask.title}",
                kind = SuggestedKind.OPEN_ACTIVE_TASK,
                taskId = activeTask.taskId,
            )
        }
        return when (presence) {
            JarvisPresence.IDLE, JarvisPresence.OFFLINE_MOCK ->
                SuggestedAction(label = "Ask Jarvis anything", kind = SuggestedKind.OPEN_CHAT)
            JarvisPresence.LISTENING ->
                SuggestedAction(label = "Open voice capture", kind = SuggestedKind.OPEN_VOICE)
            else -> null
        }
    }
}
